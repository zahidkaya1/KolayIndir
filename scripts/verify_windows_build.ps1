[CmdletBinding()]
param (
    [string]$ExePath = "dist\Loadvia\Loadvia.exe"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

$FullExePath = (Get-Item $ExePath).FullName
$TargetDir = (Get-Item $FullExePath).Directory.FullName

Write-Host "=== Loadvia Windows Build Verification ===" -ForegroundColor Cyan

# 1. Verify Executable File
if (-not (Test-Path $FullExePath)) {
    Write-Error "Executable not found: $FullExePath"
    exit 1
}

$ExeItem = Get-Item $FullExePath
if ($ExeItem.Length -le 0) {
    Write-Error "Executable size is 0 bytes: $FullExePath"
    exit 1
}
Write-Host "[OK] Executable size: $([math]::Round($ExeItem.Length / 1MB, 2)) MB" -ForegroundColor Green

# 2. Verify Version Metadata
$VerInfo = $ExeItem.VersionInfo
if ($VerInfo.ProductName -ne "Loadvia") {
    Write-Error "ProductName is '$($VerInfo.ProductName)', expected 'Loadvia'"
    exit 1
}
if ($VerInfo.FileVersion -ne "1.2.0.0") {
    Write-Error "FileVersion is '$($VerInfo.FileVersion)', expected '1.2.0.0'"
    exit 1
}
Write-Host "[OK] Version metadata verified (ProductName: Loadvia, FileVersion: 1.2.0.0)" -ForegroundColor Green

# 3. Verify Brand Assets Structure
$AssetDir = Join-Path $TargetDir "assets\Loadvia-Brand-Assets"
if (-not (Test-Path $AssetDir)) {
    $AssetDir = Join-Path $TargetDir "_internal\assets\Loadvia-Brand-Assets"
}
$RequiredAssets = @("loadvia.ico", "loadvia-logo.png", "loadvia-symbol.png")
foreach ($asset in $RequiredAssets) {
    $ap = Join-Path $AssetDir $asset
    if (-not (Test-Path $ap)) {
        Write-Error "Required brand asset missing in dist: $ap"
        exit 1
    }
}
Write-Host "[OK] Brand assets directory structure verified." -ForegroundColor Green

# 4. Verify External Tools
$ToolsDir = Join-Path $TargetDir "tools"
$RequiredTools = @("ffmpeg.exe", "ffprobe.exe", "deno.exe")
foreach ($tool in $RequiredTools) {
    $tp = Join-Path $ToolsDir $tool
    if (-not (Test-Path $tp)) {
        Write-Error "Required external tool missing in dist: $tp"
        exit 1
    }
}
Write-Host "[OK] External tools (ffmpeg, ffprobe, deno) verified." -ForegroundColor Green

# 5. Process Execution Smoke Test
Write-Host "Launching Loadvia.exe process smoke test..." -ForegroundColor Yellow
$Process = Start-Process -FilePath $FullExePath -PassThru

# Wait 8 seconds to check for immediate crash/exit
Start-Sleep -Seconds 8

if ($Process.HasExited) {
    $ExitCode = $Process.ExitCode
    Write-Error "Loadvia.exe process exited prematurely within 8s! ExitCode: $ExitCode"
    exit 1
}

Write-Host "[OK] Loadvia.exe process launched and running stably." -ForegroundColor Green

# Safely close process
try {
    $Process.CloseMainWindow() | Out-Null
    Start-Sleep -Seconds 2
    if (-not $Process.HasExited) {
        Stop-Process -Id $Process.Id -Force
    }
} catch {
    Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
}

Write-Host "=== All Verification Checks Passed ===" -ForegroundColor Green
