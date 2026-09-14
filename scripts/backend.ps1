param([switch]$Test)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$backendPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $backendPython)) { throw 'Run npm run setup:backend first.' }
Push-Location (Join-Path $projectRoot 'backend')
try {
    if ($Test) { & $backendPython -m pytest -q } else { & $backendPython -m app }
    $result = $LASTEXITCODE
} finally { Pop-Location }
exit $result
