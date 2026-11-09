/**
 * Video theme types and utilities for karaoke video styles.
 *
 * These are pre-made style configurations stored in GCS that control
 * the visual appearance of generated karaoke videos.
 */

/**
 * Summary of a theme for listing in the theme selector.
 */
export interface VideoThemeSummary {
  id: string;
  name: string;
  description: string;
  preview_url: string | null;
  thumbnail_url: string | null;
  is_default: boolean;
}

/**
 * Full theme details including style parameters.
 */
export interface VideoThemeDetail {
  id: string;
  name: string;
  description: string;
  preview_url: string | null;
  is_default: boolean;
  style_params: Record<string, any>;
  has_youtube_description: boolean;
}

/**
 * Response from GET /api/themes
 */
export interface ThemesListResponse {
  themes: VideoThemeSummary[];
}

/**
 * Response from GET /api/themes/{theme_id}
 */
export interface ThemeDetailResponse {
  theme: VideoThemeDetail;
}

/**
 * User color overrides for customizing a theme.
 * All colors are hex format (#RRGGBB).
 */
export interface ColorOverrides {
  /** Color for artist name on intro/end screens */
  artist_color?: string;
  /** Color for song title on intro/end screens */
  title_color?: string;
  /** Color for lyrics being sung (highlighted) */
  sung_lyrics_color?: string;
  /** Color for lyrics not yet sung */
  unsung_lyrics_color?: string;
}

/**
 * Check if color overrides has any values set.
 */
export function hasColorOverrides(overrides?: ColorOverrides): boolean {
  if (!overrides) return false;
  return !!(
    overrides.artist_color ||
    overrides.title_color ||
    overrides.sung_lyrics_color ||
    overrides.unsung_lyrics_color
  );
}

/**
 * Get clean color overrides object (only non-null values).
 */
export function cleanColorOverrides(overrides?: ColorOverrides): ColorOverrides | undefined {
  if (!overrides) return undefined;

  const clean: ColorOverrides = {};
  if (overrides.artist_color) clean.artist_color = overrides.artist_color;
  if (overrides.title_color) clean.title_color = overrides.title_color;
  if (overrides.sung_lyrics_color) clean.sung_lyrics_color = overrides.sung_lyrics_color;
  if (overrides.unsung_lyrics_color) clean.unsung_lyrics_color = overrides.unsung_lyrics_color;

  return Object.keys(clean).length > 0 ? clean : undefined;
}

/**
 * Validate hex color format.
 */
export function isValidHexColor(color: string): boolean {
  return /^#[0-9A-Fa-f]{6}$/.test(color);
}

/**
 * Default color override values based on common themes.
 */
export const DEFAULT_COLOR_PRESETS = {
  nomad: {
    artist_color: "#ffdf6b",
    title_color: "#ffffff",
    sung_lyrics_color: "#7070F7",
    unsung_lyrics_color: "#ffffff",
  },
  classic: {
    artist_color: "#ffffff",
    title_color: "#ffffff",
    sung_lyrics_color: "#00ff00",
    unsung_lyrics_color: "#ffffff",
  },
} as const;
