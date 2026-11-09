# ChatGoogleGenerativeAI Vertex AI Auth Fix

**Date**: 2025-12-31
**PR**: #147
**Related**: PR #145 (LangChain provider migration)

## Background

PR #145 migrated from `ChatVertexAI` (gRPC) to `ChatGoogleGenerativeAI` (REST) to fix silent hangs during model initialization. However, the migration only configured API key authentication, breaking Cloud Run deployments that use service account credentials.

## Problem

After deploying PR #145, Cloud Run lyrics worker failed with:
```
🤖 Failed to initialize chat model: GOOGLE_API_KEY environment variable is required for Google/Gemini models
```

The code required `GOOGLE_API_KEY` even though:
- Cloud Run already has `GOOGLE_CLOUD_PROJECT` set
- Service account credentials are available via ADC (Application Default Credentials)
- Vertex AI IAM permissions were already configured

## Root Cause

`ChatGoogleGenerativeAI` supports TWO authentication backends:

| Backend | Trigger | Auth Method |
|---------|---------|-------------|
| Vertex AI | `project` param set | Service account / ADC |
| Google AI Studio | Only `google_api_key` | API key |

PR #145 only passed `google_api_key`, forcing the Google AI Studio backend which doesn't support service accounts.

## Solution

Pass `project` parameter when `GOOGLE_CLOUD_PROJECT` is set to trigger Vertex AI backend:

```python
# Before (broken)
model = ChatGoogleGenerativeAI(model=model_name, google_api_key=api_key)

# After (works with service account)
model_kwargs = {"model": model_name, ...}
if project:
    model_kwargs["project"] = project  # Triggers Vertex AI backend
if api_key:
    model_kwargs["google_api_key"] = api_key  # Optional fallback
model = ChatGoogleGenerativeAI(**model_kwargs)
```

## Key Insight

`ChatGoogleGenerativeAI` from `langchain-google-genai` is a unified client that supports both Vertex AI and Google AI Studio APIs. The `project` parameter is the key discriminator - when present, it uses Vertex AI with ADC auth.

## Testing

Verified that on Cloud Run with `GOOGLE_CLOUD_PROJECT=nomadkaraoke`:
- No `GOOGLE_API_KEY` required
- Uses attached service account via ADC
- REST API (avoids gRPC hang issues from PR #145)

## Files Changed

- `lyrics_transcriber_temp/.../providers/model_factory.py` - Added project param logic
- `docs/LESSONS-LEARNED.md` - Updated documentation

## Timing Analysis Context

This fix was discovered during a timing analysis comparing local vs remote job performance. Key findings:
- Remote jobs had 38+ minute delays in lyrics worker
- Root cause: gRPC hangs (fixed by PR #145) + auth misconfiguration (fixed by this PR)
- With both fixes, remote processing should match local performance
