# Theme Validation & Removal of Default Fallbacks - 2026-01-22

## Summary

Removed all default style fallback logic to ensure cloud karaoke jobs always use complete, explicit themes (nomad). Implemented two-phase rollout: Phase 1 added validation with warnings (non-breaking), Phase 2 removed defaults and requires complete themes (breaking change).

## Problem

The system had multiple layers of fallback logic that would silently use incomplete default styles when themes were missing or incomplete:
- `load_styles_from_gcs()` would fall back to minimal styles if no theme path
- `load_styles_from_gcs()` would fall back to defaults on download failure
- Getter functions (`get_intro_format()`, etc.) would merge incomplete themes with DEFAULT_* constants
- `StyleConfig` class would return defaults if no theme loaded

This created risk of generating unstyled or partially-styled videos if theme configuration was missing.

## Solution

### Phase 1: Validation with Warnings (v0.108.15)

Added infrastructure to detect incomplete themes without breaking existing behavior:

**New Validation Function:**
```python
def validate_theme_completeness(style_params, logger) -> Tuple[bool, List[str]]
```
- Checks all required sections: intro, end, karaoke, cdg
- Checks all required fields within each section
- Returns (is_complete, list_of_missing_fields)

**Updated Getter Functions:**
- Added warnings when fields missing from themes
- Still merged with defaults (backward compatible)
- Warned: "In future versions, incomplete themes will be rejected"

**New CLI Flags:**
- `--list-themes`: Show available themes from GCS
- `--validate-theme`: Validate theme completeness and exit

**New Script:**
- `scripts/verify-gcs-themes.py`: Validate all GCS themes are complete

### Phase 2: Remove Defaults & Require Complete Themes (v0.109.0) - BREAKING

Removed all fallback logic and require complete themes everywhere:

**Style Getter Functions:**
```python
def get_intro_format(style_params) -> Dict[str, Any]:
    """Raises ValueError if intro section missing or incomplete."""
    if "intro" not in style_params:
        raise ValueError("Missing 'intro' section in theme...")

    missing = [f for f in required if f not in intro_params]
    if missing:
        raise ValueError(f"Incomplete 'intro' section. Missing: {missing}...")

    return intro_params.copy()  # Return as-is, no merging
```

Applied same pattern to `get_end_format()`, `get_karaoke_format()`, `get_cdg_format()`.

**GCS Style Loader:**
```python
def load_styles_from_gcs(...):
    if not style_params_gcs_path:
        raise ValueError("style_params_gcs_path is required...")

    # On download failure:
    except Exception as e:
        raise ValueError(f"Failed to download theme from GCS: {e}") from e
```

**Worker Style Helper:**
```python
class StyleConfig:
    def get_intro_format(self) -> Dict[str, Any]:
        if not self._style_params:
            raise ValueError("No style parameters loaded...")
        return get_intro_format(self._style_params)
```

## Multi-Layer Protection

The system now has 4 layers ensuring all cloud jobs use complete themes:

1. **API Layer** (`backend/api/routes/file_upload.py`): Auto-applies nomad theme if none specified
2. **Job Manager** (`backend/services/job_manager.py`): Enforces theme_id requirement at creation
3. **Workers** (`backend/workers/screens_worker.py`): Check theme presence at processing time
4. **Style Loader** (NEW): Fail fast if theme missing or incomplete

## Files Changed

### Core Logic
- `karaoke_gen/style_loader.py`: Added validation, removed merging, fail fast
- `backend/workers/style_helper.py`: Removed fallbacks, fail fast

### CLI
- `karaoke_gen/utils/cli_args.py`: Added --list-themes, --validate-theme flags
- `karaoke_gen/utils/gen_cli.py`: Added handlers for new flags

### Tests
- `tests/unit/conftest.py`: Added complete_theme fixture
- `tests/unit/test_style_validation.py`: New comprehensive test suite (19 tests)
- `tests/unit/test_style_loader.py`: Updated to expect errors instead of fallbacks
- `tests/unit/test_initialization.py`: Updated to use complete theme
- `tests/unit/test_gen_cli.py`: Added new CLI flags to mock fixtures

### Scripts
- `scripts/verify-gcs-themes.py`: New script to validate all GCS themes

## Breaking Changes in v0.109.0

**API Changes:**
- Style getter functions now raise `ValueError` instead of merging with defaults
- `load_styles_from_gcs()` raises `ValueError` instead of returning minimal styles
- `StyleConfig` methods raise `ValueError` instead of returning defaults

**Behavioral Changes:**
- No fallback to defaults if theme download fails
- No merging with defaults if theme incomplete
- All themes must have complete intro, end, karaoke, cdg sections

**Migration Path:**
- Ensure all GCS themes are complete (use `scripts/verify-gcs-themes.py`)
- Fix any incomplete themes before upgrading
- Local CLI users must specify `--theme` or `--style_params_json`

## Testing

- **1086 unit tests passing** (no regressions)
- New validation tests cover all error scenarios
- Tests updated to use complete themes via fixture

## Key Decisions

**Why two-phase rollout?**
- Phase 1 allowed us to validate that all GCS themes are complete before breaking changes
- Warnings in production logs would alert us to incomplete themes
- Non-breaking phase could be deployed and monitored safely

**Why fail fast instead of fallback?**
- Silent fallbacks hide configuration errors
- Better to fail loudly and fix the root cause
- Ensures video quality by preventing partially-styled outputs
- Clear error messages guide users to fix incomplete themes

**Why remove DEFAULT_* constants entirely?**
- They're still used for validation (checking required fields)
- But removed from runtime merging logic
- Could be deleted in future if validation uses schema instead

## Future Considerations

**Potential Improvements:**
- Schema-based validation instead of comparing to DEFAULT_* constants
- Theme versioning to handle breaking changes to theme structure
- Theme inheritance (e.g., themes that extend base themes)

**Monitoring:**
- Watch for `ValueError` exceptions in production logs
- Should be zero if all themes are complete
- Any errors indicate theme configuration issues that need fixing

## Related PRs

- Phase 1 (v0.108.15): Theme validation with warnings
- Phase 2 (v0.109.0): Remove defaults, require complete themes
