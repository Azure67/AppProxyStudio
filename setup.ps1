param([string]$Python='python.exe')
$ErrorActionPreference='Stop'
$root=$PSScriptRoot
$env:PYTHONDONTWRITEBYTECODE='1'
$env:TEMP=Join-Path $root 'build\tmp'
$env:TMP=$env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP,(Join-Path $root 'core') | Out-Null
& $Python -m pip install --target "$root\vendor" --cache-dir "$root\build\pip-cache" -r "$root\requirements.txt"
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
$core=Join-Path $root 'core\mihomo.exe'
if (!(Test-Path -LiteralPath $core)) {
    $archive=Join-Path $root 'build\mihomo-v1.19.1.zip'
    Invoke-WebRequest -Uri 'https://github.com/MetaCubeX/mihomo/releases/download/v1.19.1/mihomo-windows-amd64-compatible-v1.19.1.zip' -OutFile $archive
    $expected='DB7B4AB2447037A19839BC20DBBA40AE32292CB0E5F62191672579096265785D'
    if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne $expected) {throw 'Mihomo archive checksum mismatch'}
    $stage=Join-Path $root 'build\mihomo-extracted'
    Expand-Archive -LiteralPath $archive -DestinationPath $stage -Force
    $exe=@(Get-ChildItem -LiteralPath $stage -Filter '*.exe' -File)
    if ($exe.Count -ne 1) {throw 'Unexpected core archive contents'}
    Copy-Item -LiteralPath $exe[0].FullName -Destination $core
}
Write-Output 'Ready. Run run-source.ps1 or build.ps1.'
