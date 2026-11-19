$ErrorActionPreference='Stop'
$env:PYTHONPATH="$PSScriptRoot\vendor;$PSScriptRoot\src"
$env:PYTHONDONTWRITEBYTECODE='1'
python.exe "$PSScriptRoot\src\app.py"
exit $LASTEXITCODE
