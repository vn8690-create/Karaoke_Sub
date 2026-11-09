# Instrumental Review UX Fixes - 2026-01-26

## Summary

Fixed three UX issues in the instrumental review flow and one testing infrastructure issue related to local mode detection. The changes improve user feedback during audio loading and provide clear post-submission confirmation.

## Issues Fixed

### 1. Loading Spinner Not Visible

**Problem:** When switching between audio stems (backing vocals, pure instrumental, etc.), there was no visual feedback that audio was loading.

**Root Cause:** The loading spinner was implemented but wasn't visible because:
- The wrapper div around WaveformViewer was breaking absolute positioning
- The overlay approach wasn't integrated with the tab component

**Solution:** The StemComparison component already had loading state support via the `isLoading` prop:
- Shows `Loader2` spinner icon on the active tab
- Disables all tabs during loading to prevent race conditions
- Applies `opacity-50` styling to inactive tabs

No additional overlay needed - the tab component handles loading state elegantly.

### 2. Large Gap Under Waveform

**Problem:** The waveform had excess vertical space below it, wasting screen real estate.

**Root Cause:** A wrapper `<div className="relative flex-1 min-h-0">` was added around WaveformViewer, breaking the flexbox layout. The WaveformViewer was originally designed as a direct child of the flex container.

**Solution:** Removed the wrapper div. The WaveformViewer is now a direct flex child again, filling available space correctly.

**Before:**
```tsx
<div className="relative flex-1 min-h-0">
  <WaveformViewer ... />
  {isAudioLoading && <overlay />}
</div>
```

**After:**
```tsx
<WaveformViewer ... />
```

### 3. No Success Screen in Cloud Mode

**Problem:** After submitting the instrumental selection in cloud mode, users saw a brief toast and were immediately redirected without clear confirmation.

**Root Cause:** The success screen logic only ran in local mode (`window.close()`). Cloud mode skipped it and used `router.push("/app")` immediately.

**Solution:** Extended the success screen to both modes with appropriate messaging:
- Cloud mode: "Redirecting in 3s..." then redirects to `/app`
- Local mode: "Closing in 2s..." then closes window
- Both modes show which instrumental option was selected

**Implementation:**
```tsx
// Show success screen in both modes
setShowSuccess(true)
setCountdown(isLocalMode ? 2 : 3)

// Countdown effect handles both modes
useEffect(() => {
  if (!showSuccess) return
  const interval = setInterval(() => {
    setCountdown((prev) => {
      if (prev <= 1) {
        clearInterval(interval)
        if (isLocalMode) {
          window.close()
        } else {
          router.push("/app")
        }
        return 0
      }
      return prev - 1
    })
  }, 1000)
  return () => clearInterval(interval)
}, [showSuccess, isLocalMode, router])
```

## Testing Infrastructure Fix

### Local Mode Detection for E2E Tests

**Problem:** E2E tests running on `localhost:3000` were being detected as local CLI mode, making it impossible to test cloud mode behavior.

**Root Cause:** The `isLocalMode()` function only checked hostname and port, not the routing pattern.

**Solution:** Enhanced `isLocalMode()` to check for hash-based routing:
- Hash pattern `#/jobId/review` or `#/jobId/instrumental` → cloud mode
- Path pattern `/local/review` or `/local/instrumental` → local CLI mode
- Allows E2E tests to run in cloud mode on localhost by using hash routing

**Implementation:**
```typescript
export function isLocalMode(): boolean {
  if (typeof window === 'undefined') return false

  const { hostname, port, hash, pathname } = window.location

  // Must be on localhost
  if (hostname !== 'localhost' && hostname !== '127.0.0.1') return false

  // Must be on one of the known local server ports
  if (!ALL_LOCAL_PORTS.includes(port)) return false

  // If using hash-based routing (cloud mode pattern), it's NOT local mode
  if (hash && hash.match(/^#\/?[^/]+\/(review|instrumental)/)) {
    return false
  }

  // If pathname explicitly contains /local/, it's local mode
  if (pathname.includes('/local/')) {
    return true
  }

  // Default to local mode on localhost (backwards compatibility)
  return true
}
```

## Backend Fix

### Backing Vocals Audio URL Field Name

**Problem:** Backing vocals audio wouldn't load in cloud mode.

**Root Cause:** Backend was returning `audio_urls['backing']` but frontend expected `audio_urls['backing_vocals']`.

**Solution:** Changed backend to use `'backing_vocals'` to match frontend expectations:

```python
# backend/api/routes/review.py
audio_urls = {
    "clean": clean_flac_url,
    "backing_vocals": backing_flac_url,  # Changed from "backing"
    "original": original_flac_url,
}
```

## Testing

### Unit Tests (29 new tests)
- **`local-mode.test.ts`** (17 tests): Comprehensive coverage of `isLocalMode()` logic
  - Production hostname detection
  - Localhost with non-local ports
  - Hash-based routing (cloud mode)
  - Path-based routing (local CLI mode)
  - Backwards compatibility
  - Helper functions (`getLocalJobId`, `createLocalModeJob`, etc.)

- **`StemComparison.test.tsx`** (11 tests): Loading state behavior
  - Spinner visibility on active tab
  - Tab disable during loading
  - Opacity styling on inactive tabs

- **`test_routes_review.py`** (2 tests): Backend API contract
  - Instrumental analysis returns correct audio_urls structure

### E2E Tests (12 new tests)
- **`instrumental-review-ux.spec.ts`** (12 tests):
  - Loading spinner visibility when switching tabs
  - Tab disable behavior during loading
  - Waveform layout without excess gaps
  - Success screen in cloud mode with redirect
  - Success screen in local mode with window close
  - Countdown timer behavior
  - Selection options display
  - Visual regression screenshots

All 276 unit tests pass. All 12 E2E tests pass.

## Files Modified

### Source Files
- `frontend/components/instrumental-review/InstrumentalSelector.tsx`
  - Removed wrapper div around WaveformViewer
  - Extended success screen to cloud mode with countdown
  - Fixed dependency array (removed unused `router` from handleSubmit)

- `frontend/lib/local-mode.ts`
  - Enhanced `isLocalMode()` with hash routing detection

- `backend/api/routes/review.py`
  - Changed `audio_urls['backing']` to `audio_urls['backing_vocals']`

### Test Files (new)
- `frontend/lib/__tests__/local-mode.test.ts`
- `frontend/e2e/regression/instrumental-review-ux.spec.ts`

### Documentation
- `docs/LESSONS-LEARNED.md` - Added lesson about local mode detection
- `docs/README.md` - Added recent changes entry

## Lessons Learned

### Local Mode Detection for Testing
When detecting local CLI mode, always check the routing pattern in addition to hostname/port. Hash-based routing indicates cloud mode even on localhost, allowing E2E tests to exercise cloud behavior without a remote server.

### Loading States in Tab Components
Tab components with built-in loading state support (spinner on active tab, disabled state on others) provide better UX than generic overlays. The user can see which audio source they selected and that it's loading.

### Success Screens Should Be Explicit
Even if users will be redirected automatically, showing an explicit success screen with countdown:
- Confirms the action was successful
- Shows what was selected
- Gives users time to read the confirmation
- Prevents confusion about what just happened

Better to show 3 seconds of confirmation than immediately redirect and leave users wondering if it worked.

## Future Considerations

### InstrumentalSelector Unit Tests
The `InstrumentalSelector` component is complex but doesn't have direct unit tests. The E2E tests provide good coverage of user-facing behavior, but unit tests for individual functions (like `mergeAudibleSegments`) could improve maintainability.

### Loading State Consistency
Consider using the StemComparison loading pattern (spinner in tab) across other audio/video components for consistency.
