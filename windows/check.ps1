$ErrorActionPreference = 'Stop'
try {
    . (Join-Path $PSScriptRoot 'common.ps1')
    Set-Location -LiteralPath $RepoRoot
    if (-not (Test-Path -LiteralPath $VenvPython)) { throw 'Run SETUP.bat first.' }
    Set-LocalEnvironment
    if (-not (Test-Ffmpeg)) { throw 'FFmpeg/ffprobe or ASS filter is missing.' }
    Invoke-Checked -Executable $VenvPython -Arguments @('-m', 'pip', 'check')
    Invoke-Checked -Executable $VenvPython -Arguments @((Join-Path $PSScriptRoot 'verify_environment.py'))
    Write-Host 'Environment checks passed. This checks dependencies, not transcription quality or a full song render.' -ForegroundColor Green
    exit 0
} catch {
    Write-Host "Check failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
