param(
    [string]$Python = "python",
    [string]$VenvPath = ".venv-windows-build",
    [switch]$ReuseVenv,
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$AppVersion = "2.0"

function Run-Step {
    param(
        [string]$Message,
        [scriptblock]$Action
    )

    Write-Host "[+] $Message"
    & $Action
}

# Ensure we work from repository root
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptRoot "..") | Select-Object -ExpandProperty Path
Set-Location $repoRoot

if (-not $ReuseVenv -and (Test-Path $VenvPath)) {
    Remove-Item -Recurse -Force $VenvPath
}

if (-not (Test-Path $VenvPath)) {
    Run-Step -Message "Creating virtual environment at $VenvPath" -Action {
        & $Python -m venv $VenvPath
    }
}

$venvPython = Join-Path $VenvPath "Scripts/python.exe"
if (-not (Test-Path $venvPython)) {
    throw "Unable to locate venv python at $venvPython"
}

Run-Step -Message "Upgrading pip" -Action {
    & $venvPython -m pip install --upgrade pip
}

Run-Step -Message "Installing runtime dependencies" -Action {
    & $venvPython -m pip install -r requirements.txt
}

Run-Step -Message "Installing PyInstaller" -Action {
    & $venvPython -m pip install pyinstaller
}

$distPath = Join-Path $repoRoot "dist/JointSpaceVisualizer"
if (Test-Path $distPath) {
    Run-Step -Message "Removing previous dist output" -Action {
        Remove-Item -Recurse -Force $distPath
    }
}

Run-Step -Message "Building PyInstaller app" -Action {
    & $venvPython -m PyInstaller JointSpaceVisualizer.spec --clean
}

if (-not (Test-Path (Join-Path $distPath "JointSpaceVisualizer.exe"))) {
    throw "PyInstaller output missing at $distPath"
}

if ($SkipInstaller) {
    Write-Host "[+] SkipInstaller set, leaving PyInstaller directory build only"
    exit 0
}

$makensis = Get-Command "makensis.exe" -ErrorAction SilentlyContinue
if (-not $makensis) {
    throw "makensis.exe not found in PATH. Install NSIS from https://nsis.sourceforge.io/Download and ensure makensis.exe is discoverable."
}

$installerScript = Join-Path $repoRoot "installer/windows/JointSpaceVisualizer.nsi"
if (-not (Test-Path $installerScript)) {
    throw "Installer script missing at $installerScript"
}

Run-Step -Message "Packaging NSIS installer" -Action {
    $rootDefine = ($repoRoot -replace "\\", "\\\\")
    & $makensis.Path "/DROOT_DIR=$rootDefine" "/DAPP_VERSION=$AppVersion" $installerScript
}

Write-Host "[+] Installer written to" (Join-Path $repoRoot "installer/windows/JointSpaceVisualizerSetup.exe")
