[CmdletBinding()]
param (
    [string]$SetupPath = "release\Loadvia-Setup-1.2.0.exe",
    [switch]$InstallSmokeTest
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

Write-Host "=== Loadvia Windows Installer Verification ===" -ForegroundColor Cyan

# 1. Verify Setup File Existence and Size
$FullSetupPath = Resolve-Path $SetupPath -ErrorAction SilentlyContinue
if (-not $FullSetupPath -or -not (Test-Path $FullSetupPath)) {
    Write-Error "Setup file not found: $SetupPath"
    exit 1
}

$SetupItem = Get-Item $FullSetupPath
if ($SetupItem.Length -le 0) {
    Write-Error "Setup file size is 0 bytes: $SetupPath"
    exit 1
}
Write-Host "[OK] Setup file size: $([math]::Round($SetupItem.Length / 1MB, 2)) MB" -ForegroundColor Green

# 2. Verify SHA-256 Calculation
$Hash = (Get-FileHash $FullSetupPath -Algorithm SHA256).Hash
if (-not $Hash) {
    Write-Error "Failed to calculate SHA-256 hash for setup file."
    exit 1
}
Write-Host "[OK] SHA-256 calculated: $Hash" -ForegroundColor Green

# 3. Verify Version Metadata
$VerInfo = $SetupItem.VersionInfo
$ProductName = if ($VerInfo.ProductName) { $VerInfo.ProductName.Trim() } else { "" }
if ($ProductName -ne "Loadvia") {
    Write-Error "Setup ProductName is '$($VerInfo.ProductName)', expected 'Loadvia'"
    exit 1
}
$FileVersion = if ($VerInfo.FileVersion) { $VerInfo.FileVersion.Trim() } else { "" }
if ($FileVersion -ne "1.2.0.0") {
    Write-Error "Setup FileVersion is '$($VerInfo.FileVersion)', expected '1.2.0.0'"
    exit 1
}
Write-Host "[OK] Setup version metadata verified (ProductName: Loadvia, FileVersion: 1.2.0.0)" -ForegroundColor Green

# 4. Verify ISS Script Safeguards
$IssPath = Join-Path $ProjectRoot "installer\Loadvia.iss"
if (-not (Test-Path $IssPath)) {
    Write-Error "ISS script missing at $IssPath"
    exit 1
}

$IssContent = Get-Content $IssPath -Raw -Encoding UTF8

if ($IssContent -notlike "*AppId={{6411DE40-247B-45E7-9345-73DCCAF9DA69}*") {
    Write-Error "Fixed AppId missing or modified in Loadvia.iss!"
    exit 1
}
if ($IssContent -notmatch 'Source:\s*"\.\.\\dist\\Loadvia\\\*"' -or $IssContent -notmatch 'recursesubdirs') {
    Write-Error "Source dist\Loadvia recursive rule missing in Loadvia.iss!"
    exit 1
}
if ($IssContent -match '\[UninstallDelete\]') {
    Write-Error "[UninstallDelete] section found in Loadvia.iss! Danger of deleting user data!"
    exit 1
}
if ($IssContent -notmatch 'ArchitecturesAllowed=x64compatible') {
    Write-Error "x64 architecture limit directive missing in Loadvia.iss!"
    exit 1
}
if ($IssContent -notmatch 'skipifsilent') {
    Write-Error "skipifsilent flag missing in Loadvia.iss [Run] section!"
    exit 1
}
Write-Host "[OK] Inno Setup script safeguards verified." -ForegroundColor Green

# 5. Optional Smoke Test (only if explicitly requested via -InstallSmokeTest)
if ($InstallSmokeTest) {
    Write-Host "Running optional isolated install smoke test..." -ForegroundColor Yellow

    $TempInstallDir = Join-Path $env:TEMP "LoadviaSmokeTestInstall"
    if (Test-Path $TempInstallDir) { Remove-Item -Recurse -Force $TempInstallDir }

    # Run silent installation to temp dir
    $Process = Start-Process -FilePath $FullSetupPath -ArgumentList "/VERYSILENT /SUPPRESSMSGBOXES /CURRENTUSER /NOICONS /DIR=`"$TempInstallDir`"" -PassThru -Wait

    $InstalledExe = Join-Path $TempInstallDir "Loadvia.exe"
    if (-not (Test-Path $InstalledExe)) {
        Write-Error "Smoke installation failed to create Loadvia.exe at $InstalledExe"
        exit 1
    }

    # Run installed app briefly
    $AppProc = Start-Process -FilePath $InstalledExe -PassThru
    Start-Sleep -Seconds 4
    if ($AppProc.HasExited) {
        Write-Error "Installed Loadvia.exe exited prematurely during smoke test!"
        exit 1
    }

    # Close app safely
    try {
        $AppProc.CloseMainWindow() | Out-Null
        Start-Sleep -Seconds 2
        if (-not $AppProc.HasExited) { Stop-Process -Id $AppProc.Id -Force }
    } catch {
        Stop-Process -Id $AppProc.Id -Force -ErrorAction SilentlyContinue
    }

    # Silent uninstall
    $Uninstaller = Join-Path $TempInstallDir "unins000.exe"
    if (Test-Path $Uninstaller) {
        Start-Process -FilePath $Uninstaller -ArgumentList "/VERYSILENT /SUPPRESSMSGBOXES" -Wait
    }
    if (Test-Path $TempInstallDir) { Remove-Item -Recurse -Force $TempInstallDir -ErrorAction SilentlyContinue }

    Write-Host "[OK] Isolated install smoke test passed." -ForegroundColor Green
}

Write-Host "=== All Verification Checks Passed ===" -ForegroundColor Green
