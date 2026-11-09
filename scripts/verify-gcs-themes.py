#!/usr/bin/env python3
"""Verify all GCS themes are complete."""
import sys
import logging
from pathlib import Path

# Add parent directory to path so we can import backend modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.theme_service import ThemeService
from karaoke_gen.style_loader import validate_theme_completeness

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Verify all themes in GCS are complete."""
    theme_service = ThemeService()
    themes = theme_service.list_themes()

    logger.info(f"Checking {len(themes)} themes...")
    logger.info("")

    incomplete = []

    for theme_summary in themes:
        theme = theme_service.get_theme(theme_summary.id)
        if not theme:
            logger.error(f"✗ {theme_summary.id}: Failed to load")
            incomplete.append(theme_summary.id)
            continue

        is_complete, missing = validate_theme_completeness(theme.style_params)
        if is_complete:
            logger.info(f"✓ {theme_summary.id}: Complete")
        else:
            logger.error(f"✗ {theme_summary.id}: Missing {missing}")
            incomplete.append(theme_summary.id)

    logger.info("")
    if incomplete:
        logger.error(f"FAILED: {len(incomplete)} incomplete themes")
        logger.error(f"Incomplete themes: {', '.join(incomplete)}")
        return 1
    else:
        logger.info(f"SUCCESS: All {len(themes)} themes are complete")
        return 0


if __name__ == "__main__":
    sys.exit(main())
