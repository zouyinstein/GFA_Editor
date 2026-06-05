param(
    [string]$Python = "",
    [switch]$SkipToolCollect
)

$ErrorActionPreference = "Stop"
$RootDir = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RootDir

if (-not [Environment]::Is64BitOperatingSystem) {
    throw "This build script targets Windows x86_64. Please run it on 64-bit Windows."
}

if ($Python -eq "") {
    $VenvPython = Join-Path $RootDir ".venv\Scripts\python.exe"
    if (Test-Path $VenvPython) {
        $Python = $VenvPython
    } else {
        $Python = "python"
    }
}

if (-not (Test-Path ".venv")) {
    & $Python -m venv .venv
    $Python = Join-Path $RootDir ".venv\Scripts\python.exe"
}

& $Python -m pip install --upgrade pip
& $Python -m pip install -r backend\requirements.txt
& $Python -m pip install -r packaging\requirements-desktop.txt

if (-not $SkipToolCollect) {
    & $Python scripts\collect_alignment_tools.py
}

& $Python scripts\generate_app_icons.py

$env:PYINSTALLER_CONFIG_DIR = Join-Path $RootDir ".pyinstaller"
New-Item -ItemType Directory -Force -Path $env:PYINSTALLER_CONFIG_DIR | Out-Null

& $Python -m PyInstaller --noconfirm packaging\pyinstaller\gfa_editor_desktop.spec

Write-Host ""
Write-Host "Windows build complete."
Write-Host "Executable: dist\GFA_Editor\GFA_Editor.exe"
Write-Host ""
Write-Host "Share the whole dist\GFA_Editor folder, not only the .exe, because it contains bundled runtime files."
