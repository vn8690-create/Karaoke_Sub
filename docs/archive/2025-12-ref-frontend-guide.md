# Frontend Guide - Karaoke Generator Web UI

## Overview

The karaoke-gen frontend is a Next.js-based static web application deployed to GitHub Pages at **https://gen.nomadkaraoke.com**. It provides a web interface for submitting jobs to the backend API, monitoring job progress, and managing karaoke video generation.

## Architecture

### Deployment Topology

```
┌─────────────────────────────────────────────────────────┐
│  gen.nomadkaraoke.com (GitHub Pages)                   │
│  - Next.js static export                                │
│  - Pure client-side React application                   │
│  - No server-side rendering                             │
└────────────────┬────────────────────────────────────────┘
                 │
                 │ API calls (HTTPS)
                 ▼
┌─────────────────────────────────────────────────────────┐
│  api.nomadkaraoke.com (Cloud Run)                      │
│  - FastAPI backend                                      │
│  - Requires Bearer token authentication                 │
│  - Manages jobs, storage, workers                       │
└─────────────────────────────────────────────────────────┘
```

### Key Components

- **Frontend Domain**: `gen.nomadkaraoke.com` → GitHub Pages (static HTML/CSS/JS)
- **Backend API**: `api.nomadkaraoke.com` → Google Cloud Run
- **Framework**: Next.js 16.0.7 with Turbopack (static export mode)
- **UI Library**: React 19 + shadcn/ui components
- **State Management**: React hooks (useState, useEffect)
- **Storage**: localStorage for auth tokens (client-side only)

## Authentication

### How It Works

The backend API requires **Bearer token authentication** for all requests. The frontend implements client-side token management:

1. **Token Storage**: Tokens are stored in browser localStorage
2. **Token Input**: Users enter tokens via the AuthBanner component
3. **API Requests**: All API calls include `Authorization: Bearer <token>` header
4. **Token Persistence**: Tokens persist across browser sessions until cleared

### Getting a Token

Tokens are managed by administrators. Users need to contact an admin to receive an access token. There is no self-service signup.

**Admin token management**: Admin tokens are stored in Google Cloud Secret Manager (`ADMIN_TOKENS` secret).

### Using Authentication in the UI

```typescript
// Import auth functions
import { setAccessToken, getAccessToken, clearAccessToken } from '@/lib/api';

// Set token (after user input)
setAccessToken('your-token-here');

// Get current token
const token = getAccessToken();

// Clear token (logout)
clearAccessToken();
```

## Features

### 1. Job Submission

Three methods for submitting karaoke generation jobs:

#### File Upload
- Upload audio files directly (FLAC, WAV, MP3, etc.)
- Provide artist and title metadata
- Automatic processing starts immediately

#### YouTube URL
- Submit a YouTube video URL
- Backend downloads audio automatically
- Provide artist and title metadata

#### Audio Search
- Search by artist and title
- Backend finds high-quality audio sources
- Select from multiple results
- Automatic download and processing

### 2. Job Monitoring

Real-time job status tracking with:
- **Status badges**: Visual indicators (Pending, Processing, Awaiting Review, etc.)
- **Progress bars**: Visual progress for active jobs
- **Auto-refresh**: Updates every 10 seconds
- **Manual refresh**: Click refresh button anytime

**Job Statuses**:
- `PENDING` - Job created, waiting to start
- `DOWNLOADING` - Fetching audio
- `PROCESSING_AUDIO` - Separating vocals/instrumental
- `PROCESSING_LYRICS` - Transcribing lyrics
- `AWAITING_REVIEW` - Ready for human review
- `AWAITING_INSTRUMENTAL_SELECTION` - User needs to select instrumental
- `RENDERING_VIDEO` - Creating final video
- `UPLOADING` - Distributing to YouTube/Dropbox
- `COMPLETE` - Finished successfully
- `FAILED` - Error occurred
- `CANCELLED` - User cancelled

### 3. Interactive Elements

#### Lyrics Review
- Launch lyrics correction UI in new tab
- Make timing and text corrections
- Submit corrections to trigger video rendering

#### Instrumental Selection
- Preview multiple instrumental options
- Select best quality instrumental
- Audio player for A/B comparison

#### Job Actions
- **Cancel**: Stop a running job
- **Retry**: Restart a failed job
- **Delete**: Remove job and associated files
- **View Logs**: See detailed processing logs

### 4. Output Access

When jobs complete, access outputs via:
- **YouTube**: Direct link to uploaded video
- **Dropbox**: Link to Dropbox folder with files
- **Direct Downloads**: Download MP4, CDG, TXT files

## Component Structure

### Modular Architecture

```
frontend/
├── app/
│   ├── page.tsx          # Main application page
│   ├── layout.tsx        # Root layout with metadata
│   └── globals.css       # Global styles and CSS variables
│
├── components/
│   ├── auth-banner.tsx   # Authentication UI
│   │
│   ├── job/              # Job-related components
│   │   ├── JobCard.tsx           # Individual job display
│   │   ├── JobSubmission.tsx     # Job creation forms
│   │   ├── JobActions.tsx        # Job management buttons
│   │   ├── JobLogs.tsx           # Log viewer
│   │   ├── OutputLinks.tsx       # Download/distribution links
│   │   └── InstrumentalSelector.tsx  # Instrumental picker
│   │
│   ├── audio-search/     # Audio search feature
│   │   └── AudioSearchDialog.tsx
│   │
│   └── ui/               # Reusable UI primitives (shadcn/ui)
│       ├── button.tsx
│       ├── card.tsx
│       ├── dialog.tsx
│       ├── tabs.tsx
│       └── ... (more)
│
└── lib/
    ├── api.ts            # API client (all backend calls)
    ├── types.ts          # TypeScript type definitions
    └── utils.ts          # Utility functions
```

### Key Files

#### `lib/api.ts` - API Client

The central hub for all backend communication:

```typescript
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.nomadkaraoke.com';

export const api = {
  // Authentication
  setAccessToken(token: string): void
  getAccessToken(): string | null
  clearAccessToken(): void
  
  // Job Management
  listJobs(params?: { status?: string; limit?: number }): Promise<Job[]>
  getJob(jobId: string): Promise<Job>
  uploadJob(file: File, artist: string, title: string): Promise<JobResponse>
  createJobFromUrl(body: CreateJobFromUrlRequest): Promise<JobResponse>
  cancelJob(jobId: string, reason?: string): Promise<void>
  retryJob(jobId: string): Promise<void>
  deleteJob(jobId: string): Promise<void>
  
  // Audio Search
  searchAudio(request: AudioSearchRequest): Promise<AudioSearchResponse>
  getAudioSearchResults(jobId: string): Promise<AudioSearchResult[]>
  selectAudioResult(jobId: string, resultIndex: number): Promise<void>
  
  // Lyrics Review
  getReviewData(jobId: string): Promise<ReviewData>
  completeReview(jobId: string, corrections: any): Promise<void>
  
  // Instrumental Selection
  getInstrumentalOptions(jobId: string): Promise<InstrumentalOption[]>
  selectInstrumental(jobId: string, sourceIndex: number): Promise<void>
  
  // Outputs
  getDownloadUrls(jobId: string): Promise<DownloadUrls>
}
```

#### `components/auth-banner.tsx` - Authentication UI

Prominent banner at top of page for token management:
- Shows "Authentication Required" when no token
- Displays truncated token when authenticated
- Password-masked input field
- Persistent across page reloads

#### `components/job/JobCard.tsx` - Job Display

Main component for displaying individual jobs:
- Collapsible details view
- Status badges and progress bars
- Conditional rendering based on job state
- Integrates all sub-components (actions, logs, outputs, etc.)

## Styling

### Color Scheme

Matches the instrumental review UI for consistency:

```css
/* Background colors */
--bg: #0f0f0f;              /* Very dark, neutral */
--card: #1a1a1a;            /* Card backgrounds */

/* Text colors */
--text: #e5e5e5;            /* Primary text */
--text-muted: #999999;      /* Secondary text */

/* UI colors */
--primary: #3b82f6;         /* Blue (actions, links) */
--success: #10b981;         /* Green (success states) */
--warning: #f59e0b;         /* Orange (warnings) */
--error: #ef4444;           /* Red (errors) */
--border: #2a2a2a;          /* Borders */
```

### Typography

System font stack for fast loading and native feel:

```css
--font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
--font-mono: "SF Mono", Monaco, "Cascadia Code", "Courier New", monospace;
```

## Local Development

### Setup

```bash
cd frontend

# Install dependencies
npm ci --legacy-peer-deps

# Start dev server with hot-reload
npm run dev
# → http://localhost:3000

# Build static export
npm run build
# → Output: frontend/out/

# Run tests
npm test
```

### Environment Variables

Create `.env.local` for local development:

```bash
# Optional: Override API URL for local backend testing
NEXT_PUBLIC_API_URL=http://localhost:8080
```

### Testing Against Production API

The default configuration connects to the production API at `api.nomadkaraoke.com`, so you can develop locally while using the real backend.

**Important**: You'll need a valid access token to make API requests.

## Deployment

### Automatic Deployment (CI/CD)

Changes to `main` branch automatically deploy via GitHub Actions:

1. **Trigger**: Push to `main` or merge PR
2. **Build**: `npm ci --legacy-peer-deps && npm run build`
3. **Deploy**: Upload `frontend/out/` to GitHub Pages
4. **Live**: Available at `gen.nomadkaraoke.com` within ~2 minutes

### CI Workflow

`.github/workflows/ci.yml`:

```yaml
deploy-frontend:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-node@v4
    - name: Install dependencies
      working-directory: frontend
      run: npm ci --legacy-peer-deps
    - name: Build
      working-directory: frontend
      run: npm run build
    - name: Upload artifact
      uses: actions/upload-pages-artifact@v3
      with:
        path: frontend/out
```

### Manual Deployment

If needed, manually deploy via GitHub Pages settings:
1. Build: `cd frontend && npm run build`
2. Upload `frontend/out/` contents to GitHub Pages
3. Wait for GitHub Pages to rebuild

## Configuration Files

### `next.config.mjs`

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',          // Static export for GitHub Pages
  trailingSlash: true,       // Ensures paths work on static hosts
  typescript: {
    ignoreBuildErrors: false // Enforce type safety
  }
};
```

### `package.json`

Key dependencies:
- `next@16.0.7` - Framework
- `react@19.0.0` - UI library
- `lucide-react` - Icon library
- `tailwindcss` - Utility-first CSS
- `@testing-library/react` - Testing

## Common Issues

### Issue: API requests return 404

**Cause**: Frontend trying to call `gen.nomadkaraoke.com/api` instead of `api.nomadkaraoke.com/api`

**Solution**: Verify `API_BASE_URL` in `lib/api.ts` is set to `https://api.nomadkaraoke.com`

### Issue: API requests return 401 Unauthorized

**Cause**: No token or invalid token

**Solution**: Enter a valid access token via the AuthBanner

### Issue: Changes not appearing after deployment

**Cause**: GitHub Pages caching or CDN propagation delay

**Solutions**:
- Wait 2-5 minutes for CDN to update
- Hard refresh browser (Cmd/Ctrl + Shift + R)
- Check GitHub Actions for deployment status

### Issue: Build fails in CI with dependency conflicts

**Cause**: React 19 peer dependency mismatch with testing libraries

**Solution**: Use `npm ci --legacy-peer-deps` (already configured in CI)

## Testing

### Running Tests

```bash
cd frontend

# Run all tests
npm test

# Run with coverage
npm run test:coverage

# Run in CI mode (non-interactive)
npm run test:ci
```

### Test Structure

```
frontend/
├── components/__tests__/
│   ├── JobCard.test.tsx
│   └── ...
└── lib/__tests__/
    ├── api.test.ts
    └── ...
```

### Coverage Requirements

Minimum 70% code coverage enforced in CI (though frontend tests are still being expanded).

## API Integration

### Request Flow

1. User action in UI (e.g., click "Create Job")
2. Component calls API function from `lib/api.ts`
3. API function adds auth header if token exists
4. Fetch request to `api.nomadkaraoke.com`
5. Response parsed and returned
6. Component updates UI with response data

### Error Handling

All API errors are wrapped in `ApiError` class:

```typescript
try {
  const jobs = await api.listJobs({ limit: 20 });
  setJobs(jobs);
} catch (error) {
  if (error instanceof ApiError) {
    console.error(`API Error ${error.status}: ${error.message}`);
    // error.data contains full response body
  }
}
```

## Future Enhancements

Potential improvements for future iterations:

1. **OAuth Integration**: Replace manual token entry with OAuth flow
2. **Real-time Updates**: WebSocket connection for live job updates
3. **Admin Dashboard**: User management, token generation, system stats
4. **Job History**: Pagination and filtering for large job lists
5. **Batch Operations**: Select and manage multiple jobs at once
6. **Mobile Optimization**: Responsive design improvements for mobile devices
7. **Offline Support**: Service worker for offline functionality
8. **Enhanced Testing**: Increase test coverage to 90%+

## Related Documentation

- [Backend API Reference](../README.md#backend-api-reference)
- [Cloud Run Deployment](../03-deployment/CLOUD-RUN-DEPLOYMENT.md)
- [Architecture Overview](./ARCHITECTURE.md)
- [GitHub Pages Setup](.github/workflows/ci.yml)

---

**Last Updated**: December 2025  
**Frontend Version**: Deployed from `main` branch commit `91f51d6`

