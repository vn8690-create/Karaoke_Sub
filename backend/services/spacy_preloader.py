"""SpaCy model preloader for container startup.

Loads SpaCy models at container startup to avoid slow loading during request processing.
Cloud Run filesystem I/O can cause 60+ second delays when loading SpaCy models lazily.
"""

import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Singleton storage for preloaded models
_preloaded_models: dict = {}


def preload_spacy_model(model_name: str = "en_core_web_sm") -> None:
    """Preload a SpaCy model at startup.

    Args:
        model_name: The SpaCy model to load (default: en_core_web_sm)
    """
    global _preloaded_models

    if model_name in _preloaded_models:
        logger.info(f"SpaCy model '{model_name}' already preloaded")
        return

    logger.info(f"Preloading SpaCy model '{model_name}'...")
    start_time = time.time()

    try:
        import spacy

        nlp = spacy.load(model_name)
        _preloaded_models[model_name] = nlp

        elapsed = time.time() - start_time
        logger.info(f"SpaCy model '{model_name}' preloaded in {elapsed:.2f}s")
    except Exception as e:
        logger.error(f"Failed to preload SpaCy model '{model_name}': {e}")
        raise


def get_preloaded_model(model_name: str = "en_core_web_sm") -> Optional[object]:
    """Get a preloaded SpaCy model if available.

    Args:
        model_name: The SpaCy model name

    Returns:
        The preloaded SpaCy Language object, or None if not preloaded
    """
    return _preloaded_models.get(model_name)


def is_model_preloaded(model_name: str = "en_core_web_sm") -> bool:
    """Check if a SpaCy model has been preloaded."""
    return model_name in _preloaded_models


def clear_preloaded_models() -> None:
    """Clear all preloaded models. Useful for testing."""
    global _preloaded_models
    _preloaded_models.clear()
