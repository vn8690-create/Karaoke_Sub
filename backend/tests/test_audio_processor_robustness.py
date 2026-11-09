"""
Tests for audio processor robustness fixes.

Covers:
- Stage 2 validation catches missing stems
- _normalize_audio_files handles missing clean instrumental path
- _generate_combined_instrumentals handles missing backing vocals path
"""
import pytest
from unittest.mock import MagicMock, patch

from karaoke_gen.audio_processor import AudioProcessor


def _make_processor():
    """Create an AudioProcessor with mocked dependencies."""
    processor = AudioProcessor.__new__(AudioProcessor)
    processor.logger = MagicMock()
    processor.clean_instrumental_model = "model_bs_roformer"
    processor.backing_vocals_models = ["mel_band_roformer_karaoke"]
    processor.other_stems_models = []
    processor.lossless_output_format = "FLAC"
    processor.ffmpeg_base_command = "ffmpeg -y"
    return processor


class TestNormalizeAudioFilesNullSafety:
    """Tests for _normalize_audio_files defensive checks."""

    def test_raises_on_missing_clean_instrumental(self):
        processor = _make_processor()
        separation_result = {
            "clean_instrumental": {},  # missing "instrumental" key
            "combined_instrumentals": {},
        }
        with pytest.raises(ValueError, match="clean instrumental path is missing"):
            processor._normalize_audio_files(separation_result, "Artist - Title", "/tmp/output")

    def test_raises_on_none_clean_instrumental(self):
        processor = _make_processor()
        separation_result = {
            "clean_instrumental": {"instrumental": None},
            "combined_instrumentals": {},
        }
        with pytest.raises(ValueError, match="clean instrumental path is missing"):
            processor._normalize_audio_files(separation_result, "Artist - Title", "/tmp/output")

    def test_works_with_valid_path(self, tmp_path):
        processor = _make_processor()
        # Create a real file so _file_exists returns True
        audio_file = tmp_path / "instrumental.flac"
        audio_file.write_bytes(b"fake audio data")

        separation_result = {
            "clean_instrumental": {"instrumental": str(audio_file), "vocals": str(tmp_path / "vocals.flac")},
            "combined_instrumentals": {},
            "other_stems": {},
            "backing_vocals": {},
        }
        # Mock _normalize_audio to avoid actually running ffmpeg
        with patch.object(processor, "_normalize_audio"):
            processor._normalize_audio_files(separation_result, "Artist - Title", str(tmp_path))

        # Should have logged success (no exception)
        assert processor.logger.info.called

    def test_normalizes_combined_instrumentals(self, tmp_path):
        processor = _make_processor()
        instrumental = tmp_path / "instrumental.flac"
        instrumental.write_bytes(b"fake instrumental")
        combined = tmp_path / "combined.flac"
        combined.write_bytes(b"fake combined")

        separation_result = {
            "clean_instrumental": {"instrumental": str(instrumental), "vocals": str(tmp_path / "v.flac")},
            "combined_instrumentals": {"mel_band_roformer_karaoke": str(combined)},
        }
        with patch.object(processor, "_normalize_audio") as mock_normalize:
            processor._normalize_audio_files(separation_result, "Artist - Title", str(tmp_path))

        # Both clean instrumental and combined instrumental should be normalized
        assert mock_normalize.call_count == 2
        normalized_paths = [call.args[0] for call in mock_normalize.call_args_list]
        assert str(instrumental) in normalized_paths
        assert str(combined) in normalized_paths


class TestGenerateCombinedInstrumentalsNullSafety:
    """Tests for _generate_combined_instrumentals defensive checks."""

    def test_skips_model_with_missing_backing_vocals(self, tmp_path):
        processor = _make_processor()
        instrumental_path = str(tmp_path / "instrumental.flac")

        # Model has lead_vocals but not backing_vocals
        backing_vocals_result = {
            "mel_band_roformer_karaoke": {"lead_vocals": "/tmp/lead.flac"}
            # "backing_vocals" key is missing
        }
        result = processor._generate_combined_instrumentals(
            instrumental_path, backing_vocals_result, "Artist - Title", str(tmp_path)
        )
        assert result == {}
        processor.logger.error.assert_called_once()
        assert "backing_vocals path is missing" in processor.logger.error.call_args[0][0]


class TestStage2Validation:
    """Tests for stage 2 remote results validation in _process_audio_separation_remote."""

    def test_organize_stage2_missing_backing_vocals_stem(self):
        """Test that _organize_stage2_remote_results correctly handles partial results."""
        processor = _make_processor()

        # Simulate only getting the Vocals file, not the Instrumental file
        # This is what happened in the production failure
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmpdir:
            stems_dir = os.path.join(tmpdir, "stems")
            os.makedirs(stems_dir)

            # Create only the vocals file (missing the instrumental/backing vocals file)
            vocals_file = os.path.join(tmpdir, "audio_(Vocals)_mel_band_roformer_karaoke.flac")
            with open(vocals_file, "w") as f:
                f.write("fake")

            result = processor._organize_stage2_remote_results(
                [vocals_file], "Artist - Title", stems_dir
            )

            # Should have the model with only lead_vocals, no backing_vocals
            assert "mel_band_roformer_karaoke" in result
            assert "lead_vocals" in result["mel_band_roformer_karaoke"]
            assert "backing_vocals" not in result["mel_band_roformer_karaoke"]
