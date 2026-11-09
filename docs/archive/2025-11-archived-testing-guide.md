# End-to-End Testing Guide

This guide provides instructions for testing the complete karaoke generation workflow.

## Prerequisites

- Backend deployed to Cloud Run (or running locally)
- Frontend deployed to Cloudflare Pages (or running locally)
- Audio Separator API accessible
- Required API keys configured (AudioShake, Genius)

## Local Testing Setup

### Start Backend Locally

```bash
cd backend

# Set environment variables
export GOOGLE_CLOUD_PROJECT=your-project-id
export GCS_BUCKET_NAME=karaoke-gen-storage
export AUDIO_SEPARATOR_API_URL=https://your-audio-separator-api
export AUDIOSHAKE_API_KEY=your-key
export GENIUS_API_KEY=your-key

# Run backend
uvicorn backend.main:app --reload --port 8080
```

### Start Frontend Locally

```bash
cd frontend-react

# Install dependencies
npm install

# Start dev server
npm run dev

# Access at http://localhost:5173
```

## Test Scenarios

### Test 1: Job Submission from URL

**Purpose**: Verify URL-based job submission works

**Steps**:
1. Navigate to the frontend
2. Select "From URL" mode
3. Enter a YouTube URL: `https://www.youtube.com/watch?v=dQw4w9WgXcQ`
4. Click "Generate Karaoke"
5. Verify job ID is displayed
6. Check job status updates automatically

**Expected Result**:
- Job created successfully
- Status changes: Queued → Processing → Complete
- Progress bar updates
- Timeline shows events

**Validation**:
```bash
# Check backend logs
gcloud logging read "resource.type=cloud_run_revision" --limit 50

# Check Firestore
gcloud firestore documents list jobs --limit 10

# Check Cloud Storage
gsutil ls gs://karaoke-gen-storage/outputs/
```

### Test 2: File Upload

**Purpose**: Verify file upload and processing

**Steps**:
1. Navigate to the frontend
2. Select "Upload File" mode
3. Choose an audio file (MP3, WAV, FLAC)
4. Enter artist name: "Rick Astley"
5. Enter song title: "Never Gonna Give You Up"
6. Click "Upload and Generate"
7. Monitor progress

**Expected Result**:
- File uploads successfully
- Job processes the uploaded file
- Status progresses to Complete
- Output files available for download

**File Size Limits**:
- Test with small file (~1MB)
- Test with medium file (~10MB)
- Test with large file (~50MB)
- Verify appropriate error for files >100MB

### Test 3: Concurrent Jobs

**Purpose**: Verify system handles multiple simultaneous jobs

**Steps**:
1. Submit 3-5 jobs at once
2. Monitor all job statuses
3. Verify no jobs interfere with each other
4. Check all complete successfully

**Expected Result**:
- All jobs process independently
- No job ID conflicts
- All jobs complete
- No resource exhaustion

### Test 4: Error Handling

**Purpose**: Verify error scenarios are handled gracefully

**Test Cases**:

#### Invalid URL
1. Submit invalid YouTube URL
2. Expected: Clear error message

#### Unsupported File Type
1. Try to upload .exe or .pdf file
2. Expected: File type validation error

#### Missing Artist/Title
1. Upload file without artist or title
2. Expected: Form validation error

#### Network Failure
1. Stop backend
2. Try to submit job
3. Expected: Connection error message

#### Processing Failure
1. Submit URL that doesn't exist
2. Expected: Error status with message

### Test 5: Download Results

**Purpose**: Verify output files are accessible

**Steps**:
1. Wait for job to complete
2. Click download links
3. Verify files download correctly
4. Check file integrity

**Files to Verify**:
- Video file (.mp4 or .mkv)
- Lyrics file (.lrc)
- Audio file (instrumental)

**Validation**:
```bash
# Verify video plays
ffprobe downloaded-video.mp4

# Check lyrics file format
cat downloaded-lyrics.lrc

# Play audio
ffplay downloaded-instrumental.flac
```

### Test 6: Status Polling

**Purpose**: Verify real-time status updates

**Steps**:
1. Submit a long-running job
2. Observe status updates
3. Verify polling happens automatically
4. Check timeline updates

**Expected Behavior**:
- Status updates every 3 seconds during processing
- No polling when complete or errored
- Progress percentage increases
- Timeline accumulates events

### Test 7: Mobile Responsiveness

**Purpose**: Verify UI works on mobile devices

**Steps**:
1. Open frontend on mobile device or use browser DevTools
2. Test all interactions
3. Verify layout adapts
4. Check touch interactions work

**Resolutions to Test**:
- iPhone SE (375x667)
- iPhone 12 Pro (390x844)
- iPad (768x1024)
- Desktop (1920x1080)

## Performance Testing

### Load Testing

Use a tool like Apache Bench or Artillery:

```bash
# Install Artillery
npm install -g artillery

# Create test script
cat > artillery-test.yml <<EOF
config:
  target: "https://your-cloud-run-url"
  phases:
    - duration: 60
      arrivalRate: 5
scenarios:
  - name: "Submit job"
    flow:
      - post:
          url: "/api/jobs"
          json:
            url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
EOF

# Run test
artillery run artillery-test.yml
```

### Performance Metrics

Monitor:
- **API Response Time**: <500ms for job submission
- **Processing Time**: ~5-10 minutes for typical song
- **Memory Usage**: <2GB per Cloud Run instance
- **CPU Usage**: Should not max out consistently

## Automated Testing

### Backend API Tests

Create `backend/tests/test_api.py`:

```python
import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_create_job_from_url():
    response = client.post("/api/jobs", json={
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    })
    assert response.status_code == 202
    assert "job_id" in response.json()

def test_get_job_status():
    # Create job first
    create_response = client.post("/api/jobs", json={
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    })
    job_id = create_response.json()["job_id"]
    
    # Get status
    response = client.get(f"/api/jobs/{job_id}")
    assert response.status_code == 200
    assert response.json()["job_id"] == job_id
```

Run tests:
```bash
cd backend
pytest tests/
```

### Frontend Component Tests

Create `frontend-react/src/components/__tests__/JobSubmission.test.tsx`:

```typescript
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { JobSubmission } from '../JobSubmission';

const queryClient = new QueryClient();

test('renders submission form', () => {
  render(
    <QueryClientProvider client={queryClient}>
      <JobSubmission />
    </QueryClientProvider>
  );
  
  expect(screen.getByText('Create Karaoke Video')).toBeInTheDocument();
  expect(screen.getByPlaceholderText(/YouTube URL/i)).toBeInTheDocument();
});

test('switches between URL and upload modes', () => {
  render(
    <QueryClientProvider client={queryClient}>
      <JobSubmission />
    </QueryClientProvider>
  );
  
  const uploadButton = screen.getByText('Upload File');
  fireEvent.click(uploadButton);
  
  expect(screen.getByLabelText(/Artist/i)).toBeInTheDocument();
  expect(screen.getByLabelText(/Song Title/i)).toBeInTheDocument();
});
```

## Monitoring in Production

### Cloud Logging

```bash
# View recent errors
gcloud logging read "severity>=ERROR AND resource.type=cloud_run_revision" --limit 50

# View job submissions
gcloud logging read "jsonPayload.message=~'Job.*created'" --limit 20

# View processing completions
gcloud logging read "jsonPayload.message=~'complete'" --limit 20
```

### Cloud Monitoring

Set up alerts for:
- Error rate > 5%
- Latency > 10s
- Instance count > 8
- Memory usage > 90%

### Firestore Metrics

Monitor:
- Job completion rate
- Average processing time
- Error rate by type
- Active jobs count

## Troubleshooting

### Job Stuck in Processing

1. Check Cloud Run logs for errors
2. Verify Audio Separator API is accessible
3. Check for timeout issues
4. Manually mark job as errored if needed

### Downloads Not Working

1. Verify files exist in Cloud Storage
2. Check signed URL expiration
3. Verify CORS settings on bucket
4. Test direct GCS access

### High Latency

1. Check Cloud Run cold starts
2. Increase min instances if needed
3. Verify API dependencies are responsive
4. Check network routing

## Success Criteria

✅ Jobs submit successfully (>95% success rate)
✅ Processing completes within expected time
✅ All output files are downloadable
✅ Status updates in real-time
✅ Error messages are clear and helpful
✅ UI is responsive and intuitive
✅ No data loss or corruption
✅ Concurrent jobs don't interfere
✅ System recovers from failures gracefully

## Test Checklist

- [ ] URL submission works
- [ ] File upload works
- [ ] Progress updates correctly
- [ ] Downloads work
- [ ] Errors display properly
- [ ] Mobile responsive
- [ ] Multiple concurrent jobs
- [ ] Long-running jobs complete
- [ ] API returns correct status codes
- [ ] Logs are readable
- [ ] Metrics are being collected

