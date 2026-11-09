$ErrorActionPreference = 'Stop'
try {
    . (Join-Path $PSScriptRoot 'common.ps1')
    Set-Location -LiteralPath $RepoRoot
    if (-not (Test-Path -LiteralPath $VenvPython)) { throw 'Run windows\SETUP.bat first.' }
    if (-not (Test-Ffmpeg)) { throw 'FFmpeg/ffprobe with ASS support are missing. Run windows\SETUP.bat.' }
    Set-LocalEnvironment
    Write-Host 'Starting Karaoke Sub (preferred port 8776). The app prints and opens its actual URL. Keep this window open; Ctrl+C stops the app.' -ForegroundColor Cyan
    Invoke-Checked -Executable $VenvPython -Arguments @('-m', 'local_studio')
    exit 0
} catch {
    Write-Host "Startup failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
