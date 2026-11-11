"""Verify the Windows Local Studio Python environment without fragile python -c quoting.

Windows PowerShell 5.1 can remove nested double quotes from arguments supplied
to native executables; a script file makes verification unambiguous.
"""
from __future__ import annotations

import argparse
import importlib
import sys


REQUIRED_MODULES = (
    "torch", "torchaudio", "whisper_timestamped", "stable_whisper",
    "demucs", "fastapi", "uvicorn",
)


def verify(require_cuda: bool = False) -> int:
    if sys.version_info[:2] != (3, 11):
        print("ERROR: Python 3.11 (64-bit) is required; current:", sys.version)
        return 1

    imported = {}
    for name in REQUIRED_MODULES:
        try:
            imported[name] = importlib.import_module(name)
        except Exception as exc:
            print(f"ERROR: Cannot import {name}: {exc}")
            print("Re-run windows\\SETUP.bat to install missing dependencies.")
            return 1

    torch = imported["torch"]
    try:
        cuda = bool(torch.cuda.is_available())
        gpu_name = torch.cuda.get_device_name(0) if cuda else "CPU"
        vram = round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 1) if cuda else 0
    except Exception as exc:
        print(f"ERROR: Cannot query PyTorch CUDA: {exc}")
        return 1

    print("Python:", sys.version.split()[0])
    print("PyTorch:", torch.__version__)
    print("CUDA available:", cuda)
    print("GPU:", gpu_name)
    print("VRAM GB:", vram)
    print("Required Python modules: OK")

    if require_cuda and not cuda:
        print("ERROR: NVIDIA GPU was detected, but CUDA is unavailable.")
        print("Update NVIDIA driver or run: powershell -ExecutionPolicy Bypass -File windows\\setup.ps1 -CpuOnly")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Check NVS Karaoke Sub Windows Python dependencies")
    parser.add_argument("--require-cuda", action="store_true")
    args = parser.parse_args()
    return verify(require_cuda=args.require_cuda)


if __name__ == "__main__":
    raise SystemExit(main())
