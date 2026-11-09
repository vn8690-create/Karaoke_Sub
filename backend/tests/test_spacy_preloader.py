"""Tests for SpaCy preloader service."""

import pytest
from unittest.mock import patch, MagicMock

from backend.services.spacy_preloader import (
    preload_spacy_model,
    get_preloaded_model,
    is_model_preloaded,
    clear_preloaded_models,
)


class TestSpacyPreloader:
    """Tests for SpaCy preloading functionality."""

    def setup_method(self):
        """Clear preloaded models before each test."""
        clear_preloaded_models()

    def teardown_method(self):
        """Clear preloaded models after each test."""
        clear_preloaded_models()

    def test_preload_spacy_model_loads_and_stores(self):
        """GIVEN no preloaded models
        WHEN preload_spacy_model is called
        THEN model should be loaded and stored in singleton."""
        mock_nlp = MagicMock()

        with patch("spacy.load", return_value=mock_nlp) as mock_load:
            preload_spacy_model("en_core_web_sm")

            mock_load.assert_called_once_with("en_core_web_sm")
            assert is_model_preloaded("en_core_web_sm")
            assert get_preloaded_model("en_core_web_sm") is mock_nlp

    def test_preload_is_idempotent(self):
        """GIVEN a model already preloaded
        WHEN preload_spacy_model is called again
        THEN model should not be reloaded."""
        mock_nlp = MagicMock()

        with patch("spacy.load", return_value=mock_nlp) as mock_load:
            preload_spacy_model("en_core_web_sm")
            preload_spacy_model("en_core_web_sm")  # Second call

            # Should only load once
            assert mock_load.call_count == 1

    def test_get_preloaded_model_returns_none_if_not_loaded(self):
        """GIVEN no preloaded models
        WHEN get_preloaded_model is called
        THEN should return None."""
        assert get_preloaded_model("en_core_web_sm") is None
        assert not is_model_preloaded("en_core_web_sm")

    def test_preload_different_models(self):
        """GIVEN no preloaded models
        WHEN preload_spacy_model is called with different model names
        THEN each model should be loaded and stored separately."""
        mock_nlp_sm = MagicMock(name="en_core_web_sm")
        mock_nlp_md = MagicMock(name="en_core_web_md")

        def mock_load(model_name):
            if model_name == "en_core_web_sm":
                return mock_nlp_sm
            elif model_name == "en_core_web_md":
                return mock_nlp_md
            raise ValueError(f"Unknown model: {model_name}")

        with patch("spacy.load", side_effect=mock_load):
            preload_spacy_model("en_core_web_sm")
            preload_spacy_model("en_core_web_md")

            assert is_model_preloaded("en_core_web_sm")
            assert is_model_preloaded("en_core_web_md")
            assert get_preloaded_model("en_core_web_sm") is mock_nlp_sm
            assert get_preloaded_model("en_core_web_md") is mock_nlp_md

    def test_clear_preloaded_models(self):
        """GIVEN preloaded models
        WHEN clear_preloaded_models is called
        THEN all models should be removed."""
        mock_nlp = MagicMock()

        with patch("spacy.load", return_value=mock_nlp):
            preload_spacy_model("en_core_web_sm")
            assert is_model_preloaded("en_core_web_sm")

            clear_preloaded_models()
            assert not is_model_preloaded("en_core_web_sm")
            assert get_preloaded_model("en_core_web_sm") is None

    def test_preload_failure_raises_exception(self):
        """GIVEN spacy.load raises an exception
        WHEN preload_spacy_model is called
        THEN exception should be propagated."""
        with patch(
            "spacy.load",
            side_effect=OSError("Model not found"),
        ):
            with pytest.raises(OSError, match="Model not found"):
                preload_spacy_model("nonexistent_model")

            # Model should not be marked as preloaded
            assert not is_model_preloaded("nonexistent_model")

    def test_preload_uses_default_model_name(self):
        """GIVEN no model name specified
        WHEN preload_spacy_model is called without arguments
        THEN should use en_core_web_sm as default."""
        mock_nlp = MagicMock()

        with patch("spacy.load", return_value=mock_nlp) as mock_load:
            preload_spacy_model()

            mock_load.assert_called_once_with("en_core_web_sm")
            assert is_model_preloaded("en_core_web_sm")
