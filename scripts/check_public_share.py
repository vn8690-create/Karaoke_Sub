#!/usr/bin/env python3
"""
Check the public Google Drive share for issues.

Invokes the gdrive-validator Cloud Function and displays results.

Usage:
    python scripts/check_public_share.py          # Formatted output
    python scripts/check_public_share.py --json    # Raw JSON output

Exit codes:
    0 = all clear
    1 = issues found
    2 = error
"""
import argparse
import json
import subprocess
import sys


PROJECT_ID = "nomadkaraoke"
REGION = "us-central1"
FUNCTION_NAME = "gdrive-validator"


def call_cloud_function() -> dict:
    """Call the GDrive validator Cloud Function via gcloud."""
    result = subprocess.run(
        [
            "gcloud", "functions", "call", FUNCTION_NAME,
            f"--region={REGION}",
            f"--project={PROJECT_ID}",
            "--format=json",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )

    if result.returncode != 0:
        raise RuntimeError(f"gcloud call failed: {result.stderr.strip()}")

    # gcloud functions call --format=json returns the response as a double-encoded JSON string
    parsed = json.loads(result.stdout)

    # If parsed is a string, it's the double-encoded function response
    if isinstance(parsed, str):
        return json.loads(parsed)

    # If it's a dict with a "result" field (older gcloud versions), unwrap it
    if isinstance(parsed, dict) and "result" in parsed:
        inner = parsed["result"]
        return json.loads(inner) if isinstance(inner, str) else inner

    return parsed


def print_formatted(data: dict):
    """Print validation results in a human-readable format."""
    status = data.get("status", "unknown")

    if status == "ok":
        summary = data.get("summary", {})
        print("✅ All clear - no issues found\n")
        print(f"  MP4:     {summary.get('mp4', 0):,} files")
        print(f"  MP4-720p:{summary.get('mp4_720p', 0):,} files")
        print(f"  CDG:     {summary.get('cdg', 0):,} files")
        print(f"  Total:   {summary.get('total', 0):,} files")
        return

    if status == "issues_found":
        issues = data.get("issues", {})

        # Duplicates
        dupes = issues.get("duplicates", {})
        if dupes:
            print("⚠️  DUPLICATES:")
            for folder, seq_map in dupes.items():
                for seq_num, filenames in seq_map.items():
                    print(f"  {folder}: NOMAD-{int(seq_num):04d} appears {len(filenames)} times")
                    for f in filenames[:3]:
                        print(f"    - {f}")
                    if len(filenames) > 3:
                        print(f"    - ...and {len(filenames) - 3} more")
            print()

        # Invalid filenames
        invalid = issues.get("invalid_filenames", {})
        if invalid:
            print("⚠️  INVALID FILENAMES:")
            for folder, filenames in invalid.items():
                for f in filenames[:5]:
                    print(f"  {folder}: {f}")
                if len(filenames) > 5:
                    print(f"  ...and {len(filenames) - 5} more in {folder}")
            print()

        # Gaps
        gaps = issues.get("gaps", {})
        if gaps:
            print("⚠️  SEQUENCE GAPS:")
            for folder, missing in gaps.items():
                if len(missing) <= 10:
                    print(f"  {folder}: missing {', '.join(map(str, missing))}")
                else:
                    print(f"  {folder}: {len(missing)} gaps (first 5: {', '.join(map(str, missing[:5]))}...)")
            print()

        # Summary
        summary = issues.get("summary", {})
        print(f"Checked: {summary.get('mp4', 0)} MP4, {summary.get('mp4_720p', 0)} 720p, {summary.get('cdg', 0)} CDG files")
        return

    if status == "warning":
        print(f"⚠️  {data.get('message', 'Unknown warning')}")
        return

    print(f"❌ Unexpected status: {status}")
    print(f"   {data.get('message', '')}")


def main():
    parser = argparse.ArgumentParser(description="Check public GDrive share for issues")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    try:
        data = call_cloud_function()
    except Exception as e:
        if args.json:
            print(json.dumps({"status": "error", "message": str(e)}))
        else:
            print(f"❌ Error: {e}")
        sys.exit(2)

    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print_formatted(data)

    status = data.get("status", "error")
    if status == "ok":
        sys.exit(0)
    elif status == "issues_found":
        sys.exit(1)
    else:
        sys.exit(2)


if __name__ == "__main__":
    main()
