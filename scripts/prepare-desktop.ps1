$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'build-backend.ps1')
if (-not $?) { exit 1 }
Push-Location (Split-Path $PSScriptRoot -Parent)
try { npm.cmd run build; $result = $LASTEXITCODE } finally { Pop-Location }
exit $result
