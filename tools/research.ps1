# Pass public search terms or identifiers to the project's dedicated interpreter.
$ErrorActionPreference = 'Stop'
$candidates = @(
    (Join-Path $env:LOCALAPPDATA 'FrontierTraining'),
    (Join-Path $env:USERPROFILE 'AppData/Local/FrontierTraining')
)
foreach ($root in $candidates) {
    $python = Join-Path $root 'tools-venv/Scripts/python.exe'
    if (Test-Path -LiteralPath $python) {
        & $python -X utf8 (Join-Path $PSScriptRoot 'research_sources.py') @args
        exit $LASTEXITCODE
    }
}
throw 'Research Python environment missing. See docs/TOOLS.md.'
