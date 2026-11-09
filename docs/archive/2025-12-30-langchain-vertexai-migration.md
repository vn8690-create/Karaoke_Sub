# LangChain Vertex AI Migration Plan

**Date**: 2025-12-30
**Status**: Planned
**Priority**: Medium (deprecation warning, not yet breaking)

## Background

The `ChatVertexAI` class from `langchain-google-vertexai` was deprecated in version 3.2.0 and will be removed in 4.0.0. The recommended replacement is `ChatGoogleGenerativeAI` from the `langchain-google-genai` package.

Deprecation warning observed in logs:
```
LangChainDeprecationWarning: The class `ChatVertexAI` was deprecated in LangChain 3.2.0
and will be removed in 4.0.0. An updated version of the class exists in the
`langchain-google-genai` package and should be used instead.
```

## Current Implementation

**File**: `lyrics_transcriber_temp/lyrics_transcriber/correction/agentic/providers/model_factory.py`

```python
from langchain_google_vertexai import ChatVertexAI

model = ChatVertexAI(
    model=model_name,
    project=config.gcp_project_id,
    location=config.gcp_location,
    timeout=config.request_timeout_seconds,
    max_retries=config.max_retries,
    callbacks=callbacks,
)
```

## Target Implementation

```python
from langchain_google_genai import ChatGoogleGenerativeAI

model = ChatGoogleGenerativeAI(
    model=model_name,
    vertexai=True,  # Keep using Vertex AI authentication
    project=config.gcp_project_id,
    location=config.gcp_location,
    timeout=config.request_timeout_seconds,
    max_retries=config.max_retries,
    callbacks=callbacks,
)
```

## Migration Steps

### 1. Update Dependencies

In `pyproject.toml` (or wherever dependencies are managed):

```toml
# Remove
langchain-google-vertexai = "^x.x.x"

# Add
langchain-google-genai = "^4.0.0"
```

### 2. Update model_factory.py

**File**: `lyrics_transcriber_temp/lyrics_transcriber/correction/agentic/providers/model_factory.py`

```python
# Change import
# Old:
from langchain_google_vertexai import ChatVertexAI

# New:
from langchain_google_genai import ChatGoogleGenerativeAI
```

Update the `_create_vertexai_model` method:

```python
def _create_vertexai_model(
    self, model_name: str, callbacks: List[Any], config: ProviderConfig
) -> Any:
    """Create ChatGoogleGenerativeAI model for Google Gemini via Vertex AI.

    Uses Application Default Credentials (ADC) for authentication.
    In Cloud Run, this uses the service account automatically.
    Locally, run: gcloud auth application-default login
    """
    from langchain_google_genai import ChatGoogleGenerativeAI

    model = ChatGoogleGenerativeAI(
        model=model_name,
        vertexai=True,  # Use Vertex AI backend (not Google AI Studio)
        project=config.gcp_project_id,
        location=config.gcp_location,
        timeout=config.request_timeout_seconds,
        max_retries=config.max_retries,
        callbacks=callbacks,
    )
    logger.debug(f"🤖 Created Vertex AI model: {model_name} (project={config.gcp_project_id})")
    return model
```

### 3. Alternative: Environment Variable Approach

Instead of passing `vertexai=True`, you can set environment variables:

```bash
export GOOGLE_GENAI_USE_VERTEXAI=true
export GOOGLE_CLOUD_PROJECT=your-project-id
export GOOGLE_CLOUD_LOCATION=global  # or us-central1, etc.
```

Then the code simplifies to:

```python
model = ChatGoogleGenerativeAI(
    model=model_name,
    timeout=config.request_timeout_seconds,
    max_retries=config.max_retries,
    callbacks=callbacks,
)
```

## Key Differences

| Aspect | ChatVertexAI (old) | ChatGoogleGenerativeAI (new) |
|--------|-------------------|------------------------------|
| Package | `langchain-google-vertexai` | `langchain-google-genai` |
| Protocol | gRPC | REST |
| Vertex AI Support | Native | Via `vertexai=True` param |
| Auth Methods | ADC, Service Account | Same + API keys |
| Multimodal | Yes | Yes |

## Potential Benefits

1. **REST instead of gRPC**: May resolve the `fork_posix.cc` gRPC warnings we observed:
   ```
   I0000 00:00:1767135828.790289 30025640 fork_posix.cc:71] Other threads are
   currently calling into gRPC, skipping fork() handlers
   ```

2. **Unified SDK**: The `google-genai` SDK is the consolidated approach for all Google AI services.

3. **Future-proof**: Avoids breaking changes when `langchain-google-vertexai` 4.0 removes `ChatVertexAI`.

## Potential Risks

1. **REST vs gRPC latency**: Some users reported slightly slower calls with REST. Monitor LangFuse traces after migration.

2. **Behavior differences**: Test thoroughly to ensure identical behavior for:
   - Multimodal response format handling
   - Timeout behavior
   - Retry logic
   - Error messages

## Testing Plan

1. Run existing agentic correction unit tests
2. Run a full local CLI job with `USE_AGENTIC_AI=1`
3. Compare LangFuse traces before/after for:
   - Response times
   - Success rates
   - Error types
4. Verify Cloud Run deployment works with new package

## References

- [langchain-google-genai 4.0.0 Announcement](https://github.com/langchain-ai/langchain-google/discussions/1422)
- [ChatGoogleGenerativeAI Docs](https://reference.langchain.com/python/integrations/langchain_google_genai/)
- [LangChain Google Releases](https://github.com/langchain-ai/langchain-google/releases)

## Notes

- This migration was identified during investigation of 499 timeout errors in agentic correction (see PR #143)
- The gRPC → REST change might actually help with the connection issues we observed
- Authentication via Vertex AI (ADC/service accounts) is fully supported in the new package
