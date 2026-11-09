Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $RepoRoot '.venv-local\Scripts\python.exe'

function Invoke-Checked {
    param([Parameter(Mandatory)][string]$Executable, [string[]]$Arguments = @())
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed (exit $LASTEXITCODE): $Executable $($Arguments -join ' ')"
    }
}

function Refresh-ToolPath {
    $paths = @(
        [Environment]::GetEnvironmentVariable('Path', 'Machine'),
        [Environment]::GetEnvironmentVariable('Path', 'User'),
        $env:Path,
        (Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Links')
    )
    $packageRoot = Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages'
    if (Test-Path $packageRoot) {
        $packages = Get-ChildItem -Path $packageRoot -Directory -Filter 'Gyan.FFmpeg*' -ErrorAction SilentlyContinue
        foreach ($package in $packages) {
            $binaries = Get-ChildItem -LiteralPath $package.FullName -Recurse -File -Filter 'ffmpeg.exe' -ErrorAction SilentlyContinue
            foreach ($binary in $binaries) { $paths += $binary.DirectoryName }
        }
    }
    $env:Path = (($paths -join ';').Split(';') | Where-Object { $_ } | Select-Object -Unique) -join ';'
}

function Test-Ffmpeg {
    Refresh-ToolPath
    if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) { return $false }
    if (-not (Get-Command ffprobe -ErrorAction SilentlyContinue)) { return $false }
    $filters = & ffmpeg -hide_banner -filters 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0 -or $filters -notmatch '\bass\s+V->V') { return $false }
    return $true
}

function Set-LocalEnvironment {
    # Keep models beside the project instead of spreading them across a Windows profile.
    $cacheRoot = Join-Path $RepoRoot '.local-data\models'
    New-Item -ItemType Directory -Path $cacheRoot -Force | Out-Null
    $env:KARAOKE_MODEL_DIR = $cacheRoot
    $env:XDG_CACHE_HOME = $cacheRoot
    $env:TORCH_HOME = Join-Path $cacheRoot 'torch'
    $env:PYTHONUTF8 = '1'
    Refresh-ToolPath
}
