#!/usr/bin/env python3
"""
Remove stranded E2E test job files from the Google Drive public share.

These files were left behind by the daily happy-path E2E test before the
cleanup-distribution endpoint existed (pre-PR #411) or when the GDrive
cleanup was silently skipped because gdrive_files was empty.

Usage:
    # Dry run - show what would be deleted
    python scripts/cleanup_test_job_gdrive.py --dry-run

    # Delete all test job files (files whose name contains test song patterns)
    python scripts/cleanup_test_job_gdrive.py

    # Delete files with a specific brand code
    python scripts/cleanup_test_job_gdrive.py --brand-code NOMAD-1271

    # Use a different GDrive folder ID
    python scripts/cleanup_test_job_gdrive.py --gdrive-folder-id 1abc...

Requires:
    - google-api-python-client, google-auth
    - DEFAULT_GDRIVE_FOLDER_ID env var (or --gdrive-folder-id flag)
    - GOOGLE_APPLICATION_CREDENTIALS or gcloud auth application-default login
      (alternatively: gdrive-oauth-credentials secret in Secret Manager)

The test song used by the E2E happy path is:
    Artist: piri
    Title: dog
"""
import argparse
import json
import logging
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

# Patterns that identify test job files
# These match files created by the E2E happy-path test
TEST_FILE_PATTERNS = [
    "piri - dog",  # Current test song (artist: piri, title: dog)
]

PUBLIC_SHARE_SUBFOLDERS = ["CDG", "MP4", "MP4-720p"]


def build_gdrive_service():
    """Build Google Drive API service from credentials."""
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        # Try Secret Manager first
        try:
            import google.cloud.secretmanager as sm
            client = sm.SecretManagerServiceClient()
            name = "projects/nomadkaraoke/secrets/gdrive-oauth-credentials/versions/latest"
            response = client.access_secret_version(request={"name": name})
            creds_data = json.loads(response.payload.data.decode("utf-8"))

            credentials = Credentials(
                token=creds_data.get("token"),
                refresh_token=creds_data.get("refresh_token"),
                token_uri=creds_data.get("token_uri", "https://oauth2.googleapis.com/token"),
                client_id=creds_data.get("client_id"),
                client_secret=creds_data.get("client_secret"),
                scopes=creds_data.get("scopes", ["https://www.googleapis.com/auth/drive.file"]),
            )
            logger.info("Using GDrive credentials from Secret Manager")
        except Exception as e:
            logger.warning(f"Secret Manager failed ({e}), falling back to ADC")
            import google.auth
            credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/drive"]
            )

        return build("drive", "v3", credentials=credentials)

    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        logger.error("Install with: pip install google-api-python-client google-auth google-cloud-secret-manager")
        sys.exit(1)


def find_test_files(service, root_folder_id: str, patterns: list[str]) -> list[dict]:
    """
    Search CDG/, MP4/, MP4-720p/ subfolders for files matching test song patterns.

    Returns list of dicts: {name, id, subfolder}
    """
    found = []

    for subfolder in PUBLIC_SHARE_SUBFOLDERS:
        escaped = subfolder.replace("'", "\\'")
        query = (
            f"name='{escaped}' and '{root_folder_id}' in parents "
            f"and mimeType='application/vnd.google-apps.folder' and trashed=false"
        )
        results = service.files().list(
            q=query, fields="files(id, name)",
            supportsAllDrives=True, includeItemsFromAllDrives=True
        ).execute()

        if not results.get("files"):
            logger.debug(f"Subfolder '{subfolder}' not found, skipping")
            continue

        subfolder_id = results["files"][0]["id"]
        logger.debug(f"Found subfolder '{subfolder}': {subfolder_id}")

        # List all files in this subfolder
        page_token = None
        while True:
            kwargs = dict(
                q=f"'{subfolder_id}' in parents and trashed=false",
                fields="nextPageToken, files(id, name)",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                pageSize=200,
            )
            if page_token:
                kwargs["pageToken"] = page_token

            response = service.files().list(**kwargs).execute()

            for f in response.get("files", []):
                name_lower = f["name"].lower()
                for pattern in patterns:
                    if pattern.lower() in name_lower:
                        found.append({
                            "name": f["name"],
                            "id": f["id"],
                            "subfolder": subfolder,
                        })
                        break

            page_token = response.get("nextPageToken")
            if not page_token:
                break

    return found


def find_files_by_brand_code(service, root_folder_id: str, brand_code: str) -> list[dict]:
    """Find all files with a specific brand code prefix in the public share subfolders."""
    found = []

    for subfolder in PUBLIC_SHARE_SUBFOLDERS:
        escaped = subfolder.replace("'", "\\'")
        query = (
            f"name='{escaped}' and '{root_folder_id}' in parents "
            f"and mimeType='application/vnd.google-apps.folder' and trashed=false"
        )
        results = service.files().list(
            q=query, fields="files(id, name)",
            supportsAllDrives=True, includeItemsFromAllDrives=True
        ).execute()

        if not results.get("files"):
            continue

        subfolder_id = results["files"][0]["id"]
        escaped_brand = brand_code.replace("'", "\\'")
        file_query = (
            f"name contains '{escaped_brand}' and '{subfolder_id}' in parents and trashed=false"
        )
        file_results = service.files().list(
            q=file_query, fields="files(id, name)",
            supportsAllDrives=True, includeItemsFromAllDrives=True
        ).execute()

        for f in file_results.get("files", []):
            if f["name"].startswith(f"{brand_code} - "):
                found.append({
                    "name": f["name"],
                    "id": f["id"],
                    "subfolder": subfolder,
                })

    return found


def main():
    parser = argparse.ArgumentParser(
        description="Remove stranded E2E test job files from Google Drive public share"
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted")
    parser.add_argument(
        "--gdrive-folder-id",
        default=os.getenv("DEFAULT_GDRIVE_FOLDER_ID"),
        help="Root Google Drive folder ID (defaults to DEFAULT_GDRIVE_FOLDER_ID env var)",
    )
    parser.add_argument(
        "--brand-code",
        help="Delete only files with this specific brand code (e.g., NOMAD-1271)",
    )
    parser.add_argument(
        "--patterns",
        nargs="+",
        default=TEST_FILE_PATTERNS,
        help="Filename patterns to match (default: piri - dog)",
    )
    args = parser.parse_args()

    if not args.gdrive_folder_id:
        logger.error(
            "No GDrive folder ID. Set DEFAULT_GDRIVE_FOLDER_ID env var "
            "or pass --gdrive-folder-id"
        )
        sys.exit(1)

    logger.info(f"GDrive root folder: {args.gdrive_folder_id}")
    if args.dry_run:
        logger.info("DRY RUN - no files will be deleted")

    service = build_gdrive_service()

    if args.brand_code:
        logger.info(f"Searching for files with brand code: {args.brand_code}")
        files = find_files_by_brand_code(service, args.gdrive_folder_id, args.brand_code)
    else:
        logger.info(f"Searching for test job files matching patterns: {args.patterns}")
        files = find_test_files(service, args.gdrive_folder_id, args.patterns)

    if not files:
        logger.info("No test job files found")
        return

    logger.info(f"\nFound {len(files)} file(s) to delete:")
    for f in files:
        logger.info(f"  [{f['subfolder']}] {f['name']} (id: {f['id']})")

    if args.dry_run:
        logger.info("\nDry run complete - no files deleted")
        return

    confirm = input(f"\nDelete {len(files)} file(s)? [y/N] ")
    if confirm.lower() != "y":
        logger.info("Aborted")
        return

    deleted = 0
    failed = 0
    for f in files:
        try:
            service.files().delete(
                fileId=f["id"], supportsAllDrives=True
            ).execute()
            logger.info(f"Deleted: [{f['subfolder']}] {f['name']}")
            deleted += 1
        except Exception as e:
            logger.error(f"Failed to delete {f['name']}: {e}")
            failed += 1

    logger.info(f"\nDone: {deleted} deleted, {failed} failed")


if __name__ == "__main__":
    main()
