# Karaoke-Gen CLI Workflow Documentation

## Overview

The `karaoke-gen` CLI tool is a **complex multi-stage process** for creating professional karaoke videos with perfectly synchronized lyrics. It is **NOT** a simple one-shot batch job - it requires human interaction at several critical decision points and involves multiple remote services, parallel processing, and careful audio/video synchronization.

## High-Level Architecture

```
┌────────────┐
│ User Input │
│  (Audio +  │
│  Metadata) │
└─────┬──────┘
      │
      ├──────────────────────────────────────────┐
      │                                          │
      v                                          v
┌─────────────────┐                    ┌─────────────────┐
│ Audio Separation│                    │    Lyrics       │
│  (Remote GPU)   │                    │  Processing     │
│                 │                    │  (Remote APIs)  │
│ • Stage 1: Clean│                    │                 │
│   Instrumental  │                    │ • Fetch from    │
│ • Stage 2:      │                    │   Genius/Spotify│
│   Backing Vocals│                    │ • Transcribe    │
└────────┬────────┘                    │   w/ AudioShake │
         │                             │ • Correct       │
         │                             │ • HUMAN REVIEW  │
         │                             └────────┬────────┘
         │                                      │
         └──────────────┬───────────────────────┘
                        v
              ┌───────────────────┐
              │ Video Generation  │
              │ • Title screen    │
              │ • Lyrics video    │
              │ • End screen      │
              └─────────┬─────────┘
                        │
                        v
           ┌────────────────────────┐
           │   HUMAN DECISION       │
           │ Select Instrumental    │
           │ (with/without backing  │
           │  vocals)               │
           └────────┬───────────────┘
                    │
                    v
         ┌──────────────────────┐
         │  Video Finalization  │
         │ • Remux with audio   │
         │ • Multiple formats   │
         │ • CDG/TXT generation │
         └──────────┬───────────┘
                    │
                    v
         ┌──────────────────────┐
         │  Distribution        │
         │ • Upload to YouTube  │
         │ • Upload to Dropbox  │
         │ • Discord notify     │
         │ • Email draft        │
         └──────────────────────┘
```

## Stage-by-Stage Workflow

### Stage 0: Input & Setup

**Entry Point:** `karaoke_gen/utils/gen_cli.py::async_main()`

**User Inputs:**
- Audio file path (local FLAC/WAV file) OR YouTube URL
- Artist name
- Song title
- Style parameters JSON (branding, fonts, colors, backgrounds)
- Optional parameters (output directories, format preferences, etc.)

**Environment Variables Required:**
- `AUDIO_SEPARATOR_API_URL` - URL for remote audio separation service (Modal)
- `AUDIOSHAKE_API_TOKEN` - API key for AudioShake transcription service
- `GENIUS_API_TOKEN` - API key for Genius lyrics
- `SPOTIFY_COOKIE_SP_DC` - Spotify cookie for lyrics fetching
- `RAPIDAPI_KEY` - RapidAPI key for additional lyrics sources

**Code Flow:**
1. Parse command-line arguments
2. Initialize `KaraokePrep` class with configuration
3. Determine if input is local file or URL
4. Create output directory structure

**Output:**
- Directory created: `{Artist} - {Title}/`
- Audio file copied/downloaded to output directory
- Converted to WAV format for processing

---

### Stage 1: Parallel Audio & Lyrics Processing

**Entry Point:** `karaoke_gen/karaoke_gen.py::prep_single_track()`

This stage runs **TWO OPERATIONS IN PARALLEL** using `asyncio.gather()`:

#### Stage 1A: Audio Separation (Parallel Track 1)

**Code:** `karaoke_gen/audio_processor.py::process_audio_separation()`

**Process Flow:**

1. **Stage 1 Separation - Clean Instrumental:**
   - Submits audio to remote API (Modal) with models:
     - `model_bs_roformer_ep_317_sdr_12.9755.ckpt` (clean instrumental)
     - `htdemucs_6s.yaml` (6-stem separation: bass, drums, guitar, piano, other, vocals)
   - Polls remote API every 15 seconds for completion
   - Downloads separated stems when complete

   **Outputs from Stage 1:**
   ```
   {Artist} - {Title}/stems/
   ├── {Artist} - {Title} (Vocals model_bs_roformer...).flac
   ├── {Artist} - {Title} (Bass htdemucs_6s).flac
   ├── {Artist} - {Title} (Drums htdemucs_6s).flac
   ├── {Artist} - {Title} (Guitar htdemucs_6s).flac
   ├── {Artist} - {Title} (Piano htdemucs_6s).flac
   └── {Artist} - {Title} (Other htdemucs_6s).flac
   
   {Artist} - {Title}/
   └── {Artist} - {Title} (Instrumental model_bs_roformer...).flac
   ```

2. **Stage 2 Separation - Backing Vocals:**
   - Takes the clean vocal stem from Stage 1
   - Submits it to remote API with model:
     - `mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt`
   - Separates lead vocals from backing vocals
   - Downloads results

   **Outputs from Stage 2:**
   ```
   {Artist} - {Title}/stems/
   ├── {Artist} - {Title} (Lead Vocals mel_band_roformer...).flac
   └── {Artist} - {Title} (Backing Vocals mel_band_roformer...).flac
   ```

3. **Post-Processing:**
   - Generates combined instrumentals (instrumental + backing vocals)
   - Normalizes all audio files to consistent volume

   **Additional Outputs:**
   ```
   {Artist} - {Title}/
   ├── {Artist} - {Title} (Instrumental +BV mel_band_roformer...).flac
   ```

**Why Two Stages?**
- Stage 1 produces the cleanest possible instrumental
- Stage 2 isolates backing vocals from lead vocals
- This gives users choice: pure instrumental OR instrumental with backing vocals

**Remote Service:** Modal-hosted audio-separator API
**Processing Time:** ~3-5 minutes (GPU-accelerated)
**Polling Interval:** 15 seconds

---

#### Stage 1B: Lyrics Transcription (Parallel Track 2)

**Code:** `karaoke_gen/lyrics_processor.py::transcribe_lyrics()`

**Process Flow:**

1. **Lyrics Fetching:**
   - Queries Genius API for lyrics
   - Queries Spotify API (via RapidAPI) for lyrics
   - Queries Musixmatch API (via RapidAPI) for lyrics
   - Uses best available source

2. **Audio Transcription:**
   - Uploads audio to AudioShake API
   - Polls for transcription completion
   - Downloads word-level timestamps and confidence scores

   **AudioShake Response Format:**
   ```json
   {
     "words": [
       {
         "text": "hello",
         "start_time": 1.234,
         "end_time": 1.567,
         "confidence": 0.95
       },
       ...
     ]
   }
   ```

3. **Lyrics Correction (Automatic):**
   - Uses `LyricsTranscriber` package (imported from `lyrics_transcriber_local/`)
   - Finds "anchor sequences" - matching word patterns between transcription & reference lyrics
   - Applies sophisticated correction algorithms:
     - `ExtendAnchorHandler` - extends known-good matches
     - `SyllablesMatchHandler` - matches by syllable count
   - Handles common transcription errors (homophones, etc.)

4. **Human Review Interface:**
   - Launches web server on `localhost:8000`
   - Serves React-based review UI
   - User can:
     - Play audio with synchronized highlighting
     - Edit incorrect words
     - Split/merge lines
     - Adjust timing
   - Generates preview video (360p) for review

   **Why Human Review is Critical:**
   - Transcription is never 100% accurate
   - Homophone errors ("there" vs "their")
   - Slang, proper nouns, non-standard pronunciations
   - Artistic decisions about line breaks

5. **Final Output Generation:**
   - After user completes review, generates:
     - LRC file (timed lyrics)
     - ASS file (karaoke subtitles)
     - Full 4K video with scrolling lyrics
     - Plain text files (corrected, uncorrected, original)

   **Outputs:**
   ```
   {Artist} - {Title}/lyrics/
   ├── {Artist} - {Title} (Karaoke).lrc
   ├── {Artist} - {Title} (Karaoke).ass
   ├── {Artist} - {Title} (Lyrics Genius).txt
   ├── {Artist} - {Title} (Lyrics Spotify).txt
   ├── {Artist} - {Title} (Lyrics Corrected).txt
   ├── {Artist} - {Title} (Lyrics Uncorrected).txt
   └── {Artist} - {Title} (Lyrics Corrections).json
   
   {Artist} - {Title}/
   ├── {Artist} - {Title} (Karaoke).lrc  [moved from lyrics/]
   └── {Artist} - {Title} (With Vocals).mkv  [moved from lyrics/]
   ```

**Remote Services:**
- Genius API (lyrics source)
- Spotify API via RapidAPI (lyrics source)
- Musixmatch API via RapidAPI (lyrics source)
- AudioShake API (transcription)

**Processing Time:** 
- Transcription: ~1-2 minutes
- Correction: ~30 seconds
- Human review: **variable** (5-15 minutes typical)
- Video generation: ~5-10 minutes (4K, software encoding)

**Local Web Server:**
- Port: `8000`
- Framework: FastAPI (served by `lyrics_transcriber`)
- Purpose: Interactive review interface

**Why This is Complex:**
- Multiple fallback sources for lyrics
- Word-level timestamp alignment
- Confidence-based correction
- **Human-in-the-loop required** for quality

---

### Stage 2: Title & End Screen Generation

**Entry Point:** `karaoke_gen/karaoke_gen.py::prep_single_track()` (after parallel processing)

**Code:** `karaoke_gen/video_generator.py::create_title_video()` and `create_end_video()`

**Process:**
1. Renders title screen with artist/song name
2. Renders end screen with "Thank you for singing!" message
3. Uses style parameters from JSON (fonts, colors, backgrounds)
4. Exports as both JPG (thumbnail) and MOV (video)

**Outputs:**
```
{Artist} - {Title}/
├── {Artist} - {Title} (Title).jpg
├── {Artist} - {Title} (Title).mov
├── {Artist} - {Title} (End).jpg
└── {Artist} - {Title} (End).mov
```

**Duration:** ~10 seconds for both screens combined

---

### Stage 3: Countdown Padding Synchronization

**Entry Point:** `karaoke_gen/karaoke_gen.py::prep_single_track()` (after parallel processing complete)

**Problem Being Solved:**
When lyrics start very early in the song (within first 3 seconds), the `LyricsTranscriber` automatically adds a countdown intro ("3... 2... 1...") to give the singer preparation time. This adds ~3 seconds of silence to the **vocal audio only**.

**Code:** `karaoke_gen/audio_processor.py::apply_countdown_padding_to_instrumentals()`

**Process:**
1. Detects if countdown padding was added (from `LyricsTranscriber` output)
2. Pads **all instrumental files** with matching silence
3. Updates file paths to use padded versions

**Why This Matters:**
- Without padding, instrumental and vocals are out of sync
- Video subtitles would be misaligned
- Karaoke experience would be broken

**Modified Files:**
```
{Artist} - {Title}/
├── {Artist} - {Title} (Instrumental ...) (Padded).flac
└── {Artist} - {Title} (Instrumental +BV ...) (Padded).flac
```

---

### Stage 4: Finalization - User Interaction Required

**Entry Point:** `karaoke_gen/utils/gen_cli.py::async_main()` calls `KaraokeFinalise.process()`

**Code:** `karaoke_gen/karaoke_finalise/karaoke_finalise.py`

This stage has **TWO CRITICAL HUMAN DECISION POINTS:**

#### Decision Point 1: Select Instrumental Audio

**Why:**
Some songs sound better with backing vocals, others without. This is a **subjective artistic decision** that cannot be automated.

**User Prompt:**
```
Choose instrumental audio file to use as karaoke audio:
1: {Artist} - {Title} (Instrumental model_bs_roformer...).flac
2: {Artist} - {Title} (Instrumental +BV mel_band_roformer...).flac

Choose instrumental audio file to use as karaoke audio: [1]/2:
```

**User Action:** Types `1` or `2` and presses Enter

**Impact:** Determines which audio track is used for final karaoke video

#### Decision Point 2: Approve Final Videos

**Process:**
1. System generates 4 final video files:
   - Lossless 4K MP4 (PCM audio)
   - Lossless 4K MKV (FLAC audio)  
   - Lossy 4K MP4 (AAC audio)
   - Lossy 720p MP4 (AAC audio)

2. User reviews videos (plays them locally)

3. **User Prompt:**
```
Final video files created:
- Lossless 4K MP4: {path}
- Lossless 4K MKV: {path}
- Lossy 4K MP4: {path}
- Lossy 720p MP4: {path}

Please check them! Proceed? [y]/n
```

**User Action:** Types `y` and presses Enter (or `n` to abort)

---

### Stage 5: Packaging & Distribution

**Code:** `karaoke_gen/karaoke_finalise/karaoke_finalise.py::process()`

**5.1 CDG/MP3 ZIP Generation** (if `--enable_cdg`)

**What is CDG?**
CD+Graphics format used by physical karaoke machines. Each frame is a low-res (288x192) bitmap with lyrics overlay.

**Process:**
1. Converts LRC to TOML format
2. Uses `lyrics_transcriber.output.cdg.CDGGenerator` to create binary CDG file
3. Converts instrumental FLAC to MP3
4. Creates ZIP: `{Artist} - {Title} (Final Karaoke CDG).zip`
   - Contains: `{Artist} - {Title} (Karaoke).cdg` + `.mp3`

**Why CDG?**
- Compatibility with professional karaoke systems
- Small file size for distribution
- Industry standard format

---

**5.2 TXT/MP3 ZIP Generation** (if `--enable_txt`)

**Process:**
1. Converts LRC to plain TXT format (using `lyrics-converter` library)
2. Uses same MP3 from CDG generation
3. Creates ZIP: `{Artist} - {Title} (Final Karaoke TXT).zip`

**Why TXT?**
- Simple format for karaoke apps
- Human-readable backup
- Easy integration with basic players

---

**5.3 Video Remuxing & Encoding**

**Process:**
1. **Remux with selected instrumental:**
   - Takes `(With Vocals).mkv` (has lyrics video, original audio)
   - Replaces audio track with chosen instrumental
   - Creates `(Karaoke).mp4`

2. **Concatenate with title/end screens:**
   - Combines: Title (5s) + Karaoke + End (5s)
   - Creates temporary PCM-audio MP4

3. **Encode to multiple formats:**
   - **Lossless 4K MP4:** H.264 video + PCM audio (uncompressed)
   - **Lossless 4K MKV:** H.264 video + FLAC audio (compressed lossless)
   - **Lossy 4K MP4:** H.264 video + AAC audio (for web/sharing)
   - **Lossy 720p MP4:** H.264 video (1280x720) + AAC audio (for slower connections)

**Encoding Time:** ~15-20 minutes total (CPU-intensive, no GPU)

**Why Multiple Formats?**
- **Lossless MP4/MKV:** Archival quality, future re-encoding
- **Lossy 4K:** YouTube upload, online sharing
- **Lossy 720p:** Email, mobile devices, bandwidth-constrained users

---

**5.4 Folder Organization** (if `--brand_prefix` and `--organised_dir`)

**Process:**
1. Calculates next sequential brand code (e.g., `NOMAD-1155`)
2. Renames directory: `{Artist} - {Title}` → `{BRAND}-{NUM} - {Artist} - {Title}`
3. Moves directory to organized location
4. Updates all internal file references

**Purpose:**
- Consistent branding across all tracks
- Easy inventory management
- Sequential numbering for catalog

---

**5.5 Public Share Distribution** (if `--public_share_dir`)

**Process:**
1. Copies files to public share directory:
   - `(Final Karaoke CDG).zip`
   - `(Final Karaoke TXT).zip`  
   - `(Final Karaoke Lossy 4k).mp4`
   - `(Final Karaoke Lossy 720p).mp4`

2. **Syncs to cloud** (if `--rclone_destination`):
   - Uses `rclone` to copy public share directory to Google Drive / Dropbox
   - Makes files available for customer download

**Purpose:**
- Separate customer-facing files from working files
- Clean download location
- Automated cloud backup

---

**5.6 YouTube Upload** (if `--youtube_client_secrets_file`)

**Dependencies:**
- Google API OAuth2 credentials
- YouTube Data API v3 enabled
- Local credentials cache: `youtube_upload_token.pickle`

**Process:**
1. **Check for existing video:**
   - Searches YouTube channel for matching title
   - Avoids duplicate uploads

2. **Authenticate:**
   - Uses OAuth2 flow (browser-based on first run)
   - Stores credentials for future use

3. **Upload MKV file:**
   - Uses `(Final Karaoke Lossless 4k).mkv`
   - Title: `{Artist} - {Title} (Karaoke)`
   - Description: Loaded from `--youtube_description_file`
   - Visibility: Unlisted (not public by default)

4. **Upload thumbnail:**
   - Uses `(Title).jpg` as video thumbnail
   - Makes video visually appealing in YouTube interface

**Why MKV for YouTube?**
- FLAC audio preserves quality
- YouTube re-encodes anyway
- Avoids double compression

**Processing Time:** ~2-5 minutes depending on upload speed

---

**5.7 Discord Notification** (if `--discord_webhook_url`)

**Process:**
1. Constructs webhook payload with:
   - Artist & title
   - YouTube URL
   - Brand code
   - Completion timestamp

2. POSTs to Discord webhook

**Purpose:**
- Team notification
- Production log
- Automatic documentation

---

**5.8 Email Draft Creation** (if `--email_template_file`)

**Dependencies:**
- Gmail API credentials
- OAuth2 authentication
- Template file with placeholders

**Process:**
1. Generates rclone sharing link for organized folder
2. Loads email template
3. Replaces placeholders:
   - `{ARTIST}` → Artist name
   - `{TITLE}` → Song title
   - `{BRAND_CODE}` → Brand code
   - `{FOLDER_LINK}` → Dropbox/Drive link
   - `{YOUTUBE_URL}` → YouTube URL

4. Creates Gmail draft (does NOT send automatically)

**Purpose:**
- Customer communication template
- Ready-to-send delivery notification
- Consistent professional messaging

---

**5.9 Final Output Logging**

**Terminal Output:**
```
Karaoke generation complete! Output files:

Track: {Artist} - {Title}

Working Files:
 Video With Vocals: {path}
 Video With Instrumental: {path}

Final Videos:
 Lossless 4K MP4 (PCM): {path}
 Lossless 4K MKV (FLAC): {path}
 Lossy 4K MP4 (AAC): {path}
 Lossy 720p MP4 (AAC): {path}

Karaoke Files:
 CDG+MP3 ZIP: {path}
 TXT+MP3 ZIP: {path}

Organization:
 Brand Code: {code}
 Directory: {path}

Sharing:
 Folder Link: {url} (copied to clipboard)
 YouTube URL: {url} (copied to clipboard)
```

---

## Dependency Summary

### External Services

| Service | Purpose | Required | Alternative |
|---------|---------|----------|-------------|
| **audio-separator API (Modal)** | GPU-accelerated stem separation | Yes | Local CPU (very slow) |
| **AudioShake API** | Word-level transcription | Yes | None (transcription required) |
| **Genius API** | Lyrics fetching | No | Spotify, Musixmatch, manual file |
| **Spotify API (via RapidAPI)** | Lyrics fetching | No | Genius, Musixmatch, manual file |
| **Musixmatch API (via RapidAPI)** | Lyrics fetching | No | Genius, Spotify, manual file |
| **YouTube Data API** | Video upload | No | Manual upload |
| **Gmail API** | Email draft creation | No | Manual email |
| **Discord Webhook** | Notifications | No | Manual notification |
| **rclone** | Cloud file sync | No | Manual copy |

### Credentials Required

**API Keys** (environment variables):
- `AUDIO_SEPARATOR_API_URL`
- `AUDIOSHAKE_API_TOKEN`
- `GENIUS_API_TOKEN`
- `RAPIDAPI_KEY`
- `SPOTIFY_COOKIE_SP_DC`

**OAuth2 Credentials** (JSON files):
- YouTube: `--youtube_client_secrets_file` (Google OAuth)
- Gmail: Same credentials file can be used

**Webhooks:**
- `--discord_webhook_url` (Discord webhook URL)

### Local Tools Required

- **FFmpeg** - Video/audio encoding (must be in PATH)
- **rclone** - Cloud file sync (optional)

---

## Critical Design Decisions

### Why Modal for Audio Separation?

**Reason:** GPU acceleration makes separation **10-100x faster**

**Local CPU:**
- Single song: 20-40 minutes
- Requires 16GB+ RAM
- Blocks computer during processing

**Remote GPU (Modal):**
- Single song: 3-5 minutes  
- No local resources used
- Can process multiple songs in parallel

### Why Human Review is Non-Negotiable?

**Reasons:**
1. **Transcription errors are common:**
   - Homophones ("there" vs "their", "your" vs "you're")
   - Slang ("gonna" vs "going to")
   - Proper nouns (artist/place names)

2. **Artistic decisions:**
   - Line break placement
   - Timing adjustments for singability
   - Handling of ad-libs and background vocals

3. **Quality assurance:**
   - Ensures professional output
   - Catches edge cases
   - Validates before expensive video generation

**Time Investment:** 5-15 minutes per song
**Value:** Difference between amateur and professional quality

### Why Multiple Instrumental Options?

**Reason:** Musical taste is subjective

**Examples:**
- **Backing vocals enhance:** Gospel, R&B, many pop songs
- **Backing vocals interfere:** Rock, metal, some country

**Solution:** Generate both, let user decide after listening

### Why So Many Output Formats?

**Different use cases:**

| Format | Use Case | Quality | File Size |
|--------|----------|---------|-----------|
| Lossless 4K MP4 | Archival, re-encoding | Highest | ~500MB |
| Lossless 4K MKV | YouTube upload | Highest | ~300MB |
| Lossy 4K MP4 | Online sharing, streaming | High | ~100MB |
| Lossy 720p MP4 | Mobile, email, low bandwidth | Medium | ~30MB |
| CDG+MP3 ZIP | Professional karaoke systems | Medium | ~10MB |
| TXT+MP3 ZIP | Simple karaoke apps | Medium | ~10MB |

**Total storage per song:** ~950MB

---

## Challenges for Cloud Migration

Based on this workflow analysis, here are the key challenges for building a cloud-hosted version:

### 1. **Human-in-the-Loop Requirements**

**Current CLI:** 
- Launches local web server (port 8000)
- User reviews in browser
- Synchronous wait for completion

**Cloud Challenge:**
- Cannot block server waiting for user
- Need async job queue
- Need persistent state storage
- Need notification system for "review ready"

**Potential Solutions:**
- Job state machine: `pending` → `awaiting_review` → `in_review` → `processing` → `complete`
- Email/SMS notification when review is ready
- Review interface hosted separately (React SPA)
- Firestore for job state persistence

### 2. **Instrumental Selection**

**Current CLI:**
- Presents choice after audio separation completes
- Waits for user input
- Then proceeds with finalization

**Cloud Challenge:**
- Cannot present CLI prompt to web user
- Need UI for audio playback comparison
- Need way to store selection

**Potential Solutions:**
- Generate both instrumentals always
- Provide preview audio player in web UI
- Store selection in job metadata
- Allow changing selection after initial submission

### 3. **File Storage**

**Current CLI:**
- All files on local disk
- Large working files (stems, uncompressed video)
- Total: ~2GB per song during processing

**Cloud Challenge:**
- Need cloud storage (GCS)
- Bandwidth costs for upload/download
- Cleanup strategy for temp files
- Access control for user files

**Potential Solutions:**
- GCS lifecycle policies (delete after 7 days)
- Signed URLs for secure download
- Separate buckets for temp vs final files
- Compress intermediate files

### 4. **Processing Time**

**Current CLI:**
- Total: 30-45 minutes per song
- Phases:
  - Audio separation: 3-5 min (GPU)
  - Transcription: 1-2 min (AudioShake)
  - **Human review: 5-15 min** (variable)
  - Video generation: 10 min (CPU)
  - Video encoding: 15-20 min (CPU)
  - YouTube upload: 2-5 min (network)

**Cloud Challenge:**
- Long-running Cloud Run requests not ideal
- Need async job processing
- Need progress updates
- Need timeout handling

**Potential Solutions:**
- Background worker for video encoding
- Cloud Build for containerized jobs?
- Modal for GPU tasks (already using)
- Progress polling endpoint

### 5. **Sequential Dependencies**

**Current CLI:**
- Linear flow with checkpoints
- Can resume from last checkpoint
- State is implicit (files on disk)

**Cloud Challenge:**
- Need explicit state management
- Need retry logic
- Need checkpoint/resume capability
- Need error recovery

**Potential Solutions:**
- Firestore for job state machine
- Timeline events for progress tracking
- Idempotent operations
- Graceful degradation

### 6. **Authentication & Authorization**

**Current CLI:**
- No auth needed (local machine)
- All credentials in environment

**Cloud Challenge:**
- Multi-user system
- Private job data
- Credential storage
- Quota management

**Potential Solutions:**
- User accounts (Firebase Auth)
- Per-user GCS buckets
- Secrets in Google Secret Manager
- Usage limits per user

### 7. **Cost Management**

**Current CLI:**
- One-time credential costs
- No per-job costs (except API calls)

**Cloud Challenge:**
- Per-job costs:
  - Cloud Run compute
  - GCS storage
  - GCS bandwidth
  - AudioShake API ($0.02-0.05 per minute)
- Need cost tracking
- Need to pass costs to user ($2 per song target)

**Potential Solutions:**
- Estimate costs upfront
- Show progress to justify time
- Optimize encoding settings
- Cache common resources

---

## Conclusion

The `karaoke-gen` CLI workflow is a **sophisticated, human-in-the-loop pipeline** that produces professional-quality karaoke videos. The key challenges for cloud migration are:

1. **Async job processing** with state persistence
2. **Human interaction points** (review, selection)
3. **File storage & lifecycle** management
4. **Long-running tasks** (video encoding)
5. **Cost optimization** while maintaining quality

**The workflow cannot be simplified** without sacrificing quality. The human review and decision points are essential features, not bugs.

The cloud architecture must embrace this complexity and design around the async, multi-stage nature of the process rather than trying to force it into a simple request/response model.

