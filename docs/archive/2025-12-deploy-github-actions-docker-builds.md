# GitHub Actions Docker Builds - Cost Optimization

**Date:** 2025-12-28
**Problem:** Cloud Build costing $100+/month with slow builds
**Solution:** Move Docker builds to GitHub Actions with registry caching

---

## Overview

This document describes the migration from Google Cloud Build to GitHub Actions for Docker image builds. This change eliminates Cloud Build costs while improving build speeds through better caching.

## Cost Comparison

| Approach | Monthly Cost | Build Speed | Caching |
|----------|-------------|-------------|---------|
| **Cloud Build (N1_HIGHCPU_32)** | ~$100+ | 5-15 min | Limited |
| **GitHub Actions + Registry Cache** | **$0** | 2-5 min | Excellent |

### Why Cloud Build Was Expensive

1. **N1_HIGHCPU_32 pricing**: ~$0.064/build-minute (21x more than default)
2. **No persistent layer cache**: Each build re-downloaded dependencies
3. **Cold start overhead**: Spinning up build VMs added latency
4. **Large dependency tree**: torch, transformers, etc. = ~500 packages

### Why GitHub Actions Is Free

- **Public repositories**: Unlimited build minutes on GitHub-hosted runners
- **Registry cache**: Layers cached in Artifact Registry, persist between builds
- **BuildKit mode=max**: Caches ALL intermediate layers, not just final

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    NEW BUILD PIPELINE                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   GitHub Actions (Free)                                                │
│   ├── docker/setup-buildx-action (BuildKit)                            │
│   ├── google-github-actions/auth (Workload Identity)                   │
│   └── docker/build-push-action                                         │
│       ├── cache-from: type=registry,ref=...karaoke-backend:cache       │
│       └── cache-to: type=registry,ref=...karaoke-backend:cache,mode=max│
│                                                                         │
│   Artifact Registry                                                    │
│   ├── karaoke-backend:latest         (production image)               │
│   ├── karaoke-backend:cache          (build cache - ALL layers)       │
│   ├── karaoke-backend-base:latest    (base image with deps)           │
│   └── karaoke-backend-base:cache     (base cache)                     │
│                                                                         │
│   Build Times (Expected):                                              │
│   ├── First build (cold): ~8-10 min                                   │
│   ├── Code-only changes: ~2-3 min (cache hit)                         │
│   └── Dependency changes: ~6-8 min (partial cache hit)                │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## How It Works

### Two-Stage Build Pattern

We maintain the existing two-stage build pattern for efficiency:

1. **Base Image** (`karaoke-backend-base`)
   - Contains Python 3.11, ffmpeg, system dependencies
   - All pip dependencies pre-installed
   - Only rebuilt when `poetry.lock` or `Dockerfile.base` changes
   - Hash-based change detection via image labels

2. **App Image** (`karaoke-backend`)
   - Built FROM the base image
   - Contains only application code
   - Fast rebuilds (~2 min) for code-only changes

### Registry Cache

The key optimization is using Artifact Registry as a persistent layer cache:

```yaml
- uses: docker/build-push-action@v6
  with:
    cache-from: type=registry,ref=.../karaoke-backend:cache
    cache-to: type=registry,ref=.../karaoke-backend:cache,mode=max
```

**Benefits:**
- `mode=max` caches ALL layers, not just the final image
- Cache persists between CI runs (unlike GitHub Actions cache which has 10GB limit)
- Layers only re-built when inputs change

---

## Files Changed

### New Files

- **`.dockerignore`** - Reduces build context from ~1GB to ~10MB

### Modified Files

- **`.github/workflows/ci.yml`** - `deploy-backend` job rewritten to use:
  - `docker/setup-buildx-action@v3`
  - `docker/build-push-action@v6`
  - Registry caching to Artifact Registry

### Kept (as fallback)

- **`cloudbuild.yaml`** - Still works for manual triggers
- **`cloudbuild-base.yaml`** - Still works for manual base image builds

---

## Manual Builds (Fallback)

If GitHub Actions fails, you can still use Cloud Build:

```bash
# Build base image (only if dependencies changed)
gcloud builds submit --config=cloudbuild-base.yaml --project=nomadkaraoke

# Build and deploy app image
gcloud builds submit --config=cloudbuild.yaml --project=nomadkaraoke
```

---

## Monitoring

### Check Build Cache Usage

View cache images in Artifact Registry:

```bash
gcloud artifacts docker images list \
  us-central1-docker.pkg.dev/nomadkaraoke/karaoke-repo \
  --include-tags
```

You should see `*:cache` tags for both base and app images.

### Compare Build Times

- **GitHub Actions**: Check workflow run times in Actions tab
- **Previous Cloud Build**: ~5-15 min per build
- **Expected with cache**: ~2-3 min for code changes

---

## Troubleshooting

### Cache Miss (Slow Build)

If builds are slow despite no dependency changes:

1. Check if cache image exists:
   ```bash
   docker pull us-central1-docker.pkg.dev/nomadkaraoke/karaoke-repo/karaoke-backend:cache
   ```

2. Force cache rebuild by pushing to `main` with a small change

### Disk Space Issues

GitHub Actions runners have limited disk. If base image builds fail:

1. The workflow includes `jlumbroso/free-disk-space` action
2. It removes Android SDK, Haskell, .NET, etc. to free ~20GB

### Authentication Issues

If `docker push` fails with permission errors:

1. Check Workload Identity is configured correctly
2. Verify service account has `roles/artifactregistry.writer`

---

## Future Improvements

1. **Parallel base/app builds**: If base is unchanged, start app build immediately
2. **GitHub Actions cache fallback**: Use GHA cache when registry is slow
3. **Build metrics**: Track build times and cache hit rates

---

## References

- [Docker Build with GitHub Actions](https://docs.docker.com/build/ci/github-actions/)
- [Registry Cache Backend](https://docs.docker.com/build/cache/backends/registry/)
- [Cache Management](https://docs.docker.com/build/ci/github-actions/cache/)
