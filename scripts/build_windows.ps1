[CmdletBinding()]
param (
    [switch]$Clean,
    [switch]$DebugBuild,
    [string]$FfmpegPath,
    [string]$FfprobePath,
    [string]$DenoPath,
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

Write-Host "=== Loadvia 1.0.0 Windows Build Process ===" -ForegroundColor Cyan

# 1. Verify 64-bit Python
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    $PythonExe = "python"
}

$Arch = & $PythonExe -c "import struct; print(struct.calcsize('P') * 8)"
if ($Arch.Trim() -ne "64") {
    Write-Error "Build requires 64-bit Python. Current: ${Arch}-bit"
    exit 1
}
Write-Host "[OK] Python 64-bit verified." -ForegroundColor Green

# 2. Verify Brand Assets
$IconPath = Join-Path $ProjectRoot "assets\Loadvia-Brand-Assets\loadvia.ico"
if (-not (Test-Path $IconPath)) {
    Write-Error "Brand asset missing: $IconPath"
    exit 1
}
Write-Host "[OK] Brand assets verified." -ForegroundColor Green

# 3. Resolve External Binaries
function Resolve-ToolPath ([string]$GivenPath, [string]$ToolName) {
    if ($GivenPath -and (Test-Path $GivenPath)) {
        return (Get-Item $GivenPath).FullName
    }
    $Found = Get-Command $ToolName -ErrorAction SilentlyContinue
    if ($Found) {
        return $Found.Source
    }
    return $null
}

$ResolvedFfmpeg = Resolve-ToolPath $FfmpegPath "ffmpeg"
$ResolvedFfprobe = Resolve-ToolPath $FfprobePath "ffprobe"
$ResolvedDeno = Resolve-ToolPath $DenoPath "deno"

if (-not $ResolvedFfmpeg) { Write-Error "ffmpeg.exe not found! Please specify -FfmpegPath"; exit 1 }
if (-not $ResolvedFfprobe) { Write-Error "ffprobe.exe not found! Please specify -FfprobePath"; exit 1 }
if (-not $ResolvedDeno) { Write-Error "deno.exe not found! Please specify -DenoPath"; exit 1 }

Write-Host "[OK] ffmpeg : $ResolvedFfmpeg" -ForegroundColor Green
Write-Host "[OK] ffprobe: $ResolvedFfprobe" -ForegroundColor Green
Write-Host "[OK] deno   : $ResolvedDeno" -ForegroundColor Green

# 4. Pre-build Tests
if (-not $SkipTests) {
    Write-Host "Running pre-build tests..." -ForegroundColor Yellow
    & $PythonExe -m pytest tests/test_branding.py -q --timeout=30 --timeout-method=thread
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Pre-build branding tests failed!"
        exit $LASTEXITCODE
    }
    Write-Host "[OK] Pre-build tests passed." -ForegroundColor Green
}

# 5. Clean Previous Builds
if ($Clean) {
    Write-Host "Cleaning build/ and dist/ directories..." -ForegroundColor Yellow
    if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
    if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
}

# 6. PyInstaller Build
$SpecFile = Join-Path $ProjectRoot "packaging\Loadvia.spec"
if ($DebugBuild) {
    Write-Host "Building DEBUG executable (console=True)..." -ForegroundColor Yellow
    & $PythonExe -m PyInstaller --clean --noconfirm --name Loadvia-Debug $SpecFile
} else {
    Write-Host "Building RELEASE executable (console=False)..." -ForegroundColor Yellow
    & $PythonExe -m PyInstaller --clean --noconfirm $SpecFile
}

if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller build failed!"
    exit $LASTEXITCODE
}

# 7. Copy External Binaries to dist/Loadvia/tools/
$TargetDir = Join-Path $ProjectRoot "dist\Loadvia"
if (-not (Test-Path $TargetDir)) {
    Write-Error "Build target directory not found: $TargetDir"
    exit 1
}

$ToolsDir = Join-Path $TargetDir "tools"
if (-not (Test-Path $ToolsDir)) {
    New-Item -ItemType Directory -Path $ToolsDir | Out-Null
}

Copy-Item -Path $ResolvedFfmpeg -Destination (Join-Path $ToolsDir "ffmpeg.exe") -Force
Copy-Item -Path $ResolvedFfprobe -Destination (Join-Path $ToolsDir "ffprobe.exe") -Force
Copy-Item -Path $ResolvedDeno -Destination (Join-Path $ToolsDir "deno.exe") -Force

Write-Host "[OK] Copied external binaries into $ToolsDir" -ForegroundColor Green

# 7.1 Copy Brand Assets to top-level assets directory if needed
$TargetAssetDir = Join-Path $TargetDir "assets\Loadvia-Brand-Assets"
$SrcAssetDir = Join-Path $ProjectRoot "assets\Loadvia-Brand-Assets"
if (-not (Test-Path $TargetAssetDir)) {
    New-Item -ItemType Directory -Path (Join-Path $TargetDir "assets") -Force | Out-Null
    Copy-Item -Path $SrcAssetDir -Destination $TargetAssetDir -Recurse -Force
}

# 8. Verify Built Executable Metadata
$ExePath = Join-Path $TargetDir "Loadvia.exe"
if (-not (Test-Path $ExePath)) {
    Write-Error "Built executable missing: $ExePath"
    exit 1
}

$VersionInfo = (Get-Item $ExePath).VersionInfo
Write-Host "=== EXE Version Metadata ===" -ForegroundColor Cyan
Write-Host "FileDescription : $($VersionInfo.FileDescription)"
Write-Host "FileVersion     : $($VersionInfo.FileVersion)"
Write-Host "ProductName     : $($VersionInfo.ProductName)"
Write-Host "ProductVersion  : $($VersionInfo.ProductVersion)"
Write-Host "OriginalFilename: $($VersionInfo.OriginalFilename)"
Write-Host "CompanyName     : $($VersionInfo.CompanyName)"

# 9. Verify Smoke Test
$VerifyScript = Join-Path $PSScriptRoot "verify_windows_build.ps1"
if (Test-Path $VerifyScript) {
    Write-Host "Running smoke test..." -ForegroundColor Yellow
    & $VerifyScript -ExePath $ExePath
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Build verification / smoke test failed!"
        exit $LASTEXITCODE
    }
}

Write-Host "=== Build Completed Successfully ===" -ForegroundColor Green
