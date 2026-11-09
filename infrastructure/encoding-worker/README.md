# Encoding Worker Deployment

This directory contains the scripts for the GCE encoding worker's immutable deployment pattern.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    PACKER IMAGE (rarely changes)                │
├─────────────────────────────────────────────────────────────────┤
│ - Python 3.13, FFmpeg, fonts (static dependencies)             │
│ - bootstrap.sh (downloads startup.sh from GCS)                 │
│ - systemd service definition                                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ downloads on every service start
┌─────────────────────────────────────────────────────────────────┐
│                    GCS (CI-managed, always current)             │
├─────────────────────────────────────────────────────────────────┤
│ gs://karaoke-gen-storage-nomadkaraoke/                         │
│ ├── encoding-worker/                                            │
│ │   ├── startup.sh      ← Main logic (this file)               │
│ │   └── version.txt     ← Expected version number              │
│ └── wheels/                                                     │
│     └── karaoke_gen-current.whl  ← Latest wheel (fixed path)   │
└─────────────────────────────────────────────────────────────────┘
```

## Files

| File | Location | Purpose |
|------|----------|---------|
| `bootstrap.sh` | Baked in Packer image | Downloads and runs startup.sh |
| `startup.sh` | Deployed to GCS by CI | Main startup logic |
| `version.txt` | Written to GCS by CI | Expected version for verification |

## Deployment Flow

1. **CI builds wheel** → uploads to `wheels/karaoke_gen-current.whl`
2. **CI uploads startup.sh** → `encoding-worker/startup.sh`
3. **CI writes version** → `encoding-worker/version.txt`
4. **CI restarts service** → triggers bootstrap.sh
5. **bootstrap.sh** downloads fresh startup.sh from GCS
6. **startup.sh** downloads wheel, installs, verifies version
7. **CI verifies** health endpoint returns correct version
8. **CI FAILS** if version mismatch

## Why This Pattern?

### Before (problematic)
- startup.sh baked into Packer image
- Required image rebuild + VM recreation for logic changes
- 51 versioned wheels, sorting could fail
- CI warned on version mismatch but continued

### After (robust)
- startup.sh downloaded from GCS on every start
- Logic changes via CI, no image rebuild needed
- Fixed path `karaoke_gen-current.whl`, no sorting
- CI FAILS on version mismatch

## Modifying Startup Logic

1. Edit `infrastructure/encoding-worker/startup.sh`
2. Push to main
3. CI automatically deploys to GCS
4. Service restart picks up new script

No Packer image rebuild needed!

## When to Rebuild Packer Image

Only rebuild when changing:
- Python version
- FFmpeg version
- System packages/fonts
- bootstrap.sh (should be extremely rare)

## Manual Operations

```bash
# Check current version on VM
gcloud compute ssh encoding-worker --zone=us-central1-c --project=nomadkaraoke \
  --tunnel-through-iap \
  --command="curl -s http://localhost:8080/health | jq '.wheel_version'"

# View startup logs
gcloud compute ssh encoding-worker --zone=us-central1-c --project=nomadkaraoke \
  --tunnel-through-iap \
  --command="sudo journalctl -u encoding-worker -n 50"

# Force service restart (triggers fresh startup.sh download)
gcloud compute ssh encoding-worker --zone=us-central1-c --project=nomadkaraoke \
  --tunnel-through-iap \
  --command="sudo systemctl restart encoding-worker"
```

## Troubleshooting

### Version mismatch after deployment
1. Check CI logs for GCS upload success
2. Check `/var/log/encoding-worker-startup.log` on VM
3. Verify `version.txt` in GCS matches expected

### Service won't start
1. Check bootstrap.sh can reach GCS: `gsutil ls gs://karaoke-gen-storage-nomadkaraoke/`
2. Check Secret Manager access for API key
3. Check startup.sh logs: `cat /var/log/encoding-worker-startup.log`
