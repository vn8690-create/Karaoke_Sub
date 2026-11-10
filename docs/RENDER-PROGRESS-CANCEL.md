# FFmpeg render progress + cancel API

Backend-only change for Karaoke Sub Local Studio. Claude remains responsible for Studio UI, timeline and Karaoke Editor.

## Why
Previously long-running render jobs sent only start/end messages. Users couldn't see real encoder progress or stop an expensive encode without closing the whole application.

## API
- POST /api/projects/{project_id}/render (existing): starts a render.
- GET /api/projects/{project_id} (existing): now reports intermediate progress from FFmpeg between roughly 10 and 97 while rendering. Reaches 100 only when render completes and files are published.
- POST /api/projects/{project_id}/render/cancel (new): request cancellation of a running or queued render. When cancellation finishes, the project status becomes "cancelled" and can be rendered again.

The cancellation endpoint never cancels separate/transcribe/align jobs. The API is protected by the Local Studio loopback-only trusted-host and origin checks.

## Implementation
FFmpeg writes machine-readable progress on stdout (-progress pipe:1). A watchdog terminates the process when a cancellation event is set. stderr goes to a temporary disk file, preventing pipe-memory deadlocks. The system cleans rendering.mp4 on cancel; a previous karaoke.mp4 is preserved until successful replacement. This does not implement resume-after-cancel or pause.

## Test
    python -m unittest tests.local_studio.test_render_progress -v
    python -m unittest discover -s tests/local_studio -v

CI runs on Windows and Linux. Perform a real 7-10 minute MP4 test on the target PC before claiming long-video performance is solved.

## Claude handoff
When wiring the UI, keep it simple:
- Poll GET project; show progress and message.
- While status is queued/rendering, show Cancel Render.
- Send POST render/cancel, keep polling until "cancelled" or "ready".
- Allow Retry Render after cancellation, preserving project media and lyric timing.
