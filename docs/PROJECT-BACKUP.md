# Portable ZIP Backup for Karaoke Sub Local Studio

Backend-only capability. No changes to the new Claude UI, timeline, or Karaoke Editor.

## Why
The existing download endpoint returns project JSON, not the actual audio, vocals, instrumental, background, rendered MP4, or subtitle files. Moving a project to another Windows PC requires those files too.

## API
- GET /api/projects/{project_id}/backup : returns karaoke-project-backup.zip.
- POST /api/projects/import-backup : multipart upload field named backup; returns a new project (HTTP 201).
- GET /api/projects : displays both original and restored projects.

Example using PowerShell after starting Local Studio on localhost:8776:

    curl.exe -o my-song-backup.zip http://127.0.0.1:8776/api/projects/PROJECT_ID/backup
    curl.exe -F "backup=@my-song-backup.zip" http://127.0.0.1:8776/api/projects/import-backup

The importer always assigns a new project ID. It never overwrites an existing project. Exports are rejected while a project is processing to avoid incomplete snapshots.

## Format
Manifest (manifest.json) plus referenced files under media/. Example: media/source.mp3, media/audio.wav, media/instrumental.wav, media/vocals.wav, media/background.mp4, media/lyrics.ass, media/lyrics.srt, media/lyrics.lrc, media/karaoke.mp4.

Files not referenced by project.files are not included. No models, API keys, Python environments, unrelated folders, or global app settings.

## Integrity and safety
- SHA-256 and original byte size for every file.
- Rejects unrecognized ZIP entries, directory traversal, symbolic links, case-insensitive filename collisions, unexpected extensions and corrupted data.
- Maximum 32 files, 4 GiB each, 16 GiB total unpacked, 12 GiB archive upload.
- Validates lyric timestamps before restoring. Restores through a staging directory then publishes under a new ID.
- The existing loopback-only HTTP and Origin/Host restrictions apply.
- ZIPs include user-supplied music/video. Keep backups private and ensure adequate free disk space for a temporary ZIP.

## Tests
    python -m unittest tests.local_studio.test_project_backup -v

Tests cover round trip and malicious ZIP cases. CI runs on Ubuntu and Windows as part of the repository Local Studio workflow.

## Frontend handoff to Claude
Claude can add Import ZIP and Backup ZIP actions to the Project Library later. This backend does not modify Claude's design or feature area.
