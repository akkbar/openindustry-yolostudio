$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$buildRoot = Join-Path $projectRoot '.tools\backend-build'
$bundleRoot = Join-Path $projectRoot 'artifacts'
$buildPython = Join-Path $buildRoot 'Scripts\python.exe'

Push-Location $projectRoot
try {
    if (-not (Test-Path -LiteralPath $buildPython)) {
        py -3.10 -m venv $buildRoot
        if ($LASTEXITCODE -ne 0) { throw 'Python 3.10 is required to create the backend build environment.' }
    }
    @'
import struct
import sys
assert sys.platform == "win32" and struct.calcsize("P") == 8 and sys.version_info[:2] == (3, 10), "Build requires Windows x64 and Python 3.10."
'@ | & $buildPython -
    if ($LASTEXITCODE -ne 0) { throw 'Unsupported backend build environment.' }
    & $buildPython -m pip install --disable-pip-version-check -q -r backend/requirements-build.lock
    if ($LASTEXITCODE -ne 0) { throw 'Backend build dependency installation failed.' }

    $previousCache = $env:PYINSTALLER_CONFIG_DIR
    $previousYoloAutoInstall = $env:YOLO_AUTOINSTALL
    $env:PYINSTALLER_CONFIG_DIR = Join-Path $buildRoot 'cache'
    $env:YOLO_AUTOINSTALL = 'False'
    try {
        & $buildPython -m PyInstaller --noconfirm --clean --distpath $bundleRoot --workpath (Join-Path $buildRoot 'work') backend/packaging/backend.spec
        if ($LASTEXITCODE -ne 0) { throw 'Backend executable build failed.' }
    } finally {
        $env:PYINSTALLER_CONFIG_DIR = $previousCache
        $env:YOLO_AUTOINSTALL = $previousYoloAutoInstall
    }

    $output = Join-Path $bundleRoot 'backend'
    Copy-Item -LiteralPath 'installer\backend-poc-README.md' -Destination (Join-Path $bundleRoot 'README.md') -Force
    Copy-Item -LiteralPath 'scripts\test-backend-bundle.ps1' -Destination (Join-Path $bundleRoot 'Test-Backend.ps1') -Force
    $qaImages = Join-Path $bundleRoot 'qa-images'
    New-Item -ItemType Directory -Path $qaImages -Force | Out-Null
    foreach ($name in @('sample.jpg', 'sample.jpeg', 'sample.png', 'sample.webp')) {
        Copy-Item -LiteralPath (Join-Path 'tests\fixtures\images' $name) -Destination (Join-Path $qaImages $name) -Force
    }
    $files = @(Get-ChildItem -LiteralPath $output -File -Recurse | Sort-Object FullName | ForEach-Object {
        [ordered]@{
            path = $_.FullName.Substring($bundleRoot.Length + 1).Replace('\', '/')
            bytes = $_.Length
            sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    })
    $manifest = [ordered]@{
        product = 'Vision Studio Backend'
        phase = 26
        version = '0.1.0'
        platform = 'windows-x64'
        packaging = 'PyInstaller one-directory'
        built_at_utc = [DateTime]::UtcNow.ToString('o')
        python = (& $buildPython -c 'import platform; print(platform.python_version())')
        pyinstaller = (& $buildPython -m PyInstaller --version)
        files = $files
    }
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText((Join-Path $bundleRoot 'backend-manifest.json'), ($manifest | ConvertTo-Json -Depth 6), $utf8)
    $archive = Join-Path $bundleRoot 'VisionStudio-Backend-0.1.0-windows-x64.zip'
    & $buildPython scripts/package-backend.py
    if ($LASTEXITCODE -ne 0) { throw 'Backend QA archive creation failed.' }
    $archiveHash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
    [System.IO.File]::WriteAllText("$archive.sha256", "$archiveHash  $([System.IO.Path]::GetFileName($archive))`n", $utf8)
    Write-Host "Backend bundle: $output"
    Write-Host "Portable QA archive: $archive"
} finally { Pop-Location }
