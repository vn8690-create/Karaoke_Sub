"""Langfuse callback handler preloader for container startup.

Initializes the Langfuse callback handler at container startup to avoid
slow initialization during request processing. The CallbackHandler()
constructor makes blocking network calls to the Langfuse API, which can
take 3+ minutes on Cloud Run cold starts.

IMPORTANT: Langfuse v3 is built on OpenTelemetry. If not configured carefully,
it will install itself as the GLOBAL OpenTelemetry tracer provider, capturing
ALL spans from every library (FastAPI, HTTP clients, etc.) - not just LLM calls.
This caused us to exceed our Langfuse hobby tier monthly event limit with
thousands of "(empty)" HTTP request traces.

The fix: Initialize the Langfuse client with an ISOLATED TracerProvider before
creating the CallbackHandler. This ensures only LangChain/LLM traces are sent
to Langfuse, while other OTEL instrumentation remains separate.

See:
- docs/archive/2026-01-08-performance-investigation.md for background
- https://github.com/orgs/langfuse/discussions/9136 for the OTEL issue
"""

import logging
import os
import time
from typing import Optional, Any

logger = logging.getLogger(__name__)

# Singleton storage for preloaded handler
_preloaded_handler: Optional[Any] = None
_initialization_attempted: bool = False


def preload_langfuse_handler() -> Optional[Any]:
    """Preload Langfuse callback handler at startup.

    Only initializes if LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY
    environment variables are set.

    CRITICAL: We initialize the Langfuse client with an isolated TracerProvider
    BEFORE creating the CallbackHandler. This prevents Langfuse from hijacking
    the global OpenTelemetry provider and capturing all HTTP request spans.

    Returns:
        The preloaded CallbackHandler, or None if not configured
    """
    global _preloaded_handler, _initialization_attempted

    if _initialization_attempted:
        logger.debug("Langfuse initialization already attempted")
        return _preloaded_handler

    _initialization_attempted = True

    # Check if Langfuse is configured
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_HOST", "https://us.cloud.langfuse.com")

    if not (public_key and secret_key):
        logger.info("Langfuse not configured (missing keys), skipping preload")
        return None

    logger.info("Preloading Langfuse callback handler with isolated tracer...")
    start_time = time.time()

    try:
        # Import OpenTelemetry TracerProvider for isolation
        from opentelemetry.sdk.trace import TracerProvider
        from langfuse import Langfuse
        from langfuse.langchain import CallbackHandler

        # CRITICAL: Initialize Langfuse client with an ISOLATED TracerProvider
        # This prevents Langfuse from setting itself as the global OTEL provider,
        # which would cause ALL HTTP requests to be traced (not just LLM calls).
        # See: https://github.com/orgs/langfuse/discussions/9136
        Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
            tracer_provider=TracerProvider(),  # Isolated - won't touch global OTEL
        )
        logger.info("Langfuse client initialized with isolated TracerProvider")

        # Now create the CallbackHandler - it will reuse the existing client
        # instead of creating a new one that hijacks global OTEL
        _preloaded_handler = CallbackHandler()

        elapsed = time.time() - start_time
        logger.info(f"Langfuse handler preloaded in {elapsed:.2f}s (host: {host})")

        return _preloaded_handler

    except ImportError as e:
        logger.warning(f"langfuse or opentelemetry package not installed, skipping preload: {e}")
        return None
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Failed to preload Langfuse handler after {elapsed:.2f}s: {e}")
        # Don't raise - Langfuse is optional
        return None


def get_preloaded_langfuse_handler() -> Optional[Any]:
    """Get the preloaded Langfuse callback handler if available.

    Returns:
        The preloaded CallbackHandler, or None if not preloaded/configured
    """
    return _preloaded_handler


def is_langfuse_preloaded() -> bool:
    """Check if Langfuse handler has been preloaded."""
    return _preloaded_handler is not None


def is_langfuse_configured() -> bool:
    """Check if Langfuse environment variables are configured."""
    return bool(
        os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")
    )


def clear_preloaded_handler() -> None:
    """Clear preloaded handler. Useful for testing."""
    global _preloaded_handler, _initialization_attempted
    _preloaded_handler = None
    _initialization_attempted = False
