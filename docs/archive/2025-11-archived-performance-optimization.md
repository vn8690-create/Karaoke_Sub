# Performance Optimization Guide

Optimizations for Cloud Run backend and Cloudflare Pages frontend.

## Cloud Run Optimization

### Container Configuration

Optimize the `Dockerfile`:

```dockerfile
# Use multi-stage build for smaller image
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY backend/requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.11-slim

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Copy from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

WORKDIR /app
COPY backend /app/backend
COPY karaoke_gen /app/karaoke_gen

CMD exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT} --workers 2
```

### Service Configuration

Optimal Cloud Run settings:

```bash
gcloud run deploy karaoke-backend \
  --image gcr.io/$PROJECT_ID/karaoke-backend \
  --region us-central1 \
  --memory 2Gi \
  --cpu 2 \
  --timeout 600 \
  --max-instances 10 \
  --min-instances 1 \
  --concurrency 80 \
  --cpu-throttling \
  --execution-environment gen2 \
  --service-account karaoke-backend@$PROJECT_ID.iam.gserviceaccount.com
```

**Key Settings**:
- `--memory 2Gi`: Sufficient for video processing
- `--cpu 2`: 2 vCPUs for faster processing
- `--min-instances 1`: Keep one instance warm
- `--concurrency 80`: Handle multiple requests per instance
- `--cpu-throttling`: Save costs when idle
- `--execution-environment gen2`: Better performance

### Caching Strategy

Add caching to the backend:

```python
# backend/services/cache_service.py
from functools import lru_cache
import hashlib

class CacheService:
    def __init__(self):
        self.memory_cache = {}
    
    def cache_transcription_result(self, audio_hash: str, result: dict):
        """Cache transcription results by audio hash."""
        # Store in Firestore or Cloud Storage
        pass
    
    @lru_cache(maxsize=100)
    def get_cached_result(self, audio_hash: str):
        """Get cached result if available."""
        pass
```

### Database Connection Pooling

Optimize Firestore connections:

```python
# backend/services/firestore_service.py
from google.cloud import firestore

# Use connection pooling
@lru_cache(maxsize=1)
def get_firestore_client():
    return firestore.Client(project=settings.google_cloud_project)

class FirestoreService:
    def __init__(self):
        self.db = get_firestore_client()
```

## Frontend Optimization

### Code Splitting

Configure Vite for optimal code splitting:

```typescript
// frontend-react/vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom'],
          query: ['@tanstack/react-query'],
          ui: ['zustand', 'axios']
        }
      }
    },
    chunkSizeWarningLimit: 1000
  }
});
```

### Asset Optimization

Optimize images and assets:

```bash
# Install image optimization
npm install --save-dev vite-plugin-imagemin

# Add to vite.config.ts
import viteImagemin from 'vite-plugin-imagemin';

plugins: [
  react(),
  viteImagemin({
    optipng: { optimizationLevel: 7 },
    pngquant: { quality: [0.8, 0.9] },
    mozjpeg: { quality: 80 }
  })
]
```

### Lazy Loading

Implement route-based code splitting:

```typescript
// frontend-react/src/App.tsx
import { lazy, Suspense } from 'react';

const JobSubmission = lazy(() => import('./components/JobSubmission'));
const JobStatus = lazy(() => import('./components/JobStatus'));

function App() {
  return (
    <Suspense fallback={<Loading />}>
      <JobSubmission />
      <JobStatus />
    </Suspense>
  );
}
```

### API Response Caching

Optimize TanStack Query caching:

```typescript
// frontend-react/src/main.tsx
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5000, // 5 seconds
      cacheTime: 300000, // 5 minutes
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});
```

## Cloud Storage Optimization

### Lifecycle Policies

Automatically clean up old files:

```bash
# Create lifecycle policy
cat > lifecycle.json <<EOF
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "Delete"},
        "condition": {"age": 7, "matchesPrefix": ["temp/", "uploads/"]}
      },
      {
        "action": {"type": "SetStorageClass", "storageClass": "NEARLINE"},
        "condition": {"age": 30, "matchesPrefix": ["outputs/"]}
      }
    ]
  }
}
EOF

gsutil lifecycle set lifecycle.json gs://karaoke-gen-storage
```

### Transfer Acceleration

Use signed URLs for faster downloads:

```python
# backend/services/storage_service.py
def generate_signed_url(self, blob_path: str, expiration_minutes: int = 60) -> str:
    blob = self.bucket.blob(blob_path)
    url = blob.generate_signed_url(
        version="v4",
        expiration=timedelta(minutes=expiration_minutes),
        method="GET",
        response_type="application/octet-stream",  # Force download
        response_disposition=f'attachment; filename="{blob_path.split("/")[-1]}"'
    )
    return url
```

## Monitoring and Metrics

### Cloud Monitoring Dashboard

Create custom dashboard:

```bash
# Create monitoring dashboard
cat > dashboard.json <<EOF
{
  "displayName": "Karaoke Generator Dashboard",
  "gridLayout": {
    "widgets": [
      {
        "title": "Request Count",
        "xyChart": {
          "dataSets": [{
            "timeSeriesQuery": {
              "timeSeriesFilter": {
                "filter": "resource.type=\"cloud_run_revision\""
              }
            }
          }]
        }
      }
    ]
  }
}
EOF

gcloud monitoring dashboards create --config-from-file=dashboard.json
```

### Logging Optimization

Structured logging for better analysis:

```python
# backend/main.py
import logging
import json

class StructuredLogger:
    def __init__(self, name):
        self.logger = logging.getLogger(name)
    
    def log(self, level, message, **kwargs):
        log_entry = {
            "message": message,
            "severity": level,
            **kwargs
        }
        self.logger.log(getattr(logging, level), json.dumps(log_entry))

logger = StructuredLogger(__name__)
logger.log("INFO", "Job created", job_id="abc123", status="queued")
```

### Performance Metrics

Track key metrics:

```python
# backend/services/metrics_service.py
from google.cloud import monitoring_v3
import time

class MetricsService:
    def __init__(self):
        self.client = monitoring_v3.MetricServiceClient()
        self.project_name = f"projects/{settings.google_cloud_project}"
    
    def record_processing_time(self, job_id: str, duration: float):
        """Record job processing duration."""
        series = monitoring_v3.TimeSeries()
        series.metric.type = "custom.googleapis.com/karaoke/processing_time"
        series.metric.labels["job_id"] = job_id
        
        point = monitoring_v3.Point()
        point.value.double_value = duration
        point.interval.end_time.seconds = int(time.time())
        
        series.points = [point]
        self.client.create_time_series(
            name=self.project_name,
            time_series=[series]
        )
```

## Cost Optimization

### Cloud Run Cost Reduction

1. **CPU Throttling**: Enable to save costs when idle
2. **Min Instances**: Set to 1 only during peak hours
3. **Request Timeout**: Set appropriately to avoid wasted compute
4. **Memory Allocation**: Right-size based on actual usage

### Storage Cost Reduction

1. **Lifecycle Policies**: Auto-delete old files
2. **Storage Class**: Move old outputs to Nearline/Coldline
3. **Compression**: Compress large files before storage

### Monitoring Costs

Track costs in Cloud Console:

```bash
# View current month costs
gcloud billing accounts list
gcloud billing projects link $PROJECT_ID --billing-account=XXXXX-XXXXX-XXXXX

# Set budget alerts
gcloud billing budgets create \
  --billing-account=XXXXX-XXXXX-XXXXX \
  --display-name="Karaoke Gen Budget" \
  --budget-amount=100 \
  --threshold-rule=percent=50 \
  --threshold-rule=percent=90
```

## Performance Targets

### Backend
- API Response Time: <500ms (p95)
- Job Processing: 5-10 minutes for 4-minute song
- Concurrent Jobs: Support 5+ simultaneous
- Error Rate: <2%
- Uptime: >99.5%

### Frontend
- Initial Load: <2s
- Time to Interactive: <3s
- Lighthouse Score: >90
- Core Web Vitals: All green

### Infrastructure
- Cloud Run Instances: 1-10 (auto-scale)
- Storage Usage: <100GB
- Monthly Cost: <$100

