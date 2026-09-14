$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Push-Location $projectRoot
try {
    if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
        py -3 -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Python virtual environment creation failed.' }
    }
    & '.\.venv\Scripts\python.exe' -m pip install -r backend/requirements-dev.lock
    if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }
    & '.\.venv\Scripts\python.exe' -m pip install --no-deps -e './backend'
    if ($LASTEXITCODE -ne 0) { throw 'Backend package installation failed.' }
} finally { Pop-Location }
