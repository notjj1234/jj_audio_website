#Requires -Version 5.1
<#
.SYNOPSIS
  Compile AudioTools-<version>-windows-x64-<cpu|cuda>-setup.exe with Inno Setup.

.EXAMPLE
  .\packaging\make_windows_installer.ps1 -Flavor cpu -CopyToDownloads
  .\packaging\make_windows_installer.ps1 -Flavor cuda -CopyToDownloads
#>
[CmdletBinding()]
param(
    [string]$DistDir = "",
    [string]$OutputDir = "",
    [string]$AppVersion = "",
    [ValidateSet("cpu", "cuda")]
    [string]$Flavor = "cpu",
    [switch]$CopyToDownloads
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")

if (-not $AppVersion) {
    $AppVersion = & python -c "import sys; sys.path.insert(0, 'src'); from audio_to_tab import __version__; print(__version__)"
    if ($LASTEXITCODE -ne 0 -or -not $AppVersion) {
        throw "Could not read audio_to_tab.__version__ (activate the desktop venv and pip install -e . first)."
    }
}
$Iss = Join-Path $PSScriptRoot "AudioTools.iss"
$Flavor = $Flavor.ToLowerInvariant()

if (-not $DistDir) {
    $DistDir = Join-Path $Root "dist\AudioTools"
}
if (-not $OutputDir) {
    $OutputDir = Join-Path $Root "dist"
}

$Exe = Join-Path $DistDir "AudioTools.exe"
if (-not (Test-Path $Exe)) {
    throw "Missing $Exe — run: pyinstaller packaging/audio_tools.spec --noconfirm --clean"
}

function Find-ISCC {
    $candidates = @(
        "${env:ProgramFiles}\Inno Setup 7\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 7\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "${env:LocalAppData}\Programs\Inno Setup 7\ISCC.exe",
        "${env:LocalAppData}\Programs\Inno Setup 6\ISCC.exe"
    )
    foreach ($c in $candidates) {
        if ($c -and (Test-Path $c)) { return $c }
    }
    $cmd = Get-Command iscc -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

$ISCC = Find-ISCC
if (-not $ISCC) {
    throw @"
Inno Setup compiler (ISCC.exe) not found.
Install from https://jrsoftware.org/isinfo.php then re-run this script.
"@
}

New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

# Absolute paths for ISCC /D defines (forward slashes avoid escape issues)
$DistAbs = (Resolve-Path $DistDir).Path -replace '\\', '/'
$OutAbs = (Resolve-Path $OutputDir).Path -replace '\\', '/'

Write-Host "ISCC:     $ISCC"
Write-Host "DistDir:  $DistAbs"
Write-Host "OutputDir:$OutAbs"
Write-Host "Version:  $AppVersion"
Write-Host "Flavor:   $Flavor"

& $ISCC `
    "/DDistDir=$DistAbs" `
    "/DOutputDir=$OutAbs" `
    "/DAppVersion=$AppVersion" `
    "/DFlavor=$Flavor" `
    $Iss

if ($LASTEXITCODE -ne 0) {
    throw "ISCC failed with exit code $LASTEXITCODE"
}

$SetupName = "AudioTools-$AppVersion-windows-x64-$Flavor-setup.exe"
$Setup = Join-Path $OutputDir $SetupName
if (-not (Test-Path $Setup)) {
    throw "Expected installer missing: $Setup"
}

$sizeMb = [math]::Round((Get-Item $Setup).Length / 1MB, 1)
Write-Host "Built $Setup ($sizeMb MB)"

if ($CopyToDownloads) {
    $dest = Join-Path $env:USERPROFILE "Downloads\$SetupName"
    Copy-Item -Path $Setup -Destination $dest -Force
    Write-Host "Copied to $dest"
    try {
        explorer.exe "/select,$dest"
    } catch {
        # non-fatal
    }
}

exit 0
