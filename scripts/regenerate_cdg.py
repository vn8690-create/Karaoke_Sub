#!/usr/bin/env python3
"""
Regenerate CDG ZIP packages for jobs that completed without them.

This one-time remediation script handles the case where jobs completed with
enable_cdg=True but the CDG ZIP wasn't produced (e.g., due to the custom
instrumental path bug fixed in b671b83f).

For each job, the script:
1. Fetches job data from Firestore
2. Downloads LRC and instrumental audio from GCS
3. Loads theme CDG styles
4. Generates CDG package using PackagingService
5. Uploads CDG ZIP to GCS
6. Updates file_urls.packages.cdg_zip in Firestore
7. Uploads CDG ZIP to Google Drive (if GDrive was used)
8. Updates state_data.gdrive_files in Firestore
9. Uploads CDG/TXT ZIPs to Dropbox (if Dropbox was used)

Usage:
    python -m scripts.regenerate_cdg JOB_ID [JOB_ID ...]
    python -m scripts.regenerate_cdg 5b6aba25 5161b069

Requirements:
    - GOOGLE_CLOUD_PROJECT=nomadkaraoke (or set via gcloud config)
    - gcloud auth application-default login (for GCS/Firestore access)
"""

import argparse
import logging
import os
import sys
import tempfile
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "nomadkaraoke")

from backend.services.storage_service import StorageService
from backend.services.job_manager import JobManager
from backend.services.packaging_service import PackagingService
from karaoke_gen.style_loader import get_cdg_format
from karaoke_gen.utils import sanitize_filename

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("regenerate_cdg")


def get_instrumental_gcs_key(instrumental_selection: str) -> str:
    """Get the GCS file_urls.stems key for the instrumental selection."""
    if instrumental_selection == "custom":
        return "custom_instrumental"
    elif instrumental_selection == "clean":
        return "instrumental_clean"
    else:  # with_backing
        return "instrumental_with_backing"


def get_instrumental_suffix(instrumental_selection: str) -> str:
    """Get the filename suffix for the instrumental selection."""
    if instrumental_selection == "custom":
        return "Custom"
    elif instrumental_selection == "clean":
        return "Clean"
    else:
        return "Backing"


def regenerate_cdg_for_job(job_id: str, storage: StorageService, job_manager: JobManager, dry_run: bool = False):
    """Regenerate CDG ZIP for a single job."""
    logger.info(f"=== Processing job {job_id} ===")

    # 1. Fetch job from Firestore
    job = job_manager.get_job(job_id)
    if not job:
        logger.error(f"Job {job_id} not found in Firestore")
        return False

    logger.info(f"Job: {job.artist} - {job.title}")
    logger.info(f"  enable_cdg: {job.enable_cdg}")
    logger.info(f"  status: {job.status}")

    if not job.enable_cdg:
        logger.warning(f"Job {job_id} does not have enable_cdg=True, skipping")
        return False

    # Check if CDG already exists in GCS
    existing_cdg = job.file_urls.get("packages", {}).get("cdg_zip")
    cdg_already_in_gcs = existing_cdg and storage.file_exists(existing_cdg)
    if cdg_already_in_gcs:
        logger.info(f"CDG ZIP already exists in GCS: {existing_cdg}")
    elif existing_cdg:
        logger.warning("CDG ZIP in Firestore but NOT in GCS, will regenerate")

    # Get instrumental selection
    instrumental_selection = job.state_data.get("instrumental_selection", "clean")
    logger.info(f"  instrumental_selection: {instrumental_selection}")

    # Get lyrics metadata for countdown padding
    lyrics_metadata = job.state_data.get("lyrics_metadata", {})
    lrc_has_countdown_padding = lyrics_metadata.get("has_countdown_padding", False)
    countdown_padding_seconds = lyrics_metadata.get("countdown_padding_seconds", 3.0)
    logger.info(f"  countdown_padding: {lrc_has_countdown_padding} ({countdown_padding_seconds}s)")

    # Check required files exist in file_urls
    lrc_url = job.file_urls.get("lyrics", {}).get("lrc")
    if not lrc_url:
        logger.error(f"Job {job_id} has no LRC file URL")
        return False

    instrumental_key = get_instrumental_gcs_key(instrumental_selection)
    instrumental_url = job.file_urls.get("stems", {}).get(instrumental_key)
    if not instrumental_url:
        logger.error(f"Job {job_id} has no instrumental URL for key '{instrumental_key}'")
        return False

    # Get style_params for CDG styles
    style_params_url = job.style_params_gcs_path

    if dry_run:
        logger.info(f"DRY RUN: Would regenerate CDG for {job.artist} - {job.title}")
        return True

    # 2. Download or regenerate CDG/TXT packages
    with tempfile.TemporaryDirectory(prefix=f"cdg-regen-{job_id}-") as temp_dir:
        safe_artist = sanitize_filename(job.artist) if job.artist else "Unknown"
        safe_title = sanitize_filename(job.title) if job.title else "Unknown"
        base_name = f"{safe_artist} - {safe_title}"
        instrumental_suffix = get_instrumental_suffix(instrumental_selection)
        brand_code = getattr(job, "brand_code", None) or job.state_data.get("brand_code", "UNKNOWN")

        cdg_zip_path = os.path.join(temp_dir, f"{base_name} (Final Karaoke CDG).zip")
        txt_zip_path = os.path.join(temp_dir, f"{base_name} (Final Karaoke TXT).zip")

        if cdg_already_in_gcs:
            # Download existing CDG ZIP from GCS for distribution
            logger.info("Downloading existing CDG ZIP from GCS for distribution...")
            storage.download_file(existing_cdg, cdg_zip_path)

            # Also download TXT if it exists
            existing_txt = job.file_urls.get("packages", {}).get("txt_zip")
            if existing_txt and storage.file_exists(existing_txt):
                logger.info("Downloading existing TXT ZIP from GCS...")
                storage.download_file(existing_txt, txt_zip_path)
        else:
            # Regenerate: download source files and generate packages
            # Download LRC
            lrc_path = os.path.join(temp_dir, f"{base_name} (Karaoke).lrc")
            logger.info(f"Downloading LRC: {lrc_url}")
            storage.download_file(lrc_url, lrc_path)

            # Download instrumental
            instrumental_path = os.path.join(temp_dir, f"{base_name} (Instrumental {instrumental_suffix}).flac")
            logger.info(f"Downloading instrumental: {instrumental_url}")
            storage.download_file(instrumental_url, instrumental_path)

            # Download and parse style_params
            import json
            style_params_path = os.path.join(temp_dir, "style_params.json")
            style_params = None

            if style_params_url:
                try:
                    logger.info(f"Downloading style params: {style_params_url}")
                    storage.download_file(style_params_url, style_params_path)
                    with open(style_params_path) as f:
                        style_params = json.load(f)
                except Exception as e:
                    logger.warning(f"Failed to download style_params from {style_params_url}: {e}")

            # Fallback: load theme style_params from GCS theme directory
            if style_params is None:
                theme_id = getattr(job, "theme_id", "nomad") or "nomad"
                theme_path = f"themes/{theme_id}/style_params.json"
                logger.info(f"Trying theme style_params: {theme_path}")
                try:
                    storage.download_file(theme_path, style_params_path)
                    with open(style_params_path) as f:
                        style_params = json.load(f)
                except Exception as e:
                    logger.error(f"Failed to load theme style_params: {e}")
                    return False

            # Download CDG style assets (font, backgrounds) referenced in style_params
            cdg_section = style_params.get("cdg", {})
            style_dir = os.path.join(temp_dir, "style")
            os.makedirs(style_dir, exist_ok=True)

            # Resolve asset GCS paths. Per-job style_params have full paths like
            # "themes/nomad/assets/AvenirNext-Bold.ttf". Theme-level style_params
            # have bare filenames like "AvenirNext-Bold.ttf" that need to be
            # resolved against the theme's assets directory.
            theme_id = getattr(job, "theme_id", "nomad") or "nomad"
            theme_assets_prefix = f"themes/{theme_id}/assets"

            for asset_key in ["font_path", "instrumental_background", "title_screen_background", "outro_background"]:
                asset_path = cdg_section.get(asset_key)
                if not asset_path or not isinstance(asset_path, str) or os.path.isabs(asset_path):
                    continue

                # Determine the GCS path — bare filenames need the theme prefix
                if "/" not in asset_path:
                    gcs_path = f"{theme_assets_prefix}/{asset_path}"
                else:
                    gcs_path = asset_path

                local_path = os.path.join(style_dir, os.path.basename(asset_path))
                try:
                    storage.download_file(gcs_path, local_path)
                    cdg_section[asset_key] = local_path
                    logger.info(f"Downloaded CDG asset {asset_key}: {gcs_path}")
                except Exception as e:
                    logger.warning(f"Failed to download CDG asset {asset_key} from {gcs_path}: {e}")

            # 3. Extract CDG styles
            cdg_styles = get_cdg_format(style_params)
            if not cdg_styles:
                logger.error(f"No CDG styles found in theme for job {job_id}")
                return False

            logger.info("CDG styles loaded successfully")

            # 4. Generate CDG package
            packaging_service = PackagingService(
                cdg_styles=cdg_styles,
                dry_run=False,
                non_interactive=True,
            )

            mp3_path = os.path.join(temp_dir, f"{base_name} (Karaoke).mp3")
            cdg_path = os.path.join(temp_dir, f"{base_name} (Karaoke).cdg")

            logger.info("Generating CDG package...")
            zip_file, mp3_file, cdg_file = packaging_service.create_cdg_package(
                lrc_file=lrc_path,
                audio_file=instrumental_path,
                output_zip_path=cdg_zip_path,
                artist=job.artist,
                title=job.title,
                output_mp3_path=mp3_path,
                output_cdg_path=cdg_path,
                lrc_has_countdown_padding=lrc_has_countdown_padding,
                countdown_padding_seconds=countdown_padding_seconds,
            )

            if not os.path.isfile(cdg_zip_path):
                logger.error(f"CDG ZIP not created at expected path: {cdg_zip_path}")
                return False

            zip_size = os.path.getsize(cdg_zip_path)
            logger.info(f"CDG ZIP created: {cdg_zip_path} ({zip_size / 1024:.1f} KB)")

            # 5. Upload CDG ZIP to GCS
            gcs_cdg_path = f"jobs/{job_id}/packages/cdg_zip.zip"
            logger.info(f"Uploading CDG ZIP to GCS: {gcs_cdg_path}")
            storage.upload_file(cdg_zip_path, gcs_cdg_path)

            # 6. Update Firestore file_urls
            logger.info("Updating Firestore file_urls.packages.cdg_zip")
            job_manager.update_file_url(job_id, "packages", "cdg_zip", gcs_cdg_path)

            # Also generate TXT if enabled
            if job.enable_txt:
                logger.info("Job also has enable_txt=True, generating TXT package...")
                try:
                    txt_zip, txt_file = packaging_service.create_txt_package(
                        lrc_file=lrc_path,
                        mp3_file=mp3_path,
                        output_zip_path=txt_zip_path,
                    )
                    if os.path.isfile(txt_zip_path):
                        gcs_txt_path = f"jobs/{job_id}/packages/txt_zip.zip"
                        storage.upload_file(txt_zip_path, gcs_txt_path)
                        job_manager.update_file_url(job_id, "packages", "txt_zip", gcs_txt_path)
                        logger.info(f"TXT ZIP uploaded: {gcs_txt_path}")
                except Exception as e:
                    logger.error(f"TXT generation failed: {e}")

        # === Distribution steps (run for both new and existing packages) ===

        # 7. Upload to GDrive if job uses it
        gdrive_files = job.state_data.get("gdrive_files", {})
        if gdrive_files and "cdg" not in gdrive_files:
            logger.info("Uploading CDG ZIP to Google Drive...")
            try:
                from backend.services.gdrive_service import get_gdrive_service
                gdrive = get_gdrive_service()
                if gdrive.is_configured:
                    gdrive_folder_id = getattr(job, "gdrive_folder_id", None)

                    if gdrive_folder_id:
                        safe_base = sanitize_filename(f"{job.artist} - {job.title}")
                        filename_base = f"{brand_code} - {safe_base}"
                        cdg_folder_id = gdrive.get_or_create_folder(gdrive_folder_id, "CDG")
                        file_id = gdrive.upload_file(
                            cdg_zip_path,
                            cdg_folder_id,
                            f"{filename_base}.zip",
                        )
                        logger.info(f"Uploaded CDG to GDrive: {file_id}")

                        # 8. Update state_data.gdrive_files
                        gdrive_files["cdg"] = file_id
                        job_manager.update_job(job_id, {"state_data.gdrive_files": gdrive_files})
                        logger.info("Updated Firestore state_data.gdrive_files")
                    else:
                        logger.warning("No gdrive_folder_id on job, skipping GDrive upload")
                else:
                    logger.warning("GDrive not configured, skipping upload")
            except Exception as e:
                logger.error(f"GDrive upload failed (non-fatal): {e}")
        elif gdrive_files:
            logger.info("GDrive already has CDG file, skipping GDrive upload")
        else:
            logger.info("No existing GDrive files, skipping GDrive upload")

        # 9. Upload to Dropbox if job uses it
        dropbox_path = job.dropbox_path
        if dropbox_path:
            logger.info("Uploading packages to Dropbox...")
            try:
                from backend.services.dropbox_service import get_dropbox_service
                dropbox = get_dropbox_service()
                if dropbox.is_configured:
                    safe_base = sanitize_filename(f"{job.artist} - {job.title}")
                    folder_name = f"{brand_code} - {safe_base}"
                    remote_folder = f"{dropbox_path}/{folder_name}"

                    # Upload CDG ZIP
                    if os.path.isfile(cdg_zip_path):
                        cdg_remote = f"{remote_folder}/{os.path.basename(cdg_zip_path)}"
                        dropbox.upload_file(cdg_zip_path, cdg_remote)
                        logger.info(f"Uploaded CDG to Dropbox: {cdg_remote}")

                    # Upload TXT ZIP
                    if os.path.isfile(txt_zip_path):
                        txt_remote = f"{remote_folder}/{os.path.basename(txt_zip_path)}"
                        dropbox.upload_file(txt_zip_path, txt_remote)
                        logger.info(f"Uploaded TXT to Dropbox: {txt_remote}")
                else:
                    logger.warning("Dropbox not configured, skipping upload")
            except Exception as e:
                logger.error(f"Dropbox upload failed (non-fatal): {e}")
        else:
            logger.info("No dropbox_path on job, skipping Dropbox upload")

    logger.info(f"=== Job {job_id} CDG regeneration complete ===")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Regenerate CDG ZIP packages for jobs that completed without them."
    )
    parser.add_argument(
        "job_ids",
        nargs="+",
        help="Job IDs to regenerate CDG for",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    args = parser.parse_args()

    storage = StorageService()
    job_manager = JobManager()

    results = {}
    for job_id in args.job_ids:
        try:
            success = regenerate_cdg_for_job(job_id, storage, job_manager, dry_run=args.dry_run)
            results[job_id] = "OK" if success else "FAILED"
        except Exception as e:
            logger.exception(f"Error processing job {job_id}: {e}")
            results[job_id] = f"ERROR: {e}"

    # Summary
    logger.info("\n=== Summary ===")
    for job_id, status in results.items():
        logger.info(f"  {job_id}: {status}")

    # Exit with error if any failed
    if any(s != "OK" for s in results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
