"""NLTK resource preloader for container startup.

Loads NLTK data at container startup to avoid slow downloads during request processing.
Cloud Run's ephemeral filesystem means NLTK data must be re-downloaded on each cold start,
which can take 30-100+ seconds for cmudict.

See docs/archive/2026-01-08-performance-investigation.md for background.
"""

import logging
import time
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Singleton storage for preloaded resources
_preloaded_resources: Dict[str, Any] = {}


def preload_nltk_cmudict() -> None:
    """Preload NLTK's CMU Pronouncing Dictionary at startup.

    The cmudict is used by SyllablesMatchHandler for syllable counting.
    Without preloading, each SyllablesMatchHandler init downloads ~30MB,
    which took 50-100+ seconds in Cloud Run.
    """
    global _preloaded_resources

    if "cmudict" in _preloaded_resources:
        logger.info("NLTK cmudict already preloaded")
        return

    logger.info("Preloading NLTK cmudict...")
    start_time = time.time()

    try:
        import nltk

        # Ensure the data is downloaded
        try:
            from nltk.corpus import cmudict

            # Try to access it - will raise LookupError if not downloaded
            _ = cmudict.dict()
        except LookupError:
            logger.info("Downloading NLTK cmudict data...")
            nltk.download("cmudict", quiet=True)
            from nltk.corpus import cmudict

        # Load into memory
        cmu_dict = cmudict.dict()
        _preloaded_resources["cmudict"] = cmu_dict

        elapsed = time.time() - start_time
        logger.info(f"NLTK cmudict preloaded in {elapsed:.2f}s ({len(cmu_dict)} entries)")

    except Exception as e:
        logger.error(f"Failed to preload NLTK cmudict: {e}")
        raise


def get_preloaded_cmudict() -> Optional[Dict]:
    """Get the preloaded CMU dictionary if available.

    Returns:
        The preloaded cmudict dictionary, or None if not preloaded
    """
    return _preloaded_resources.get("cmudict")


def is_cmudict_preloaded() -> bool:
    """Check if cmudict has been preloaded."""
    return "cmudict" in _preloaded_resources


def preload_nltk_punkt() -> None:
    """Preload NLTK's punkt tokenizer (optional, used for sentence tokenization)."""
    global _preloaded_resources

    if "punkt" in _preloaded_resources:
        logger.info("NLTK punkt already preloaded")
        return

    logger.info("Preloading NLTK punkt tokenizer...")
    start_time = time.time()

    try:
        import nltk

        try:
            from nltk.tokenize import word_tokenize

            # Test it works
            _ = word_tokenize("test")
        except LookupError:
            logger.info("Downloading NLTK punkt data...")
            nltk.download("punkt", quiet=True)
            nltk.download("punkt_tab", quiet=True)

        _preloaded_resources["punkt"] = True

        elapsed = time.time() - start_time
        logger.info(f"NLTK punkt preloaded in {elapsed:.2f}s")

    except Exception as e:
        logger.warning(f"Failed to preload NLTK punkt (non-critical): {e}")


def preload_all_nltk_resources() -> None:
    """Preload all NLTK resources used by the application."""
    preload_nltk_cmudict()
    # punkt is optional and less critical
    try:
        preload_nltk_punkt()
    except Exception:
        pass  # Non-critical


def clear_preloaded_resources() -> None:
    """Clear all preloaded resources. Useful for testing."""
    global _preloaded_resources
    _preloaded_resources.clear()
