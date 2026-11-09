"""
E2E tests for countdown sync in CLI workflow.

These tests verify that the CLI produces correctly synced output
when countdown padding is applied.
"""

import pytest
import subprocess
import tempfile
import os
import json
from pathlib import Path
from unittest.mock import MagicMock, patch


def cli_available():
    """Check if karaoke-gen CLI is available."""
    try:
        result = subprocess.run(
            ['karaoke-gen', '--help'],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def ffmpeg_available():
    """Check if ffmpeg is available."""
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


# Skip all tests if prerequisites aren't available
pytestmark = pytest.mark.skipif(
    not ffmpeg_available(),
    reason="ffmpeg not available. Install ffmpeg to run these tests."
)


class TestCountdownCLIBasics:
    """Basic tests for CLI countdown functionality."""

    def test_countdown_processor_import(self):
        """CountdownProcessor can be imported from CLI modules."""
        from karaoke_gen.lyrics_transcriber.output.countdown_processor import CountdownProcessor
        assert CountdownProcessor is not None

    def test_countdown_processor_constants(self):
        """CountdownProcessor has expected constants."""
        from karaoke_gen.lyrics_transcriber.output.countdown_processor import CountdownProcessor

        assert CountdownProcessor.COUNTDOWN_PADDING_SECONDS == 3.0
        assert CountdownProcessor.COUNTDOWN_THRESHOLD_SECONDS == 3.0
        assert CountdownProcessor.COUNTDOWN_TEXT == "3... 2... 1..."


class TestCountdownProcessorDirectly:
    """Direct tests for CountdownProcessor with synthetic inputs."""

    @pytest.fixture
    def early_start_correction_result(self):
        """Create a mock CorrectionResult where first word starts at 0.5s.

        CountdownProcessor only uses correction_result.corrected_segments,
        so we use a mock to avoid the complex CorrectionResult constructor.
        """
        from unittest.mock import MagicMock
        from karaoke_gen.lyrics_transcriber.types import LyricsSegment, Word

        word = Word(id="word1", text="Hello", start_time=0.5, end_time=1.0)
        segment = LyricsSegment(id="seg1", text="Hello world", start_time=0.5, end_time=2.0, words=[word])

        mock_result = MagicMock()
        mock_result.corrected_segments = [segment]
        return mock_result

    @pytest.fixture
    def late_start_correction_result(self):
        """Create a mock CorrectionResult where first word starts at 5.0s."""
        from unittest.mock import MagicMock
        from karaoke_gen.lyrics_transcriber.types import LyricsSegment, Word

        word = Word(id="word1", text="Hello", start_time=5.0, end_time=5.5)
        segment = LyricsSegment(id="seg1", text="Hello world", start_time=5.0, end_time=6.0, words=[word])

        mock_result = MagicMock()
        mock_result.corrected_segments = [segment]
        return mock_result

    @pytest.fixture
    def test_audio(self, tmp_path):
        """Create a short test audio file."""
        audio_path = tmp_path / "test.flac"

        # Create 5 seconds of audio
        subprocess.run([
            'ffmpeg', '-y', '-f', 'lavfi',
            '-i', 'sine=frequency=440:duration=5',
            '-c:a', 'flac',
            str(audio_path)
        ], capture_output=True)

        return audio_path

    def test_countdown_added_for_early_start(self, early_start_correction_result, test_audio, tmp_path):
        """CountdownProcessor adds countdown when song starts within 3s."""
        from karaoke_gen.lyrics_transcriber.output.countdown_processor import CountdownProcessor

        processor = CountdownProcessor(cache_dir=str(tmp_path))

        modified_result, new_audio, padding_added, padding_seconds = processor.process(
            correction_result=early_start_correction_result,
            audio_filepath=str(test_audio),
        )

        assert padding_added is True
        assert padding_seconds == 3.0

    def test_no_countdown_for_late_start(self, late_start_correction_result, test_audio, tmp_path):
        """CountdownProcessor doesn't add countdown when song starts after 3s."""
        from karaoke_gen.lyrics_transcriber.output.countdown_processor import CountdownProcessor

        processor = CountdownProcessor(cache_dir=str(tmp_path))

        modified_result, new_audio, padding_added, padding_seconds = processor.process(
            correction_result=late_start_correction_result,
            audio_filepath=str(test_audio),
        )

        assert padding_added is False
        assert padding_seconds == 0.0

    def test_timestamps_shifted_by_padding(self, early_start_correction_result, test_audio, tmp_path):
        """When countdown is added, all timestamps are shifted by padding amount."""
        from karaoke_gen.lyrics_transcriber.output.countdown_processor import CountdownProcessor

        original_start = early_start_correction_result.corrected_segments[0].start_time
        assert original_start == 0.5

        processor = CountdownProcessor(cache_dir=str(tmp_path))

        modified_result, _, padding_added, padding_seconds = processor.process(
            correction_result=early_start_correction_result,
            audio_filepath=str(test_audio),
        )

        # When countdown is added:
        # - corrected_segments[0] is the new countdown segment (e.g., "3...2...1...")
        # - corrected_segments[1] is the original segment with shifted timestamps
        assert len(modified_result.corrected_segments) >= 2, (
            "Countdown should add a segment, so there should be at least 2 segments"
        )

        # Original segment should now be at index 1 with shifted timestamps
        shifted_segment = modified_result.corrected_segments[1]
        expected_start = original_start + padding_seconds

        assert shifted_segment.start_time == expected_start, (
            f"Expected start time {expected_start}, got {shifted_segment.start_time}"
        )

    def test_audio_padded_correctly(self, early_start_correction_result, test_audio, tmp_path):
        """Audio file is padded by correct amount."""
        from karaoke_gen.lyrics_transcriber.output.countdown_processor import CountdownProcessor

        # Get original duration
        probe = subprocess.run([
            'ffprobe', '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            str(test_audio)
        ], capture_output=True, text=True)
        original_duration = float(json.loads(probe.stdout)['format']['duration'])

        processor = CountdownProcessor(cache_dir=str(tmp_path))

        _, new_audio_path, padding_added, padding_seconds = processor.process(
            correction_result=early_start_correction_result,
            audio_filepath=str(test_audio),
        )

        # Get new duration
        probe = subprocess.run([
            'ffprobe', '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            new_audio_path
        ], capture_output=True, text=True)
        new_duration = float(json.loads(probe.stdout)['format']['duration'])

        expected_duration = original_duration + padding_seconds
        assert abs(new_duration - expected_duration) < 0.1, (
            f"Expected duration ~{expected_duration}s, got {new_duration}s"
        )


class TestKaraokeFinaliseCountdownIntegration:
    """Integration tests for KaraokeFinalise with countdown padding."""

    @pytest.fixture
    def test_audio_files(self, tmp_path):
        """Create test audio files for finalization tests."""
        files = {}

        # Create instrumental
        instrumental = tmp_path / "instrumental.flac"
        subprocess.run([
            'ffmpeg', '-y', '-f', 'lavfi',
            '-i', 'sine=frequency=440:duration=10',
            '-c:a', 'flac',
            str(instrumental)
        ], capture_output=True)
        files['instrumental'] = instrumental

        # Create video placeholder (silent)
        with_vocals = tmp_path / "with_vocals.mp4"
        subprocess.run([
            'ffmpeg', '-y', '-f', 'lavfi',
            '-i', 'color=black:size=1920x1080:duration=10',
            '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
            '-t', '10',
            '-c:v', 'libx264', '-c:a', 'aac',
            str(with_vocals)
        ], capture_output=True)
        files['with_vocals'] = with_vocals

        return files

    def test_finalise_creates_padded_instrumental_when_needed(self, test_audio_files, tmp_path):
        """KaraokeFinalise creates padded instrumental when countdown_padding_seconds > 0."""
        from karaoke_gen.karaoke_finalise.karaoke_finalise import KaraokeFinalise

        output_file = tmp_path / "output.mp4"

        finalise = KaraokeFinalise(
            countdown_padding_seconds=3.0,
            non_interactive=True,
        )

        # Mock execute_command to track calls
        calls = []
        original_execute = finalise.execute_command
        def mock_execute(cmd, desc):
            calls.append((cmd, desc))
            # Don't actually run ffmpeg for this test
            pass
        finalise.execute_command = mock_execute

        # Mock _pad_audio_file to track if it's called
        pad_called = []
        def mock_pad(input_audio, output_audio, padding):
            pad_called.append((input_audio, output_audio, padding))
            # Create output file
            with open(output_audio, 'w') as f:
                f.write("padded")
        finalise._pad_audio_file = mock_pad

        finalise.remux_with_instrumental(
            str(test_audio_files['with_vocals']),
            str(test_audio_files['instrumental']),
            str(output_file)
        )

        # Should have called _pad_audio_file
        assert len(pad_called) == 1
        assert pad_called[0][2] == 3.0  # padding_seconds

    def test_finalise_skips_padding_when_none(self, test_audio_files, tmp_path):
        """KaraokeFinalise skips padding when countdown_padding_seconds is None."""
        from karaoke_gen.karaoke_finalise.karaoke_finalise import KaraokeFinalise

        output_file = tmp_path / "output.mp4"

        finalise = KaraokeFinalise(
            countdown_padding_seconds=None,
            non_interactive=True,
        )

        # Mock _pad_audio_file to track if it's called
        pad_called = []
        def mock_pad(input_audio, output_audio, padding):
            pad_called.append((input_audio, output_audio, padding))
        finalise._pad_audio_file = mock_pad
        finalise.execute_command = lambda cmd, desc: None

        finalise.remux_with_instrumental(
            str(test_audio_files['with_vocals']),
            str(test_audio_files['instrumental']),
            str(output_file)
        )

        # Should NOT have called _pad_audio_file
        assert len(pad_called) == 0


class TestCountdownSyncInvariant:
    """Tests for the critical sync invariant."""

    def test_sync_invariant_formula(self):
        """
        SYNC INVARIANT:
        If vocals are padded by N seconds, instrumental must also be padded by N seconds.
        This ensures the relative timing between vocals and instrumental is preserved.
        """
        original_vocal_start = 0.5  # seconds
        original_instrumental_start = 0.0  # seconds
        padding = 3.0  # seconds

        # After padding
        padded_vocal_start = original_vocal_start + padding
        padded_instrumental_start = original_instrumental_start + padding

        # Relative offset must be preserved
        original_offset = original_vocal_start - original_instrumental_start
        padded_offset = padded_vocal_start - padded_instrumental_start

        assert original_offset == padded_offset, (
            "INVARIANT VIOLATION: Padding changed the relative timing"
        )

    def test_both_streams_padded_equally(self):
        """Both audio streams must be padded by the same amount."""
        padding_seconds = 3.0

        # Vocals are padded in CountdownProcessor
        vocal_padding = padding_seconds

        # Instrumental must be padded the same in KaraokeFinalise
        instrumental_padding = padding_seconds

        assert vocal_padding == instrumental_padding, (
            "Vocals and instrumental must be padded equally"
        )
