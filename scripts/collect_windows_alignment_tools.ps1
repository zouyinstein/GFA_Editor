param(
    [string]$RootDir = ""
)

$ErrorActionPreference = "Stop"

if ($RootDir -eq "") {
    $RootDir = Resolve-Path (Join-Path $PSScriptRoot "..")
} else {
    $RootDir = Resolve-Path $RootDir
}

$DestDir = Join-Path $RootDir "packaging\bin\windows-x86_64"
New-Item -ItemType Directory -Force -Path $DestDir | Out-Null

$WorkDir = Join-Path $env:TEMP ("gfa_editor_windows_tools_" + (Get-Date -Format "yyyyMMddHHmmss"))
New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null

function Invoke-Download {
    param(
        [string]$Url,
        [string]$OutputPath
    )
    & curl.exe -L -o $OutputPath $Url
    if ($LASTEXITCODE -ne 0) {
        throw "Download failed: $Url"
    }
}

function Assert-Hash {
    param(
        [string]$Path,
        [string]$Algorithm,
        [string]$Expected
    )
    $Actual = (Get-FileHash $Path -Algorithm $Algorithm).Hash.ToLowerInvariant()
    if ($Actual -ne $Expected.ToLowerInvariant()) {
        throw "$Algorithm mismatch for $Path; expected $Expected got $Actual"
    }
    Write-Host "$Algorithm $Actual  $Path"
}

$MinimapUrl = "https://github.com/win-ngs/minimap2-windows-build/releases/download/v2.31-r1302/minimap2-2.31-r1302-windows-x86_64-ucrt64.zip"
$MinimapSha256 = "986397b28c170d00a9d16977897914d367e4a6b08c26f9ce1b44813b88015ba4"
$MinimapZip = Join-Path $WorkDir "minimap2-2.31-r1302-windows-x86_64-ucrt64.zip"
$MinimapDir = Join-Path $WorkDir "minimap2"
Invoke-Download $MinimapUrl $MinimapZip
Assert-Hash $MinimapZip "SHA256" $MinimapSha256
Expand-Archive -Path $MinimapZip -DestinationPath $MinimapDir -Force

foreach ($Name in @("minimap2.exe", "libwinpthread-1.dll", "zlib1.dll")) {
    $File = Get-ChildItem $MinimapDir -Recurse -File -Filter $Name | Select-Object -First 1
    if (-not $File) {
        throw "Missing $Name in minimap2 archive"
    }
    Copy-Item $File.FullName (Join-Path $DestDir $Name) -Force
}

$BlastUrl = "https://ftp.ncbi.nlm.nih.gov/blast/executables/blast+/LATEST/ncbi-blast-2.17.0+-x64-win64.tar.gz"
$BlastArchive = Join-Path $WorkDir "ncbi-blast-2.17.0+-x64-win64.tar.gz"
$BlastMd5File = Join-Path $WorkDir "ncbi-blast-2.17.0+-x64-win64.tar.gz.md5"
$BlastDir = Join-Path $WorkDir "blast"
Invoke-Download $BlastUrl $BlastArchive
Invoke-Download "$BlastUrl.md5" $BlastMd5File
$ExpectedBlastMd5 = ((Get-Content $BlastMd5File -Raw) -split "\s+")[0]
Assert-Hash $BlastArchive "MD5" $ExpectedBlastMd5

New-Item -ItemType Directory -Force -Path $BlastDir | Out-Null
& tar.exe -xzf $BlastArchive -C $BlastDir
if ($LASTEXITCODE -ne 0) {
    throw "Failed to extract BLAST archive"
}

$BlastExe = Get-ChildItem $BlastDir -Recurse -File -Filter "blastn.exe" | Select-Object -First 1
if (-not $BlastExe) {
    throw "Missing blastn.exe in BLAST archive"
}
$BlastBin = $BlastExe.Directory.FullName
Copy-Item $BlastExe.FullName (Join-Path $DestDir "blastn.exe") -Force
Get-ChildItem $BlastBin -File -Filter "*.dll" | ForEach-Object {
    Copy-Item $_.FullName (Join-Path $DestDir $_.Name) -Force
}

Write-Host ""
Write-Host "Collected Windows alignment tools:"
Get-ChildItem $DestDir | Sort-Object Name | Select-Object Name,Length
Write-Host ""
& (Join-Path $DestDir "minimap2.exe") --version
& (Join-Path $DestDir "blastn.exe") -version
