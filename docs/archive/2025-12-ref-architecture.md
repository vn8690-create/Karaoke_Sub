# Karaoke Generator - Architecture Overview

**Last Updated:** 2025-12-08

This document describes both the original CLI architecture and the cloud backend architecture.

---

## Cloud Backend Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CLOUD ARCHITECTURE                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Frontend (Cloudflare Pages)                       │   │
│  │                                                                      │   │
│  │  • React + TypeScript                                               │   │
│  │  • Job submission                                                   │   │
│  │  • Progress tracking                                                │   │
│  │  • Lyrics review interface  ⚠️                                      │   │
│  │  • Instrumental selection   ⚠️                                      │   │
│  │  • File download                                                    │   │
│  └────────────────────────────────┬────────────────────────────────────┘   │
│                                   │ HTTPS                                   │
│                                   ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                 Backend API (Cloud Run - FastAPI)                    │   │
│  │                                                                      │   │
│  │  Endpoints:                                                         │   │
│  │  • POST /api/jobs/upload     - Create job with file                 │   │
│  │  • GET  /api/jobs/{id}       - Job status                           │   │
│  │  • GET  /api/jobs/{id}/review - Get review data                     │   │
│  │  • POST /api/jobs/{id}/review - Save corrections                    │   │
│  │  • POST /api/jobs/{id}/complete-review - Finish review              │   │
│  │  • POST /api/jobs/{id}/select-instrumental - Choose audio           │   │
│  │                                                                      │   │
│  │  Workers (Background Tasks):                                        │   │
│  │  • Audio Worker      - Stem separation via Modal API                │   │
│  │  • Lyrics Worker     - Transcription via AudioShake                 │   │
│  │  • Screens Worker    - Title/end screen generation                  │   │
│  │  • Render Worker     - Karaoke video with lyrics (post-review)      │   │
│  │  • Video Worker      - Final assembly and encoding                  │   │
│  └───────────────┬─────────────────────────────────────────────────────┘   │
│                  │                                                          │
│        ┌─────────┴─────────┐                                               │
│        │                   │                                               │
│        ▼                   ▼                                               │
│  ┌───────────────┐   ┌─────────────────────────────────────────────────┐   │
│  │   Firestore   │   │           Google Cloud Storage                   │   │
│  │               │   │                                                  │   │
│  │ • Job state   │   │  jobs/{job_id}/                                 │   │
│  │ • Timeline    │   │  ├── input/           - Original audio          │   │
│  │ • Metadata    │   │  ├── stems/           - Separated audio         │   │
│  │ • File URLs   │   │  ├── lyrics/          - Corrections, LRC, ASS   │   │
│  │               │   │  ├── screens/         - Title, end videos       │   │
│  └───────────────┘   │  ├── videos/          - with_vocals.mkv         │   │
│                      │  └── finals/          - Output formats          │   │
│                      └─────────────────────────────────────────────────┘   │
│                                                                             │
│  External APIs:                                                            │
│  • Modal       - GPU audio separation                                      │
│  • AudioShake  - Lyrics transcription                                      │
│  • Genius      - Reference lyrics                                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Processing Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           JOB PROCESSING FLOW                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   1. UPLOAD                                                                 │
│      │                                                                      │
│      │  POST /api/jobs/upload                                              │
│      │  • Save audio to GCS                                                │
│      │  • Create job in Firestore                                          │
│      │  • Trigger parallel workers                                         │
│      │                                                                      │
│      ▼                                                                      │
│   2. PARALLEL PROCESSING                                                    │
│      │                                                                      │
│      │  ┌─────────────────┐         ┌─────────────────┐                    │
│      │  │  Audio Worker   │         │  Lyrics Worker  │                    │
│      │  │                 │         │                 │                    │
│      │  │ • Modal API     │         │ • AudioShake    │                    │
│      │  │ • 2-stage sep   │         │ • Auto-correct  │                    │
│      │  │ • Upload stems  │         │ • Save JSON     │                    │
│      │  │                 │         │ • NO VIDEO      │                    │
│      │  └────────┬────────┘         └────────┬────────┘                    │
│      │           │                           │                             │
│      │           └───────────┬───────────────┘                             │
│      │                       │                                             │
│      ▼                       ▼                                             │
│   3. SCREENS GENERATION (waits for both)                                   │
│      │                                                                      │
│      │  • Generate title screen (5s video)                                 │
│      │  • Generate end screen (5s video)                                   │
│      │  • Upload to GCS                                                    │
│      │                                                                      │
│      ▼                                                                      │
│   4. HUMAN REVIEW  ⚠️ BLOCKING                                             │
│      │                                                                      │
│      │  Status: AWAITING_REVIEW                                            │
│      │                                                                      │
│      │  React UI:                                                          │
│      │  • GET /review → Load corrections + audio                           │
│      │  • User corrects lyrics, adjusts timing                             │
│      │  • POST /review → Save progress                                     │
│      │  • POST /complete-review → Finish                                   │
│      │                                                                      │
│      ▼                                                                      │
│   5. VIDEO RENDERING (post-review)                                         │
│      │                                                                      │
│      │  Status: RENDERING_VIDEO                                            │
│      │                                                                      │
│      │  Render Video Worker:                                               │
│      │  • Download corrected lyrics                                        │
│      │  • Use OutputGenerator from LyricsTranscriber                       │
│      │  • Generate with_vocals.mkv (karaoke video)                         │
│      │  • Upload to GCS                                                    │
│      │                                                                      │
│      ▼                                                                      │
│   6. INSTRUMENTAL SELECTION  ⚠️ BLOCKING                                   │
│      │                                                                      │
│      │  Status: AWAITING_INSTRUMENTAL_SELECTION                            │
│      │                                                                      │
│      │  Frontend:                                                          │
│      │  • Show audio players for both options                              │
│      │  • User listens and chooses                                         │
│      │  • POST /select-instrumental → Submit choice                        │
│      │                                                                      │
│      ▼                                                                      │
│   7. FINAL VIDEO GENERATION                                                │
│      │                                                                      │
│      │  Status: GENERATING_VIDEO                                           │
│      │                                                                      │
│      │  Video Worker:                                                      │
│      │  • Remux with_vocals.mkv with selected instrumental                 │
│      │  • Concatenate: title + karaoke + end                               │
│      │  • Encode to multiple formats                                       │
│      │  • Upload finals to GCS                                             │
│      │                                                                      │
│      ▼                                                                      │
│   8. COMPLETE                                                              │
│                                                                             │
│      Status: COMPLETE                                                       │
│      User downloads final videos via signed URLs                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### LyricsTranscriber Integration

**Key Insight:** We use LyricsTranscriber as a library, NOT as a server.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    LYRICSTRANSCRIBER INTEGRATION                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   CLI Mode (Original):                    Cloud Mode (Our Approach):        │
│   ─────────────────────                   ──────────────────────────        │
│                                                                             │
│   LyricsTranscriber                       LyricsTranscriber                 │
│   ├── transcribe()                        ├── transcribe()   ✅            │
│   ├── correct()                           ├── correct()      ✅            │
│   ├── ReviewServer.start()  ← BLOCKS      │                                │
│   │   └── Waits for browser               │   (Skip server - save JSON)   │
│   │       to submit                       │                                │
│   └── OutputGenerator                     │                                │
│       └── generates video                 │   ... ASYNC GAP ...            │
│                                           │   (Human reviews via React)    │
│                                           │                                │
│                                           └── OutputGenerator   ✅         │
│                                               └── generates video          │
│                                                   (called after review)    │
│                                                                             │
│   ❌ DON'T USE:                          ✅ DO USE:                        │
│   • ReviewServer                          • LyricsTranscriber              │
│   • server.start()                        • CorrectionResult               │
│   • Blocking waits                        • OutputGenerator                │
│                                           • OutputConfig                   │
│                                           • CorrectionOperations           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Original CLI Architecture

### Core Functionality

The Karaoke Generator CLI transforms audio files (local files or YouTube URLs) into professional karaoke videos with synchronized lyrics.

### Main Processing Pipeline

#### 1. Input Processing
- **Input Sources**: Local audio files (FLAC, WAV, MP3) or YouTube URLs
- **Metadata**: Artist name and song title
- **File Handling**: Converts input media to WAV format

#### 2. Parallel Processing Phase

**Audio Separation** (Compute-Intensive):
- Multiple AI models for different separation tasks
- Remote processing via Modal API when `AUDIO_SEPARATOR_API_URL` is set
- Output: Multiple stems (vocals, instrumental, backing vocals, drums, bass)

**Lyrics Processing**:
- Genius API for lyric retrieval
- AudioShake API for transcription
- AI-powered lyrics correction

#### 3. Human Review Phase (Interactive)
- Web interface launches in browser
- Users review and correct transcribed lyrics
- Fine-tuning of timing and text accuracy
- **Critical**: Requires human interaction

#### 4. Output Generation
- LRC files (timed lyrics)
- CDG files (CD+Graphics karaoke format)
- ASS/SSA files (subtitles)
- Video files with lyric overlays

#### 5. Video Production
- Title/End screens with custom branding
- Multiple format exports (4K, 720p, lossless, lossy)

### External API Dependencies

**Required:**
- AudioShake API: Lyrics transcription/timing
- Genius API: Lyrics text retrieval

**Optional:**
- YouTube Data API: Video upload
- Modal API: Remote audio separation

### Computing Requirements

- **GPU/Accelerated Processing**: NVIDIA CUDA, Apple Silicon MPS, or CPU fallback
- **Storage**: Large model files, temporary files, final outputs
- **Processing Time**: 30-45 minutes per track

---

## File Structure

### GCS Bucket Structure

```
jobs/{job_id}/
├── input/
│   └── original.flac              # Uploaded audio file
├── stems/
│   ├── vocals.flac
│   ├── instrumental_clean.flac
│   ├── instrumental_with_backing.flac
│   ├── backing_vocals.flac
│   ├── drums.flac
│   └── bass.flac
├── lyrics/
│   ├── corrections.json           # Initial auto-corrected
│   ├── corrections_updated.json   # After human review
│   ├── original.txt
│   ├── corrected.txt
│   ├── karaoke.lrc
│   └── karaoke.ass
├── screens/
│   ├── title.mov
│   └── end.mov
├── videos/
│   └── with_vocals.mkv            # Karaoke video with lyrics
└── finals/
    ├── lossless_4k.mp4
    ├── lossless_4k.mkv
    ├── lossy_4k.mp4
    └── lossy_720p.mp4
```

### Firestore Job Document

```javascript
{
  job_id: "abc123",
  status: "awaiting_review",
  artist: "ABBA",
  title: "Waterloo",
  created_at: Timestamp,
  updated_at: Timestamp,
  
  // GCS paths
  input_media_gcs_path: "jobs/abc123/input/original.flac",
  
  // Signed URLs for download
  file_urls: {
    stems: {
      vocals: "https://...",
      instrumental_clean: "https://..."
    },
    lyrics: {
      corrections: "https://...",
      lrc: "https://..."
    },
    videos: {
      with_vocals: "https://..."
    },
    finals: {
      lossless_4k_mp4: "https://...",
      lossy_720p: "https://..."
    }
  },
  
  // Worker progress (parallel tracking)
  state_data: {
    audio_progress: {
      status: "complete",
      stage: 2,
      stems_uploaded: true
    },
    lyrics_progress: {
      status: "complete",
      transcription_done: true,
      corrections_saved: true
    }
  },
  
  // Timeline for debugging
  timeline: [
    { status: "pending", timestamp: "...", message: "Job created" },
    { status: "downloading", timestamp: "...", message: "Processing started" },
    // ...
  ],
  
  // Error tracking
  error_message: null,
  error_details: null
}
```

---

## State Machine

### Job States

| State | Description | Human Action |
|-------|-------------|--------------|
| `pending` | Job created, not started | - |
| `downloading` | Processing audio file | - |
| `separating_stage1` | Audio separation stage 1 | - |
| `separating_stage2` | Audio separation stage 2 | - |
| `transcribing` | Lyrics transcription | - |
| `generating_screens` | Creating title/end screens | - |
| `awaiting_review` | **Waiting for human** | Review lyrics |
| `in_review` | Human actively reviewing | Edit lyrics |
| `review_complete` | Review submitted | - |
| `rendering_video` | Generating karaoke video | - |
| `awaiting_instrumental_selection` | **Waiting for human** | Choose audio |
| `instrumental_selected` | Selection made | - |
| `generating_video` | Final encoding | - |
| `complete` | All done | Download files |
| `failed` | Error occurred | - |
| `cancelled` | User cancelled | - |

### Processing Times (Estimated)

| Stage | Duration | Notes |
|-------|----------|-------|
| Audio separation | 5-8 min | Modal API |
| Lyrics transcription | 2-3 min | AudioShake API |
| Auto-correction | 30 sec | Local processing |
| Screens generation | 30 sec | Local FFmpeg |
| Human review | 5-15 min | User dependent |
| Video rendering | 10-15 min | OutputGenerator |
| Instrumental selection | 30 sec | User dependent |
| Final encoding | 5-10 min | Multiple formats |
| **Total** | **30-50 min** | Including human time |

---

## Technology Stack

### Backend
- **Framework**: FastAPI
- **Runtime**: Python 3.12
- **Container**: Docker on Cloud Run
- **Database**: Firestore
- **Storage**: Google Cloud Storage
- **Secrets**: Google Secret Manager

### Frontend (Planned)
- **Framework**: React 18 + TypeScript
- **Build**: Vite
- **Hosting**: Cloudflare Pages
- **State**: TanStack Query + Zustand

### External Services
- **Audio Separation**: Modal (GPU)
- **Transcription**: AudioShake API
- **Lyrics**: Genius API
- **Video Processing**: FFmpeg (bundled)

### Infrastructure
- **IaC**: Pulumi
- **CI/CD**: Google Cloud Build
- **Monitoring**: Cloud Logging, Cloud Monitoring
