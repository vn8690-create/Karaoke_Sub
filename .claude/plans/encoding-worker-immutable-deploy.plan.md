# Plan: Encoding Worker Immutable Deployment Pattern

## Status: In Progress

## Problem Statement

The GCE encoding worker has recurring version mismatch issues because:
1. `startup.sh` is baked into the Packer image (requires image rebuild + VM recreation)
2. Wheel selection uses `sort -V` which can fail if image is outdated
3. CI only restarts service - doesn't verify version strictly
4. Multiple actors (CI, Pulumi, manual SSH) can cause drift
5. 51 old wheel files accumulate in GCS bucket

## Solution: Immutable Deployment Pattern

### Core Principles
1. **Single Source of Truth**: All code and config from GCS, nothing baked in image
2. **Fixed Wheel Path**: `karaoke_gen-current.whl` eliminates sorting
3. **Version Manifest**: CI writes expected version, service MUST match
4. **Strict Verification**: CI FAILS if deployed version doesn't match
5. **Self-Updating Startup**: Download startup.sh from GCS on every boot

## Implementation Steps

### Phase 1: GCS Structure & Scripts

- [x] **Step 1.1**: Create `infrastructure/encoding-worker/` directory
- [x] **Step 1.2**: Create `bootstrap.sh` (minimal, baked in image)
- [x] **Step 1.3**: Create `startup.sh` (CI-managed, deployed to GCS)
- [x] **Step 1.4**: Create README.md with documentation

### Phase 2: CI Workflow Updates

- [x] **Step 2.1**: Update CI to upload wheel to fixed path
- [x] **Step 2.2**: Update CI to upload startup.sh to GCS
- [x] **Step 2.3**: Update CI to write version.txt manifest
- [x] **Step 2.4**: Update CI to strictly verify deployed version (fail on mismatch)

### Phase 3: Packer Image Updates

- [x] **Step 3.1**: Update provision.sh to use bootstrap.sh
- [ ] **Step 3.2**: Rebuild Packer image (manual step after merge)
- [ ] **Step 3.3**: Recreate VM to use new image (manual step after merge)

### Phase 4: Documentation & Cleanup

- [x] **Step 4.1**: Update LESSONS-LEARNED.md with new pattern
- [x] **Step 4.2**: Update infrastructure/packer/README.md
- [ ] **Step 4.3**: Add lifecycle rule for old wheels (optional, later)

## New GCS Structure

```
gs://karaoke-gen-storage-nomadkaraoke/
├── wheels/
│   ├── karaoke_gen-current.whl       # Latest (CI overwrites)
│   └── karaoke_gen-{version}.whl     # Versioned for rollback
│
└── encoding-worker/
    ├── bootstrap.sh                  # Reference copy
    ├── startup.sh                    # CI-managed, downloaded on boot
    └── version.txt                   # Expected version number
```

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `infrastructure/encoding-worker/bootstrap.sh` | Create | Minimal loader (baked in image) |
| `infrastructure/encoding-worker/startup.sh` | Create | Main logic (deployed to GCS) |
| `infrastructure/packer/scripts/provision.sh` | Modify | Use bootstrap.sh |
| `.github/workflows/ci.yml` | Modify | New deployment flow |
| `docs/LESSONS-LEARNED.md` | Modify | Document pattern |

## Testing Strategy

1. **Unit test**: Verify startup.sh logic locally
2. **Integration test**: After merge, verify:
   - CI uploads files to correct GCS paths
   - Service starts with correct version
   - Health endpoint returns expected version
3. **Manual verification**: Check VM logs after first deployment

## Rollback Plan

If issues occur:
1. CI can re-upload previous wheel to `karaoke_gen-current.whl`
2. Previous versioned wheels remain in GCS for manual rollback
3. Old Packer images remain for VM rollback

## Open Questions

None - design is complete.

## Notes

- Bootstrap.sh is ~10 lines and should never need changes
- All logic changes go through startup.sh in GCS
- Version verification is strict - CI fails on mismatch
