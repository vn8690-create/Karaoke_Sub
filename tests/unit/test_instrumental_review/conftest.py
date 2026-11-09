"""
Test fixtures for instrumental_review tests.

This module provides pytest fixtures that generate test audio files
programmatically using pydub. This avoids the need for static test
audio files in the repository.
"""

import os
import math
import tempfile
from pathlib import Path
from typing import Generator

import pytest
from pydub import AudioSegment
from pydub.generators import Sine, WhiteNoise


@pytest.fixture
def temp_dir() -> Generator[str, None, None]:
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def silent_audio_path(temp_dir: str) -> str:
    """
    Create a silent audio file (10 seconds).
    
    This represents backing vocals with no audible content.
    """
    duration_ms = 10000  # 10 seconds
    
    # Create silent audio
    audio = AudioSegment.silent(duration=duration_ms, frame_rate=44100)
    
    # Save to file
    output_path = os.path.join(temp_dir, "silent_backing_vocals.flac")
    audio.export(output_path, format="flac")
    
    return output_path


@pytest.fixture
def loud_audio_path(temp_dir: str) -> str:
    """
    Create an audio file with consistent audible content (10 seconds).
    
    This represents backing vocals with clear, continuous content.
    """
    duration_ms = 10000  # 10 seconds
    
    # Create a sine wave tone
    tone = Sine(440).to_audio_segment(duration=duration_ms)
    
    # Reduce volume to -10dB
    tone = tone - 10
    
    # Save to file
    output_path = os.path.join(temp_dir, "loud_backing_vocals.flac")
    tone.export(output_path, format="flac")
    
    return output_path


@pytest.fixture
def mixed_audio_path(temp_dir: str) -> str:
    """
    Create an audio file with alternating silent and audible sections.
    
    Pattern: 2s silent, 3s audible, 2s silent, 3s audible = 10s total
    
    This represents backing vocals with some good sections and some
    sections that might need muting.
    """
    # Create segments
    silence1 = AudioSegment.silent(duration=2000, frame_rate=44100)  # 2s
    tone1 = Sine(440).to_audio_segment(duration=3000) - 15  # 3s at -15dB
    silence2 = AudioSegment.silent(duration=2000, frame_rate=44100)  # 2s
    tone2 = Sine(880).to_audio_segment(duration=3000) - 15  # 3s at -15dB
    
    # Combine
    audio = silence1 + tone1 + silence2 + tone2
    
    # Save to file
    output_path = os.path.join(temp_dir, "mixed_backing_vocals.flac")
    audio.export(output_path, format="flac")
    
    return output_path


@pytest.fixture
def quiet_audio_path(temp_dir: str) -> str:
    """
    Create an audio file with very quiet content (below -40dB threshold).
    
    This represents backing vocals that technically have content but
    are quiet enough to be considered silent.
    """
    duration_ms = 10000  # 10 seconds
    
    # Create a very quiet sine wave (-50dB)
    tone = Sine(440).to_audio_segment(duration=duration_ms)
    tone = tone - 50  # Very quiet
    
    # Save to file
    output_path = os.path.join(temp_dir, "quiet_backing_vocals.flac")
    tone.export(output_path, format="flac")
    
    return output_path


@pytest.fixture
def clean_instrumental_path(temp_dir: str) -> str:
    """
    Create a clean instrumental audio file.
    
    This is used for testing the audio editor.
    """
    duration_ms = 10000  # 10 seconds
    
    # Create a chord-like sound (multiple frequencies)
    tone1 = Sine(220).to_audio_segment(duration=duration_ms) - 12  # A
    tone2 = Sine(277).to_audio_segment(duration=duration_ms) - 12  # C#
    tone3 = Sine(330).to_audio_segment(duration=duration_ms) - 12  # E
    
    # Mix the tones
    chord = tone1.overlay(tone2).overlay(tone3)
    
    # Save to file
    output_path = os.path.join(temp_dir, "clean_instrumental.flac")
    chord.export(output_path, format="flac")
    
    return output_path


@pytest.fixture
def backing_vocals_with_issues_path(temp_dir: str) -> str:
    """
    Create backing vocals with some sections that should be muted.
    
    Pattern: 
    - 0-3s: Good backing vocals (harmonies)
    - 3-5s: Bad section (lead vocal bleed - louder)
    - 5-8s: Good backing vocals
    - 8-10s: Bad section (artifacts)
    """
    # Good section 1: Quiet harmonies
    good1 = Sine(330).to_audio_segment(duration=3000) - 20  # 3s at -20dB
    
    # Bad section 1: Loud lead vocal bleed
    bad1 = Sine(440).to_audio_segment(duration=2000) - 5  # 2s at -5dB (loud)
    
    # Good section 2: Quiet harmonies
    good2 = Sine(392).to_audio_segment(duration=3000) - 20  # 3s at -20dB
    
    # Bad section 2: Artifacts (noise-like)
    bad2 = WhiteNoise().to_audio_segment(duration=2000) - 15  # 2s at -15dB
    
    # Combine
    audio = good1 + bad1 + good2 + bad2
    
    # Save to file
    output_path = os.path.join(temp_dir, "backing_vocals_with_issues.flac")
    audio.export(output_path, format="flac")
    
    return output_path


@pytest.fixture
def stereo_audio_path(temp_dir: str) -> str:
    """
    Create a stereo audio file for testing channel handling.
    """
    duration_ms = 5000  # 5 seconds
    
    # Create stereo audio
    left = Sine(440).to_audio_segment(duration=duration_ms) - 15
    right = Sine(550).to_audio_segment(duration=duration_ms) - 15
    
    stereo = AudioSegment.from_mono_audiosegments(left, right)
    
    # Save to file
    output_path = os.path.join(temp_dir, "stereo_backing_vocals.flac")
    stereo.export(output_path, format="flac")
    
    return output_path
