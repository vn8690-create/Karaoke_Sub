param([switch]$CpuOnly)
$ErrorActionPreference = 'Stop'
try {
    . (Join-Path $PSScriptRoot 'common.ps1')
    Set-Location -LiteralPath $RepoRoot
    Write-Host 'Karaoke Sub - Windows setup (Python 3.11)' -ForegroundColor Cyan

    if (-not (Test-Path -LiteralPath $VenvPython)) {
        $python311 = $null
        $launcher = Get-Command py -ErrorAction SilentlyContinue
        if ($launcher) {
            $previousPreference = $ErrorActionPreference
            $ErrorActionPreference = 'Continue'
            $candidate = & $launcher.Source -3.11 -c 'import sys; print(sys.executable)' 2>$null
            $candidateExit = $LASTEXITCODE
            $ErrorActionPreference = $previousPreference
            if ($candidateExit -eq 0 -and $candidate) { $python311 = ($candidate | Select-Object -Last 1).Trim() }
        }
        if (-not $python311) {
            $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
            if ($pythonCommand) {
                $previousPreference = $ErrorActionPreference
                $ErrorActionPreference = 'Continue'
                $candidate = & $pythonCommand.Source -c 'import sys; print(sys.executable) if sys.version_info[:2] == (3,11) else sys.exit(1)' 2>$null
                $candidateExit = $LASTEXITCODE
                $ErrorActionPreference = $previousPreference
                if ($candidateExit -eq 0 -and $candidate) { $python311 = ($candidate | Select-Object -Last 1).Trim() }
            }
        }
        if (-not $python311) {
            throw 'Python 3.11 not found. Install Python 3.11 (64-bit) from python.org, enable the Python launcher, then run SETUP.bat again. Or use: winget install --id Python.Python.3.11 --exact'
        }
        Invoke-Checked -Executable $python311 -Arguments @('-m', 'venv', '.venv-local')
    }
    # Avoid nested quotes with Windows PowerShell 5.1 native process invocation.
    Invoke-Checked -Executable $VenvPython -Arguments @('-c', 'import sys; assert sys.version_info[:2] == (3,11)')

    if (-not (Test-Ffmpeg)) {
        if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
            throw 'FFmpeg + ffprobe with ASS subtitle support are missing. Install Gyan FFmpeg from https://www.gyan.dev/ffmpeg/builds/ and add its bin folder to PATH, then run SETUP.bat again.'
        }
        Write-Host 'Installing FFmpeg with winget...'
        Invoke-Checked -Executable 'winget' -Arguments @('install', '--id', 'Gyan.FFmpeg', '--exact', '--source', 'winget', '--accept-package-agreements', '--accept-source-agreements', '--disable-interactivity')
        if (-not (Test-Ffmpeg)) { throw 'FFmpeg or its ASS filter is still unavailable. Restart this terminal and run SETUP.bat again. Check that ffmpeg and ffprobe are on PATH.' }
    }

    $hasNvidia = $false
    if (-not $CpuOnly -and (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) {
        $previousPreference = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        & nvidia-smi --query-gpu=name --format=csv,noheader
        $hasNvidia = ($LASTEXITCODE -eq 0)
        $ErrorActionPreference = $previousPreference
    }
    $torchIndex = if ($hasNvidia) { 'https://download.pytorch.org/whl/cu121' } else { 'https://download.pytorch.org/whl/cpu' }
    Write-Host "Installing PyTorch from $torchIndex"
    Invoke-Checked -Executable $VenvPython -Arguments @('-m', 'pip', 'install', '--upgrade', 'pip', 'setuptools', 'wheel')
    # Index selection matters when switching a previously installed CPU/CUDA environment.
    Invoke-Checked -Executable $VenvPython -Arguments @('-m', 'pip', 'install', '--upgrade', '--force-reinstall', 'torch==2.5.1', 'torchaudio==2.5.1', '--index-url', $torchIndex)
    Invoke-Checked -Executable $VenvPython -Arguments @('-m', 'pip', 'install', '-r', 'requirements-local.txt')
    Invoke-Checked -Executable $VenvPython -Arguments @('-m', 'pip', 'check')
    Set-LocalEnvironment
    # Use a .py file instead of python -c: PS 5.1 may strip quoted Python string literals.
    $verifyArgs = @((Join-Path $PSScriptRoot 'verify_environment.py'))
    if ($hasNvidia) { $verifyArgs += '--require-cuda' }
    Invoke-Checked -Executable $VenvPython -Arguments $verifyArgs
    Write-Host 'Setup complete. Run START.bat to open Karaoke Sub.' -ForegroundColor Green
    exit 0
} catch {
    Write-Host "Setup failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
