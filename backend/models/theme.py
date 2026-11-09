"""
Theme data models for karaoke-gen.

Themes are pre-created style configurations stored in GCS that users can select
when creating karaoke jobs. Each theme includes:
- Style parameters (fonts, colors, backgrounds, layouts)
- Asset files (images, fonts)
- Preview images
- Optional YouTube description template
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ThemeSummary(BaseModel):
    """Summary of a theme for listing purposes."""

    id: str = Field(..., description="Unique theme identifier (e.g., 'nomad', 'default')")
    name: str = Field(..., description="Human-readable theme name")
    description: str = Field(..., description="Brief description of the theme style")
    preview_url: Optional[str] = Field(None, description="Signed URL for preview image")
    thumbnail_url: Optional[str] = Field(None, description="Signed URL for smaller thumbnail")
    is_default: bool = Field(False, description="Whether this is the default theme")


class ThemeMetadata(BaseModel):
    """Metadata for a single theme in the registry."""

    id: str
    name: str
    description: str
    is_default: bool = False
    created_at: Optional[datetime] = None


class ThemeRegistry(BaseModel):
    """Registry of all available themes, stored as _metadata.json in GCS."""

    version: int = 1
    themes: List[ThemeMetadata] = Field(default_factory=list)


class ThemeDetail(BaseModel):
    """Full theme details including style parameters."""

    id: str
    name: str
    description: str
    preview_url: Optional[str] = None
    is_default: bool = False
    style_params: Dict[str, Any] = Field(default_factory=dict)
    has_youtube_description: bool = False


class ColorOverrides(BaseModel):
    """
    User-customizable color overrides that can be applied on top of a theme.

    All colors are hex format (#RRGGBB). When applied:
    - artist_color: Applied to intro.artist_color, end.artist_color, cdg.artist_color
    - title_color: Applied to intro.title_color, end.title_color, cdg.title_color
    - sung_lyrics_color: Applied to karaoke.primary_color (converted to RGBA), cdg.active_fill
    - unsung_lyrics_color: Applied to karaoke.secondary_color (converted to RGBA), cdg.inactive_fill
    """

    artist_color: Optional[str] = Field(
        None,
        pattern=r"^#[0-9A-Fa-f]{6}$",
        description="Hex color for artist name on intro/end screens",
    )
    title_color: Optional[str] = Field(
        None,
        pattern=r"^#[0-9A-Fa-f]{6}$",
        description="Hex color for song title on intro/end screens",
    )
    sung_lyrics_color: Optional[str] = Field(
        None,
        pattern=r"^#[0-9A-Fa-f]{6}$",
        description="Hex color for lyrics being sung (highlighted)",
    )
    unsung_lyrics_color: Optional[str] = Field(
        None,
        pattern=r"^#[0-9A-Fa-f]{6}$",
        description="Hex color for lyrics not yet sung",
    )

    def has_overrides(self) -> bool:
        """Check if any color overrides are set."""
        return any(
            [
                self.artist_color,
                self.title_color,
                self.sung_lyrics_color,
                self.unsung_lyrics_color,
            ]
        )

    def to_dict(self) -> Dict[str, str]:
        """Convert to dict, excluding None values."""
        return {k: v for k, v in self.model_dump().items() if v is not None}


class ThemesListResponse(BaseModel):
    """Response from GET /api/themes endpoint."""

    themes: List[ThemeSummary]


class ThemeDetailResponse(BaseModel):
    """Response from GET /api/themes/{theme_id} endpoint."""

    theme: ThemeDetail


# Utility functions for color conversion


def hex_to_rgba(hex_color: str, alpha: int = 255) -> str:
    """
    Convert hex color (#RRGGBB) to RGBA format for ASS subtitles.

    ASS subtitle format uses "R, G, B, A" string format.

    Args:
        hex_color: Hex color string like "#7070F7"
        alpha: Alpha value 0-255 (default 255 = opaque)

    Returns:
        RGBA string like "112, 112, 247, 255"
    """
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f"{r}, {g}, {b}, {alpha}"


def rgba_to_hex(rgba_str: str) -> str:
    """
    Convert RGBA format to hex color.

    Args:
        rgba_str: RGBA string like "112, 112, 247, 255"

    Returns:
        Hex color string like "#7070F7"
    """
    parts = [int(x.strip()) for x in rgba_str.split(",")]
    r, g, b = parts[0], parts[1], parts[2]
    return f"#{r:02x}{g:02x}{b:02x}"
