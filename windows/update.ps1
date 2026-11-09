$ErrorActionPreference = 'Stop'
try {
    . (Join-Path $PSScriptRoot 'common.ps1')
    Set-Location -LiteralPath $RepoRoot
    if (-not (Test-Path -LiteralPath $VenvPython)) {
        throw 'Local Python environment not found. Run windows\SETUP.bat once before UPDATE.bat.'
    }
    $requirements = Join-Path $RepoRoot 'requirements-local.txt'
    if (-not (Test-Path -LiteralPath $requirements)) {
        throw 'requirements-local.txt is missing. Extract the update into the existing Karaoke_Sub folder.'
    }
    Set-LocalEnvironment
    Write-Host 'Updating Karaoke Sub libraries in the existing local environment...' -ForegroundColor Cyan
    Write-Host 'Keep START closed until this finishes. Existing projects and model files are kept.'
    Invoke-Checked -Executable $VenvPython -Arguments @('-m', 'pip', 'install', '-r', $requirements)
    Invoke-Checked -Executable $VenvPython -Arguments @('-m', 'pip', 'check')
    Invoke-Checked -Executable $VenvPython -Arguments @('-c', 'import stable_whisper; import importlib.metadata as m; print("stable-ts:", m.version("stable-ts"))')
    Write-Host 'Update complete. Run windows\START.bat, then press Ctrl+F5 in your browser.' -ForegroundColor Green
    exit 0
} catch {
    Write-Host "Update failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
