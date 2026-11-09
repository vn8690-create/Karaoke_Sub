$ErrorActionPreference = 'Stop'
try {
    . (Join-Path $PSScriptRoot 'common.ps1')
    Set-Location -LiteralPath $RepoRoot
    if (-not (Test-Path -LiteralPath $VenvPython)) { throw 'Run SETUP.bat first.' }
    Set-LocalEnvironment
    if (-not (Test-Ffmpeg)) { throw 'FFmpeg/ffprobe or ASS filter is missing.' }
    Invoke-Checked -Executable $VenvPython -Arguments @('-m', 'pip', 'check')
    Invoke-Checked -Executable $VenvPython -Arguments @('-c', 'import sys, torch, torchaudio, whisper_timestamped, demucs, fastapi, uvicorn; print("Python:", sys.version); print("PyTorch:", torch.__version__); print("CUDA:", torch.cuda.is_available()); print("GPU:", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU"); print("VRAM GB:", round(torch.cuda.get_device_properties(0).total_memory/1024**3, 1) if torch.cuda.is_available() else 0)')
    Write-Host 'Environment checks passed. This checks dependencies, not transcription quality or a full song render.' -ForegroundColor Green
    exit 0
} catch {
    Write-Host "Check failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
