$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
New-Item -ItemType Directory -Force -Path "$root\build" | Out-Null
$env:PYTHONDONTWRITEBYTECODE='1'
python.exe "$PSScriptRoot\test_tun.py" *> "$root\build\tun-test.log"
$LASTEXITCODE | Set-Content -LiteralPath "$root\build\tun-test.exit"
exit $LASTEXITCODE
