# CLI Feature Parity (Archived)

> **⚠️ This document has been superseded by [BACKEND-FEATURE-PARITY-PLAN.md](./BACKEND-FEATURE-PARITY-PLAN.md)**
>
> The new document provides a comprehensive plan for achieving full feature parity between the local CLI and cloud backend, including YouTube upload, Dropbox sync, and email draft functionality.

---

## Quick Reference: Current Output File Structure

On job completion, the remote CLI downloads all outputs with proper naming to match local CLI output:

```
{Brand Code} - {Artist} - {Title}/
├── Artist - Title (Final Karaoke Lossless 4k).mp4
├── Artist - Title (Final Karaoke Lossless 4k).mkv
├── Artist - Title (Final Karaoke Lossy 4k).mp4
├── Artist - Title (Final Karaoke Lossy 720p).mp4
├── Artist - Title (Final Karaoke CDG).zip
├── Artist - Title (Final Karaoke TXT).zip
├── Artist - Title (Karaoke).cdg
├── Artist - Title (Karaoke).mp3
├── Artist - Title (Karaoke).lrc
├── Artist - Title (Karaoke).ass
├── Artist - Title (Karaoke).txt
├── Artist - Title (Title).mov
├── Artist - Title (Title).jpg
├── Artist - Title (Title).png
├── Artist - Title (End).mov
├── Artist - Title (End).jpg
├── Artist - Title (End).png
├── Artist - Title (With Vocals).mkv
├── Artist - Title (Instrumental model_bs_roformer...).flac
├── Artist - Title (Instrumental +BV mel_band_roformer...).flac
└── stems/
    ├── Artist - Title (Instrumental model_bs_roformer_ep_317_sdr_12.9755.ckpt).flac
    ├── Artist - Title (Instrumental +BV mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt).flac
    ├── Artist - Title (Vocals model_bs_roformer_ep_317_sdr_12.9755.ckpt).flac
    ├── Artist - Title (Lead Vocals mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt).flac
    ├── Artist - Title (Backing Vocals mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt).flac
    ├── Artist - Title (Bass htdemucs_6s.yaml).flac
    ├── Artist - Title (Drums htdemucs_6s.yaml).flac
    ├── Artist - Title (Guitar htdemucs_6s.yaml).flac
    ├── Artist - Title (Piano htdemucs_6s.yaml).flac
    ├── Artist - Title (Other htdemucs_6s.yaml).flac
    └── Artist - Title (Vocals htdemucs_6s.yaml).flac
```

---

## See Also

- **[BACKEND-FEATURE-PARITY-PLAN.md](./BACKEND-FEATURE-PARITY-PLAN.md)** - Full implementation plan
- [ARCHITECTURE.md](../01-reference/ARCHITECTURE.md) - System architecture
- [STYLE-LOADER-REFACTOR.md](./STYLE-LOADER-REFACTOR.md) - Style loading details
