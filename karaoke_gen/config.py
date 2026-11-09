"""
Configuration utilities for karaoke generation.

This module provides configuration loading and setup functions.
Style loading is delegated to the unified style_loader module.
"""
import os
import sys
import logging

# Import from the unified style loader module
from .style_loader import (
    # Re-export defaults for backwards compatibility
    DEFAULT_STYLE_PARAMS,
    DEFAULT_INTRO_STYLE as _DEFAULT_INTRO,
    DEFAULT_END_STYLE as _DEFAULT_END,
    # Functions
    load_style_params_from_file,
    apply_style_overrides,
    get_intro_format as _get_intro_format,
    get_end_format as _get_end_format,
    get_video_durations,
    get_existing_images,
)


def load_style_params(style_params_json, style_overrides, logger):
    """
    Loads style parameters from a JSON file or uses defaults.
    
    This is the main entry point for the local CLI to load styles.
    
    Args:
        style_params_json: Path to style JSON file, or None for defaults.
        style_overrides: Dict of "section.key" -> value overrides.
        logger: Logger for messages.
    
    Returns:
        Dictionary of style parameters.
    """
    style_params = load_style_params_from_file(
        style_params_json,
        logger=logger,
        exit_on_error=True,
    )
    
    if style_overrides:
        apply_style_overrides(style_params, style_overrides, logger)
    
    return style_params


def setup_title_format(style_params):
    """
    Sets up the title format dictionary from style parameters.
    
    This is a thin wrapper around style_loader.get_intro_format()
    for backwards compatibility.
    """
    return _get_intro_format(style_params)


def setup_end_format(style_params):
    """
    Sets up the end format dictionary from style parameters.
    
    This is a thin wrapper around style_loader.get_end_format()
    for backwards compatibility.
    """
    return _get_end_format(style_params)


def setup_ffmpeg_command(log_level):
    """Sets up the base ffmpeg command string based on log level."""
    # Path to the Windows PyInstaller frozen bundled ffmpeg.exe, 
    # or the system-installed FFmpeg binary on Mac/Linux
    ffmpeg_path = os.path.join(sys._MEIPASS, "ffmpeg.exe") if getattr(sys, "frozen", False) else "ffmpeg"
    ffmpeg_base_command = f"{ffmpeg_path} -hide_banner -nostats"
    if log_level == logging.DEBUG:
        ffmpeg_base_command += " -loglevel verbose"
    else:
        ffmpeg_base_command += " -loglevel fatal"
    return ffmpeg_base_command
