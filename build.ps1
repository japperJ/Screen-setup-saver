param(
    [string]$Version = "1.0.0"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

$buildDir = Join-Path $repoRoot "build"
$distDir = Join-Path $repoRoot "dist"
$appDistDir = Join-Path $distDir "app"
$installerDistDir = Join-Path $distDir "installer"
$pyiWorkDir = Join-Path $buildDir "pyinstaller"

Write-Host "Building Screen Setup Saver ($Version)..."

if (Test-Path $appDistDir) {
    Remove-Item $appDistDir -Recurse -Force
}
if (-not (Test-Path $installerDistDir)) {
    New-Item -ItemType Directory -Path $installerDistDir | Out-Null
}

python -m pip install --upgrade pyinstaller

$pyinstallerArgs = @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--name", "ScreenSetupSaver",
    "--noconsole",
    "--distpath", $appDistDir,
    "--workpath", $pyiWorkDir,
    "--specpath", $buildDir
)

$iconPath = Join-Path $repoRoot "assets\icon.ico"
if (Test-Path $iconPath) {
    $pyinstallerArgs += @("--icon", $iconPath)
}

$pyinstallerArgs += "main.py"

# Write version.py so PyInstaller bundles it and the running app can display it
Set-Content -Path (Join-Path $repoRoot "version.py") -Value "__version__ = '$Version'"

python @pyinstallerArgs

$candidateExePaths = @(
    (Join-Path $appDistDir "ScreenSetupSaver.exe"),
    (Join-Path (Join-Path $appDistDir "ScreenSetupSaver") "ScreenSetupSaver.exe")
)
$exePath = $candidateExePaths | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $exePath) {
    $expected = $candidateExePaths -join "; "
    throw "Build failed: expected executable not found. Checked: $expected"
}
$appPayloadDir = Split-Path -Parent $exePath

$programFiles = $env:ProgramFiles
$programFilesX86 = ${env:ProgramFiles(x86)}

$makensisCandidates = @(
    (Join-Path $programFiles "NSIS\makensis.exe"),
    (Join-Path $programFilesX86 "NSIS\makensis.exe")
)
$makensis = $makensisCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $makensis) {
    $makensisCmd = Get-Command "makensis.exe" -ErrorAction SilentlyContinue
    if ($makensisCmd) {
        $makensis = $makensisCmd.Source
    }
}

if (-not $makensis) {
    Write-Warning "NSIS compiler (makensis.exe) not found. Skipping installer build."
    Write-Host "Standalone executable is available at: $exePath"
    exit 0
}

$nsisScript = Join-Path $repoRoot "installer\ScreenSetupSaver.nsi"
if (-not (Test-Path $nsisScript)) {
    throw "Installer script not found: $nsisScript"
}

& $makensis "/DAPP_VERSION=$Version" "/DAPP_EXE_PATH=$exePath" "/DAPP_DIST_DIR=$appPayloadDir" $nsisScript
if ($LASTEXITCODE -ne 0) {
    throw "NSIS build failed with exit code $LASTEXITCODE"
}

Write-Host "Done."
Write-Host "Executable: $exePath"
Write-Host "Installer output: .\dist\installer"
