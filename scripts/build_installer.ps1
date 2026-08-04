[CmdletBinding()]
param (
    [switch]$Clean,
    [string]$IsccPath,
    [switch]$SkipTests,
    [switch]$RebuildApp
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

Write-Host "=== Loadvia 1.1.0 Installer Build Process ===" -ForegroundColor Cyan

# 1. Rebuild Portable App if requested
if ($RebuildApp) {
    Write-Host "Rebuilding portable application package..." -ForegroundColor Yellow
    $BuildWinScript = Join-Path $PSScriptRoot "build_windows.ps1"
    & $BuildWinScript -Clean
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Portable app build failed!"
        exit $LASTEXITCODE
    }
}

# 2. Verify Portable Build
$TargetDir = Join-Path $ProjectRoot "dist\Loadvia"
$ExePath = Join-Path $TargetDir "Loadvia.exe"
if (-not (Test-Path $ExePath)) {
    Write-Error "Portable app missing at $ExePath! Run with -RebuildApp or build portable first."
    exit 1
}

$VerInfo = (Get-Item $ExePath).VersionInfo
if ($VerInfo.ProductName -ne "Loadvia" -or $VerInfo.FileVersion -ne "1.1.0.0") {
    Write-Error "Portable EXE version mismatch! Expected Loadvia 1.1.0.0"
    exit 1
}
Write-Host "[OK] Verified portable build ($ExePath)." -ForegroundColor Green

# 3. Locate ISCC.exe
function Resolve-IsccPath ([string]$GivenPath) {
    if ($GivenPath -and (Test-Path $GivenPath)) {
        return (Get-Item $GivenPath).FullName
    }
    $Found = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if ($Found) {
        return $Found.Source
    }
    $Candidates = @(
        "C:\Program Files\Inno Setup 7\ISCC.exe",
        "C:\Program Files (x86)\Inno Setup 7\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe",
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "$env:LocalAppData\Programs\Inno Setup 6\ISCC.exe",
        "$env:LocalAppData\Programs\Inno Setup 7\ISCC.exe"
    )
    foreach ($c in $Candidates) {
        if (Test-Path $c) {
            return (Get-Item $c).FullName
        }
    }
    return $null
}

$ResolvedIscc = Resolve-IsccPath $IsccPath
if (-not $ResolvedIscc) {
    Write-Error "ISCC.exe (Inno Setup Compiler) not found! Please install Inno Setup 6/7 or pass -IsccPath."
    exit 1
}
Write-Host "[OK] ISCC compiler: $ResolvedIscc" -ForegroundColor Green

# 4. Pre-build Installer Tests
if (-not $SkipTests) {
    Write-Host "Running pre-build installer tests..." -ForegroundColor Yellow
    $PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path $PythonExe)) { $PythonExe = "python" }
    & $PythonExe -m pytest tests/test_installer.py -q --timeout=30 --timeout-method=thread
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Installer tests failed!"
        exit $LASTEXITCODE
    }
    Write-Host "[OK] Pre-build installer tests passed." -ForegroundColor Green
}

# 5. Clean Old Setup Output if requested
$ReleaseDir = Join-Path $ProjectRoot "release"
if (-not (Test-Path $ReleaseDir)) {
    New-Item -ItemType Directory -Path $ReleaseDir | Out-Null
}
$SetupExe = Join-Path $ReleaseDir "Loadvia-Setup-1.1.0.exe"
if ($Clean -and (Test-Path $SetupExe)) {
    Remove-Item -Force $SetupExe
    Write-Host "Cleaned old installer: $SetupExe" -ForegroundColor Yellow
}

# 6. Compile Inno Setup Script
$IssScript = Join-Path $ProjectRoot "installer\Loadvia.iss"
Write-Host "Compiling Inno Setup script ($IssScript)..." -ForegroundColor Yellow
& $ResolvedIscc $IssScript
if ($LASTEXITCODE -ne 0) {
    Write-Error "Inno Setup compilation failed!"
    exit $LASTEXITCODE
}

# 7. Verify Output Setup Executable
if (-not (Test-Path $SetupExe)) {
    Write-Error "Setup EXE was not generated at $SetupExe!"
    exit 1
}

$SetupItem = Get-Item $SetupExe
Write-Host "=== Setup File Details ===" -ForegroundColor Cyan
Write-Host "Path      : $($SetupItem.FullName)"
Write-Host "Size      : $([math]::Round($SetupItem.Length / 1MB, 2)) MB"

# 8. Run Verification Script
$VerifyScript = Join-Path $PSScriptRoot "verify_installer.ps1"
if (Test-Path $VerifyScript) {
    Write-Host "Running verification..." -ForegroundColor Yellow
    & $VerifyScript -SetupPath $SetupExe
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Installer verification failed!"
        exit $LASTEXITCODE
    }
}

# 9. Print SHA-256 Hash
$Hash = (Get-FileHash $SetupExe -Algorithm SHA256).Hash
Write-Host "=== Build Completed Successfully ===" -ForegroundColor Green
Write-Host "Installer SHA-256: $Hash" -ForegroundColor Yellow
