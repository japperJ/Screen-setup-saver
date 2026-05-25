param(
    [string]$Version = "1.0.0"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

$buildDir = Join-Path $repoRoot "build"
$distDir = Join-Path $repoRoot "dist"
$appDistDir = Join-Path $distDir "app"
$pyiWorkDir = Join-Path $buildDir "pyinstaller"

Write-Host "Building Screen Setup Saver ($Version)..."

if (Test-Path $appDistDir) {
    Remove-Item $appDistDir -Recurse -Force
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

$isccCandidates = @(
    "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
)
$iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $iscc) {
    Write-Warning "Inno Setup compiler (ISCC.exe) not found. Skipping installer build."
    Write-Host "Standalone executable is available at: $exePath"
    exit 0
}

& $iscc "/DAppVersion=$Version" "/DAppExePath=$exePath" ".\installer\ScreenSetupSaver.iss"

Write-Host "Done."
Write-Host "Executable: $exePath"
Write-Host "Installer output: .\dist\installer"
