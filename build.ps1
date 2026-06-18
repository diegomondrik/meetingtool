# build.ps1 - MeetingTool v2.5 PyInstaller build (Windows ARM64)
# ASCII only (Windows PowerShell 5.1 misreads UTF-8 without BOM - lesson L-01).
#
# Usage:  .\build.ps1
# Output: dist\MeetingTool\MeetingTool.exe

# Do NOT use $ErrorActionPreference = "Stop": PyInstaller logs INFO to stderr,
# and under "Stop" PowerShell treats native-command stderr as a terminating
# error (NativeCommandError) even on success. We check $LASTEXITCODE instead.
$ErrorActionPreference = "Continue"
Set-Location -Path $PSScriptRoot

Write-Host "=================================================="
Write-Host "  MeetingTool - PyInstaller build"
Write-Host "=================================================="

# 1. Verify PyInstaller is available
Write-Host "`n[1/4] Checking PyInstaller..."
$pyiVersion = python -m PyInstaller --version
if ($LASTEXITCODE -ne 0) {
    Write-Host "  PyInstaller not found. Install with: pip install -r requirements.txt" -ForegroundColor Red
    exit 1
}
Write-Host "  PyInstaller $pyiVersion" -ForegroundColor Green

# 2. Warn if ffmpeg is missing (runtime system dependency, not bundled)
Write-Host "`n[2/4] Checking ffmpeg (system dependency)..."
$ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
if ($null -eq $ffmpeg) {
    Write-Host "  ffmpeg not on PATH. The binary will still build, but frame" -ForegroundColor Yellow
    Write-Host "  extraction needs ffmpeg installed on the target machine." -ForegroundColor Yellow
} else {
    Write-Host "  ffmpeg found: $($ffmpeg.Source)" -ForegroundColor Green
}

# 3. Clean previous build artifacts
Write-Host "`n[3/4] Cleaning previous build..."
foreach ($dir in @("build", "dist")) {
    if (Test-Path $dir) {
        Remove-Item -Recurse -Force $dir
        Write-Host "  Removed $dir\"
    }
}

# 4. Build
Write-Host "`n[4/4] Building (this takes a few minutes)..."
python -m PyInstaller MeetingTool.spec --noconfirm --clean
if ($LASTEXITCODE -ne 0) {
    Write-Host "`n  BUILD FAILED." -ForegroundColor Red
    exit 1
}

$exePath = Join-Path $PSScriptRoot "dist\MeetingTool\MeetingTool.exe"
if (Test-Path $exePath) {
    $sizeMB = [math]::Round((Get-ChildItem "dist\MeetingTool" -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB, 1)
    Write-Host "`n=================================================="
    Write-Host "  BUILD OK" -ForegroundColor Green
    Write-Host "  Executable: $exePath"
    Write-Host "  Total size: $sizeMB MB"
    Write-Host "=================================================="
} else {
    Write-Host "`n  Build finished but MeetingTool.exe not found." -ForegroundColor Red
    exit 1
}
