$ErrorActionPreference='Stop'
$projectRoot=$PSScriptRoot
$python=(Get-Command python.exe).Source
if (!(Test-Path -LiteralPath "$projectRoot\vendor\PyInstaller")) {throw '先按 README 安装项目本地依赖'}
$env:PYTHONPATH="$projectRoot\vendor;$projectRoot\src"
$env:TEMP="$projectRoot\build\tmp"
$env:TMP=$env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
$env:PYINSTALLER_CONFIG_DIR="$projectRoot\build\pyinstaller-cache"
$env:PYTHONDONTWRITEBYTECODE='1'
& $python -m PyInstaller --noconfirm --clean --windowed --onedir --name AppProxyStudio --icon "$projectRoot\assets\app.ico" --contents-directory _runtime --paths "$projectRoot\vendor" --paths "$projectRoot\src" --distpath "$projectRoot\app" --workpath "$projectRoot\build\pyinstaller" --specpath "$projectRoot\build" "$projectRoot\src\app.py"
if ($LASTEXITCODE -ne 0) {throw '打包失败'}
# Qt 6 uses Windows' system ICU. Do not ship a foreign ICU from Poppler/Conda on PATH.
$runtime=Join-Path $projectRoot 'app\AppProxyStudio\_runtime'
$quarantine=Join-Path $projectRoot 'build\excluded-dlls'
New-Item -ItemType Directory -Force -Path $quarantine | Out-Null
foreach ($name in @('icuuc.dll','icudt78.dll')) {
    $source=Join-Path $runtime $name
    if (Test-Path -LiteralPath $source) {Move-Item -LiteralPath $source -Destination (Join-Path $quarantine $name) -Force}
}
