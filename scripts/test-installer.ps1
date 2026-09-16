$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$installer = Join-Path $projectRoot 'artifacts\OpenIndustry-Vision-Studio-QA-Setup.exe'
if (-not (Test-Path -LiteralPath $installer)) { throw 'Run npm run build:installer:qa first.' }
$desktopShortcut = Join-Path ([Environment]::GetFolderPath('Desktop')) 'OpenIndustry Vision Studio QA.lnk'
$uninstallRoots = @('HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall', 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall')
function Get-QaRegistration {
    @($uninstallRoots | ForEach-Object { Get-ItemProperty -Path "$_\*" -ErrorAction SilentlyContinue } | Where-Object { $_.DisplayName -eq 'OpenIndustry Vision Studio QA' })
}
if (@(Get-QaRegistration).Count -gt 0 -or (Test-Path -LiteralPath $desktopShortcut)) {
    throw 'An existing OpenIndustry Vision Studio QA installation or shortcut was found. The test will not overwrite it.'
}
$qaRoot = Join-Path $env:LOCALAPPDATA ('VisionStudio\qa\Installer ' + [Guid]::NewGuid().ToString('N'))
$target = Join-Path $qaRoot 'Installed application'
New-Item -ItemType Directory -Path $qaRoot | Out-Null
$sentinel = Join-Path $qaRoot 'user-data-preservation.txt'
Set-Content -LiteralPath $sentinel -Value 'Keep user data after uninstall.'
$report = [ordered]@{ passed = $false; mode = 'currentUser QA'; production_per_machine_verified = $false; clean_machine_verified = $false; install_directory = $target; checked_at_utc = [DateTime]::UtcNow.ToString('o'); checks = @() }
$checks = New-Object System.Collections.Generic.List[string]

function Assert-Installer([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw "Installer check failed: $Message" }
    $checks.Add($Message)
}

function Run-Setup([string]$Executable, [string]$Arguments) {
    $start = New-Object System.Diagnostics.ProcessStartInfo
    $start.FileName = $Executable
    $start.Arguments = $Arguments
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $process = [System.Diagnostics.Process]::Start($start)
    try {
        if (-not $process.WaitForExit(60000)) { throw 'Installer did not finish within 60 seconds.' }
        return $process.ExitCode
    } finally { $process.Dispose() }
}

try {
    Assert-Installer ((Run-Setup $installer "/S /D=$target") -eq 0) 'Silent per-user installation succeeds without elevation.'
    $app = Join-Path $target 'OpenIndustry Vision Studio.exe'
    Assert-Installer (Test-Path -LiteralPath $app) 'The desktop executable is installed.'
    Assert-Installer (Test-Path -LiteralPath (Join-Path $target 'backend\backend.exe')) 'The backend executable is installed.'
    Assert-Installer (Test-Path -LiteralPath (Join-Path $target 'backend\_internal\python310.dll')) 'The bundled Python runtime is installed.'
    node (Join-Path $PSScriptRoot 'test-installed-payload.mjs') $app
    Assert-Installer ($LASTEXITCODE -eq 0) 'The installed desktop matches the release payload with the NSIS bundle marker.'
    $manifest = Get-Content -LiteralPath (Join-Path $projectRoot 'artifacts\backend-manifest.json') -Raw | ConvertFrom-Json
    foreach ($file in $manifest.files) {
        $installedFile = Join-Path $target $file.path
        if (-not (Test-Path -LiteralPath $installedFile) -or (Get-FileHash -LiteralPath $installedFile).Hash -ne $file.sha256) {
            throw "The installed backend file does not match its manifest: $($file.path)"
        }
    }
    Assert-Installer ($manifest.files.Count -gt 0) 'Every installed backend resource matches the build manifest.'
    Assert-Installer (Test-Path -LiteralPath $desktopShortcut) 'A desktop shortcut is created.'
    $shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut($desktopShortcut)
    Assert-Installer ($shortcut.TargetPath -eq $app) 'The shortcut targets the installed desktop executable.'
    Assert-Installer (@(Get-QaRegistration).Count -eq 1) 'The application is registered for uninstall.'
    Push-Location $projectRoot
    try {
        node scripts/test-desktop.mjs --installed $app
        Assert-Installer ($LASTEXITCODE -eq 0) 'The installed application opens, connects to its backend, and shuts down.'
    } finally { Pop-Location }
    $uninstaller = Join-Path $target 'uninstall.exe'
    Assert-Installer (Test-Path -LiteralPath $uninstaller) 'An uninstaller is installed.'
    Assert-Installer ((Run-Setup $uninstaller '/S') -eq 0) 'Silent uninstallation succeeds.'
    $deadline = [DateTime]::UtcNow.AddSeconds(20)
    # NSIS launches a temporary uninstaller process. Its original launcher can
    # exit before shortcut and registry cleanup, so wait for the full result.
    while ([DateTime]::UtcNow -lt $deadline) {
        $remaining = (Test-Path -LiteralPath $app) -or
            (Test-Path -LiteralPath (Join-Path $target 'backend\backend.exe')) -or
            (Test-Path -LiteralPath $desktopShortcut) -or @(Get-QaRegistration).Count -gt 0
        if (-not $remaining) { break }
        Start-Sleep -Milliseconds 200
    }
    Assert-Installer (-not (Test-Path -LiteralPath $app)) 'The desktop executable is removed.'
    Assert-Installer (-not (Test-Path -LiteralPath (Join-Path $target 'backend\backend.exe'))) 'The bundled backend is removed.'
    Assert-Installer (-not (Test-Path -LiteralPath $desktopShortcut)) 'The desktop shortcut is removed.'
    Assert-Installer (@(Get-QaRegistration).Count -eq 0) 'The uninstall registration is removed.'
    Assert-Installer ((Get-Content -LiteralPath $sentinel -Raw).Trim() -eq 'Keep user data after uninstall.') 'Uninstallation preserves user data.'
    $report['passed'] = $true
} catch {
    $report['error'] = $_.Exception.Message
    throw
} finally {
    if (-not $report['passed']) {
        $ownedUninstaller = Join-Path $target 'uninstall.exe'
        if (Test-Path -LiteralPath $ownedUninstaller) {
            try { $report['failure_cleanup_exit_code'] = Run-Setup $ownedUninstaller '/S' }
            catch { $report['failure_cleanup_error'] = $_.Exception.Message }
        }
    }
    $report['checks'] = @($checks.ToArray())
    $reportPath = Join-Path $projectRoot 'artifacts\installer-qa-report.json'
    [System.IO.File]::WriteAllText($reportPath, ($report | ConvertTo-Json -Depth 5), (New-Object System.Text.UTF8Encoding($false)))
    Copy-Item -LiteralPath $reportPath -Destination (Join-Path $qaRoot 'report.json')
    Write-Host "Installer QA report: $reportPath"
}
Write-Host "Passed $($checks.Count) installer checks. Administrator and clean-machine gates remain pending."
