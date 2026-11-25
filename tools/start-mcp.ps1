$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding
$python = Join-Path $env:USERPROFILE 'AppData/Local/FrontierTraining/tools-venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    $python = Join-Path $env:LOCALAPPDATA 'FrontierTraining/tools-venv/Scripts/python.exe'
}
& $python -X utf8 (Join-Path $PSScriptRoot 'training_mcp.py')
exit $LASTEXITCODE
