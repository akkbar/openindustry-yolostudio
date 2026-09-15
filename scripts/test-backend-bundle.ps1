param(
    [Parameter(Mandatory = $true)][string]$BundlePath,
    [switch]$RequireNoPython
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$source = (Resolve-Path -LiteralPath $BundlePath).Path
if (-not (Test-Path -LiteralPath (Join-Path $source 'backend.exe'))) { throw 'The bundle must contain backend.exe.' }
if (-not (Test-Path -LiteralPath (Join-Path $source '_internal'))) { throw 'The complete _internal directory is required.' }

# Inventory is evidence, not a claim that arbitrary host installations can all be detected.
$pythonCommands = @(Get-Command python,python3,py -CommandType Application -ErrorAction SilentlyContinue |
    Where-Object { $_.Source -notlike '*\Microsoft\WindowsApps\*' } | Select-Object -ExpandProperty Source -Unique)
$pythonRegistry = @('HKCU:\Software\Python\PythonCore', 'HKLM:\Software\Python\PythonCore', 'HKLM:\Software\WOW6432Node\Python\PythonCore') |
    Where-Object { Test-Path -LiteralPath $_ }
if ($RequireNoPython -and ($pythonCommands.Count -gt 0 -or @($pythonRegistry).Count -gt 0)) {
    throw 'Python is installed or discoverable on this machine. Run the clean-machine gate on a fresh Windows VM without Python.'
}

$qaRoot = Join-Path $env:LOCALAPPDATA ('VisionStudio\qa\Phase 1 ' + [Guid]::NewGuid().ToString('N'))
$relocated = Join-Path $qaRoot 'Relocated backend bundle'
$working = Join-Path $qaRoot 'Unrelated working directory'
$runtimeData = Join-Path $qaRoot 'Runtime data'
New-Item -ItemType Directory -Force -Path $qaRoot,$working | Out-Null
Copy-Item -LiteralPath $source -Destination $relocated -Recurse
$executable = Join-Path $relocated 'backend.exe'
$checks = New-Object System.Collections.Generic.List[string]
$processes = New-Object System.Collections.Generic.List[object]
$report = [ordered]@{
    passed = $false
    tested_at_utc = [DateTime]::UtcNow.ToString('o')
    clean_machine_requested = [bool]$RequireNoPython
    clean_machine_verified = $false
    detected_python_commands = $pythonCommands
    detected_python_registry = @($pythonRegistry)
    os = [Environment]::OSVersion.VersionString
    is_64_bit_os = [Environment]::Is64BitOperatingSystem
    source_bundle = $source
    relocated_bundle = $relocated
    checks = @()
}

function Assert-Check([bool]$Condition, [string]$Description) {
    if (-not $Condition) { throw "Check failed: $Description" }
    $checks.Add($Description)
}

function Bundle-Hashes {
    @(Get-ChildItem -LiteralPath $relocated -File -Recurse | Sort-Object FullName | ForEach-Object {
        $_.FullName.Substring($relocated.Length) + ':' + (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
    })
}

function Start-Bundle([string]$Arguments) {
    $start = New-Object System.Diagnostics.ProcessStartInfo
    $start.FileName = $executable
    $start.Arguments = $Arguments
    $start.WorkingDirectory = $working
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardInput = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $start.EnvironmentVariables.Clear()
    foreach ($key in @('SystemRoot','WINDIR','COMSPEC','TEMP','TMP','USERPROFILE','LOCALAPPDATA','APPDATA','PROGRAMDATA','PROCESSOR_ARCHITECTURE')) {
        $value = [Environment]::GetEnvironmentVariable($key)
        if ($value) { $start.EnvironmentVariables[$key] = $value }
    }
    $start.EnvironmentVariables['PATH'] = Join-Path $env:SystemRoot 'System32'
    $start.EnvironmentVariables['VISION_STUDIO_DATA_DIR'] = $runtimeData
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $start
    if (-not $process.Start()) { throw 'Backend process could not start.' }
    $entry = [pscustomobject]@{
        Process = $process
        Stdout = $process.StandardOutput.ReadToEndAsync()
        Stderr = $process.StandardError.ReadToEndAsync()
    }
    $processes.Add($entry)
    return $entry
}

try {
    Assert-Check ([Environment]::Is64BitProcess) 'The QA runner is a 64-bit Windows process.'
    $before = Bundle-Hashes
    $listener = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, 0)
    $listener.Start()
    $port = $listener.LocalEndpoint.Port
    $listener.Stop()
    $baseUrl = "http://127.0.0.1:$port"
    $entry = Start-Bundle "--port $port --parent-watch"
    $backendProcess = $entry.Process
    $report['process_id'] = $backendProcess.Id
    $report['api_url'] = $baseUrl
    $deadline = [DateTime]::UtcNow.AddSeconds(30)
    $health = $null
    while ([DateTime]::UtcNow -lt $deadline) {
        if ($backendProcess.HasExited) { throw "Backend exited during startup: $($entry.Stderr.Result)" }
        try { $health = Invoke-RestMethod "$baseUrl/health" -TimeoutSec 1; break } catch { Start-Sleep -Milliseconds 150 }
    }
    Assert-Check ($null -ne $health -and $health.status -eq 'ok' -and $health.service -eq 'vision-studio-backend') 'The relocated executable serves the expected health response.'
    Assert-Check ($health.version -eq '0.1.0') 'The bundled application version matches the release.'
    $info = Invoke-RestMethod "$baseUrl/system/info" -TimeoutSec 3
    Assert-Check ($info.os -eq 'Windows' -and $info.architecture -eq 'AMD64') 'System information reports Windows x64.'
    Assert-Check ($info.cpu.Length -gt 0 -and $info.logical_cpu_count -ge 1 -and $info.python_version.Length -gt 0) 'CPU and bundled Python information are available.'
    Assert-Check ($info.language -eq 'en') 'The application language is English.'
    Assert-Check ($info.data_directory -eq $runtimeData) 'Runtime storage is independent of the bundle and working directory.'
    foreach ($directory in @('data','projects','logs')) {
        Assert-Check (Test-Path -LiteralPath (Join-Path $runtimeData $directory)) "The $directory storage directory was initialized."
    }
    $backendProcess.Refresh()
    $pythonModules = @($backendProcess.Modules | Where-Object { $_.ModuleName -match '^python3.*\.dll$' } | Select-Object -ExpandProperty FileName)
    Assert-Check ($pythonModules.Count -ge 1) 'The running executable has loaded a Python runtime DLL.'
    foreach ($module in $pythonModules) {
        Assert-Check ($module.StartsWith($relocated + '\', [StringComparison]::OrdinalIgnoreCase)) 'The loaded Python runtime comes from the relocated bundle.'
    }
    $report['loaded_python_dlls'] = $pythonModules
    $report['system_info'] = $info
    $allowed = Invoke-WebRequest "$baseUrl/health" -UseBasicParsing -Headers @{ Origin = 'http://tauri.localhost' }
    Assert-Check ($allowed.Headers['Access-Control-Allow-Origin'] -eq 'http://tauri.localhost') 'Tauri frontend CORS is allowed.'
    $denied = Invoke-WebRequest "$baseUrl/health" -UseBasicParsing -Headers @{ Origin = 'https://untrusted.example' }
    Assert-Check (-not $denied.Headers['Access-Control-Allow-Origin']) 'Untrusted CORS origins are not allowed.'
    $schema = Invoke-RestMethod "$baseUrl/openapi.json" -TimeoutSec 3
    Assert-Check ($schema.info.title -eq 'Vision Studio API' -and $null -ne $schema.paths.'/system/info') 'The packaged API schema is available.'

    $collision = Start-Bundle "--port $port"
    Assert-Check ($collision.Process.WaitForExit(10000)) 'A second backend exits when its port is occupied.'
    Assert-Check ($collision.Process.ExitCode -ne 0) 'A port conflict returns a failing exit code.'
    Assert-Check ((Invoke-RestMethod "$baseUrl/health").status -eq 'ok') 'A port conflict leaves the original backend running.'
    $invalid = Start-Bundle '--port 0'
    Assert-Check ($invalid.Process.WaitForExit(10000)) 'Invalid command-line arguments terminate promptly.'
    Assert-Check ($invalid.Process.ExitCode -eq 2 -and $invalid.Stderr.Result.Contains('Port must be between 1 and 65535.')) 'Invalid ports return an English validation error.'

    $backendProcess.StandardInput.Close()
    Assert-Check ($backendProcess.WaitForExit(10000)) 'Closing the lifetime pipe stops the executable.'
    Assert-Check ($backendProcess.ExitCode -eq 0) 'The executable shuts down successfully.'
    $stillOnline = $false
    try { $null = Invoke-RestMethod "$baseUrl/health" -TimeoutSec 1; $stillOnline = $true } catch {}
    Assert-Check (-not $stillOnline) 'The API port is no longer serving after shutdown.'
    $standalone = Start-Bundle "--port $port"
    $standalone.Process.StandardInput.Close()
    $standaloneReady = $false
    $deadline = [DateTime]::UtcNow.AddSeconds(15)
    while ([DateTime]::UtcNow -lt $deadline -and -not $standalone.Process.HasExited) {
        try { $standaloneReady = (Invoke-RestMethod "$baseUrl/health" -TimeoutSec 1).status -eq 'ok'; break }
        catch { Start-Sleep -Milliseconds 150 }
    }
    Assert-Check $standaloneReady 'Standalone mode starts without a desktop or open input pipe.'
    $bindings = @(Get-NetTCPConnection -State Listen -OwningProcess $standalone.Process.Id -ErrorAction Stop)
    Assert-Check ($bindings.Count -eq 1 -and $bindings[0].LocalAddress -eq '127.0.0.1') 'The executable listens on loopback only.'
    $standalone.Process.Kill()
    $standalone.Process.WaitForExit()
    $after = Bundle-Hashes
    Assert-Check (-not (Compare-Object $before $after)) 'The application did not write into or change the relocated bundle.'
    $report['passed'] = $true
    $report['clean_machine_verified'] = [bool]$RequireNoPython
} catch {
    $report['error'] = $_.Exception.Message
    throw
} finally {
    foreach ($item in $processes) {
        $process = $item.Process
        if (-not $process.HasExited) {
            try { $process.StandardInput.Close() } catch {}
            if (-not $process.WaitForExit(5000)) { $process.Kill(); $process.WaitForExit() }
        }
        [System.IO.File]::WriteAllText((Join-Path $qaRoot "$($process.Id)-stdout.log"), $item.Stdout.Result)
        [System.IO.File]::WriteAllText((Join-Path $qaRoot "$($process.Id)-stderr.log"), $item.Stderr.Result)
        $process.Dispose()
    }
    $report['checks'] = @($checks.ToArray())
    $reportPath = Join-Path $qaRoot 'report.json'
    [System.IO.File]::WriteAllText($reportPath, ($report | ConvertTo-Json -Depth 8), (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "QA report: $reportPath"
}
Write-Host "Passed $($checks.Count) bundled backend checks. Clean-machine verification: $([bool]$RequireNoPython)."
