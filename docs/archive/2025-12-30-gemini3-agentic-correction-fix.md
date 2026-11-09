# Gemini 3 Flash Agentic Correction Fix

**Date**: 2025-12-30
**PR**: #137

## Problem

Karaoke jobs were hanging at the agentic correction stage with no visible errors in Langfuse traces. Cloud Run logs showed:

```
404 Publisher Model `projects/nomadkaraoke/locations/us-central1/publishers/google/models/gemini-3-flash-preview` was not found
```

## Root Cause

**Gemini 3 models require the `global` location**, not regional endpoints like `us-central1`. This is different from Gemini 2 models which work with regional endpoints.

Additionally, Gemini 3 returns a **multimodal response format** instead of plain strings:
```python
# Gemini 2 response.content:
"some text response"

# Gemini 3 response.content:
[{'type': 'text', 'text': 'some text response'}]
```

## Solution

1. Changed default `gcp_location` from `us-central1` to `global` in `config.py`
2. Added multimodal response parsing in `langchain_bridge.py`:
   ```python
   if isinstance(content, list):
       for part in content:
           if isinstance(part, dict) and part.get('type') == 'text':
               return part.get('text', '')
   ```

## Files Changed

- `lyrics_transcriber_temp/lyrics_transcriber/correction/agentic/providers/config.py` - Default location
- `lyrics_transcriber_temp/lyrics_transcriber/correction/agentic/providers/langchain_bridge.py` - Response parsing
- `lyrics_transcriber_temp/lyrics_transcriber/correction/agentic/router.py` - Model name comment

## Testing

Created `scripts/test_agentic_correction.py` for local testing without Cloud Run deployment:
```bash
GOOGLE_CLOUD_PROJECT=nomadkaraoke python scripts/test_agentic_correction.py
```

Four test cases covering sound-alike errors, punctuation, extra words, and no-error scenarios all pass.

## Key Learnings

1. **Gemini 3 requires global location** - Not documented prominently; discovered via error message
2. **Model response formats differ between versions** - Always handle both string and list content types
3. **Local test scripts are essential** - Enabled rapid iteration without Cloud Run deploy cycles
4. **Clear LLM cache when debugging** - Cached broken responses can mask fixes: `rm -rf ~/lyrics-transcriber-cache/*.json`
