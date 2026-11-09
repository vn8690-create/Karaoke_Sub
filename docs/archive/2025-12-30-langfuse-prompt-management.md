# LangFuse Prompt Management Integration

**Date**: 2025-12-30
**PR**: https://github.com/nomadkaraoke/karaoke-gen/pull/140

## Summary

Replaced hardcoded LLM prompts in the agentic correction workflow with LangFuse-managed prompts, enabling prompt iteration without redeploying the backend.

## What Changed

### New Components

1. **LangFusePromptService** (`lyrics_transcriber/.../prompts/langfuse_prompts.py`)
   - Fetches prompts from LangFuse with hardcoded fallback for local development
   - Fetches few-shot examples from LangFuse datasets
   - Singleton pattern with fail-fast when LangFuse is configured

2. **Migration Script** (`scripts/migrate-prompts-to-langfuse.py`)
   - Uploads `gap-classifier` prompt template to LangFuse
   - Uploads 9 few-shot examples as `gap-classifier-examples` dataset
   - Supports `--dry-run`, `--force`, `--verify-only` flags

3. **LangFuse Vertex AI Service Account** (Pulumi)
   - `langfuse-vertexai@nomadkaraoke.iam.gserviceaccount.com`
   - Has `roles/aiplatform.user` for calling Gemini models
   - JSON key generated for LangFuse to use GCP credits

### Modified Components

- `langfuse_integration.py` - Added `fetch_prompt()` and `fetch_dataset()` with label fallback
- `classifier.py` - Now uses LangFusePromptService, hardcoded function renamed to `build_classification_prompt_hardcoded`
- Default LangFuse host changed to US region (`https://us.cloud.langfuse.com`)

### Deleted Components

- `handlers/llm.py` - Legacy LLM handler not being used
- `handlers/llm_providers.py` - Legacy provider implementations

## Configuration

### LangFuse Credentials (GCP Secret Manager)

- `langfuse-public-key` - Project: nomadkaraoke
- `langfuse-secret-key` - Project: nomadkaraoke

### Environment Variables

```bash
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://us.cloud.langfuse.com  # Optional, this is the default
```

### LangFuse Resources

- **Prompt**: `gap-classifier` (promote to "production" label for default fetch)
- **Dataset**: `gap-classifier-examples` (9 few-shot examples)
- **Project**: nomadkaraoke at https://us.cloud.langfuse.com

## How Prompt Fetching Works

1. Try to fetch prompt with "production" label (default)
2. If not found, fall back to version 1 (for newly created prompts)
3. If LangFuse not configured, use hardcoded fallback

This allows:
- New prompts to work immediately after upload
- Production prompts to be explicitly promoted
- Local development without LangFuse credentials

## GCP Organization Policy Issue

Creating service account keys was blocked by organization policy `iam.disableServiceAccountKeyCreation`. Solution:

1. Temporarily disable policy at organization level
2. Create key via `gcloud iam service-accounts keys create`
3. Re-enable policy immediately
4. Delete local key file after pasting into LangFuse

This is a one-time operation. The key is now stored in LangFuse, not in any repo or GCP secret.

## Testing

All 676 unit tests pass. The prompt service has dedicated tests in `test_langfuse_prompts.py` that mock the LangFuse client.

## Future Work

- Add more prompts for other agentic workflows
- Set up LangFuse evaluations for prompt quality
- Consider A/B testing different prompt versions
