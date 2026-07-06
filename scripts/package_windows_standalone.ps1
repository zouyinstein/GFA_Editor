param(
    [string]$RootDir = "",
    [string]$Python = "",
    [string]$Version = "1.3.3",
    [switch]$SkipToolCollect
)

$ErrorActionPreference = "Stop"

if ($RootDir -eq "") {
    $RootDir = Resolve-Path (Join-Path $PSScriptRoot "..")
} else {
    $RootDir = Resolve-Path $RootDir
}

if ($Python -eq "") {
    $DefaultPython = Join-Path $env:LOCALAPPDATA "Programs\Python\Python311-x64\python.exe"
    $Python = if (Test-Path $DefaultPython) { $DefaultPython } else { "python" }
}

& $Python -c "import platform,sys; print(sys.executable); print(platform.machine()); print(platform.architecture()[0])"
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$BuildDir = Join-Path $env:TEMP ("GFA_Editor_windows_standalone_" + (Get-Date -Format "yyyyMMddHHmmss"))
New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null

robocopy $RootDir $BuildDir /E /XD .git .venv build dist .pytest_cache .pyinstaller __pycache__ server_data .local /XF uvicorn.log .DS_Store
$CopyCode = $LASTEXITCODE
if ($CopyCode -gt 7) {
    throw "robocopy failed with exit code $CopyCode"
}

Set-Location $BuildDir

$BuildArgs = @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    ".\scripts\build_windows_exe.ps1",
    "-Python",
    $Python
)
if ($SkipToolCollect) {
    $BuildArgs += "-SkipToolCollect"
}

& powershell.exe @BuildArgs
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$ExePath = Join-Path $BuildDir "dist\GFA_Editor\GFA_Editor.exe"
if (-not (Test-Path $ExePath)) {
    throw "Missing built executable: $ExePath"
}

$ReadmePath = Join-Path $BuildDir "dist\GFA_Editor\README_WINDOWS_START.txt"
@"
GFA Editor Windows standalone
=============================

Important:
1. Extract this zip archive first. Do not run GFA_Editor.exe from inside the Windows zip preview.
2. Keep GFA_Editor.exe and the _internal folder together in the same GFA_Editor directory.
3. Start the app by double-clicking GFA_Editor.exe after extraction.

Bundled alignment tools:
- minimap2 2.31-r1302 for Windows x86_64
- NCBI BLAST+ blastn 2.17.0+

If the app fails to start, check:
%USERPROFILE%\GFAEditorData\desktop.log
%USERPROFILE%\GFAEditorData\desktop-runtime.log
"@ | Set-Content -Path $ReadmePath -Encoding UTF8

$OutputZip = Join-Path $RootDir "dist\GFA_Editor-v$Version-windows-x86_64-standalone.zip"
Compress-Archive -Path ".\dist\GFA_Editor" -DestinationPath $OutputZip -Force

Write-Host ""
Write-Host "Windows standalone package complete."
Get-Item $OutputZip | Select-Object FullName,Length
