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
    $databasePath = Join-Path $runtimeData 'data\visionstudio.db'
    Assert-Check (Test-Path -LiteralPath $databasePath) 'The workspace database was created on first start.'
    Assert-Check ($info.database_path -eq $databasePath) 'System information reports the workspace database.'
    Assert-Check ($info.database_schema_version -ge 1) 'The workspace database reports a schema version.'
    $projectBody = @{ name = "Bundle QA $([Guid]::NewGuid().ToString('N').Substring(0, 8))" } | ConvertTo-Json -Compress
    $created = Invoke-RestMethod "$baseUrl/projects" -Method Post -ContentType 'application/json' -Body $projectBody -TimeoutSec 5
    Assert-Check ($created.id.Length -gt 0 -and $created.task_type -eq 'object_detection') 'The packaged backend creates a project.'
    $projectFolder = Join-Path $runtimeData "projects\$($created.id)"
    foreach ($directory in @('dataset','models','runs','events')) {
        Assert-Check (Test-Path -LiteralPath (Join-Path $projectFolder $directory)) "The project $directory folder was created."
    }
    $qaImages = Join-Path $PSScriptRoot 'qa-images'
    if (-not (Test-Path -LiteralPath $qaImages)) { $qaImages = Join-Path (Split-Path $PSScriptRoot -Parent) 'tests\fixtures\images' }
    foreach ($name in @('sample.jpg', 'sample.jpeg', 'sample.png', 'sample.webp')) {
        $fixture = Join-Path $qaImages $name
        $imported = Invoke-RestMethod "$baseUrl/projects/$($created.id)/datasets/images?filename=$name" -Method Post -ContentType 'application/octet-stream' -InFile $fixture -TimeoutSec 10
        Assert-Check ($imported.status -eq 'imported') "The packaged backend imports $name."
        $thumbnail = Invoke-WebRequest ($baseUrl + $imported.image.thumbnail_url) -UseBasicParsing -TimeoutSec 5
        Assert-Check ($thumbnail.StatusCode -eq 200 -and $thumbnail.Headers['Content-Type'] -eq 'image/jpeg') "The packaged backend serves the $name thumbnail."
        $original = Join-Path $projectFolder ('dataset\images\' + $imported.image.id + [IO.Path]::GetExtension($name))
        Assert-Check ((Get-FileHash -LiteralPath $fixture).Hash -eq (Get-FileHash -LiteralPath $original).Hash) "The imported $name preserves the original bytes."
    }
    Assert-Check ((Invoke-RestMethod "$baseUrl/projects/$($created.id)/datasets/summary").image_count -eq 4) 'The database records all four image formats.'
    $gallery = Invoke-RestMethod "$baseUrl/projects/$($created.id)/datasets/images?limit=2"
    Assert-Check ($gallery.total -eq 4 -and $gallery.images.Count -eq 2) 'The packaged gallery returns a bounded page.'
    Assert-Check ($gallery.images[0].width -eq 640 -and $gallery.images[0].height -eq 320 -and $gallery.images[0].annotated -eq $false) 'Gallery dimensions and annotation status are available.'
    $previewFile = Join-Path $qaRoot 'original-preview.jpg'
    Invoke-WebRequest ($baseUrl + $gallery.images[0].original_url) -UseBasicParsing -OutFile $previewFile -TimeoutSec 5
    Assert-Check ((Get-FileHash -LiteralPath $previewFile).Hash -eq (Get-FileHash -LiteralPath (Join-Path $qaImages 'sample.jpg')).Hash) 'The gallery serves unchanged original image bytes.'
    $null = Invoke-RestMethod "$baseUrl/projects/$($created.id)/datasets/images/$($gallery.images[0].id)" -Method Delete -TimeoutSec 5
    Assert-Check ((Invoke-RestMethod "$baseUrl/projects/$($created.id)/datasets/summary").image_count -eq 3) 'Deleting an image updates the persisted gallery count.'
    Assert-Check (-not (Test-Path -LiteralPath (Join-Path $projectFolder ('dataset\images\' + $gallery.images[0].id + '.jpg')))) 'Deleting an image removes its original file.'
    Assert-Check (-not (Test-Path -LiteralPath (Join-Path $projectFolder ('dataset\thumbnails\' + $gallery.images[0].id + '.jpg')))) 'Deleting an image removes its thumbnail.'
    Assert-Check ((Invoke-RestMethod "$baseUrl/projects" -TimeoutSec 5).total -eq 1) 'The packaged backend lists the created project.'
    $classRoute = "$baseUrl/projects/$($created.id)/classes"
    $classA = Invoke-RestMethod $classRoute -Method Post -ContentType 'application/json' -Body '{"name":"Banana"}' -TimeoutSec 5
    $classB = Invoke-RestMethod $classRoute -Method Post -ContentType 'application/json' -Body '{"name":"Pallet"}' -TimeoutSec 5
    Assert-Check ($classA.class_index -eq 0 -and $classB.class_index -eq 1) 'Class indices start at zero and increase.'
    $classRenamed = Invoke-RestMethod "$classRoute/$($classB.id)" -Method Patch -ContentType 'application/json' -Body '{"name":"Shipping pallet"}' -TimeoutSec 5
    Assert-Check ($classRenamed.name -eq 'Shipping pallet' -and $classRenamed.class_index -eq 1) 'Renaming preserves the class index.'
    $selectionBody = @{ selected_class_id = $classB.id } | ConvertTo-Json -Compress
    $null = Invoke-RestMethod "$baseUrl/projects/$($created.id)/annotation-state" -Method Patch -ContentType 'application/json' -Body $selectionBody -TimeoutSec 5
    Assert-Check ((Invoke-RestMethod $classRoute).selected_class_id -eq $classB.id) 'The selected class is available in project annotation state.'
    $null = Invoke-RestMethod "$classRoute/$($classA.id)" -Method Delete -TimeoutSec 5
    Assert-Check ((Invoke-RestMethod $classRoute).classes[0].class_index -eq 1) 'Deleting another class does not renumber the selected class.'
    $null = Invoke-RestMethod "$classRoute/$($classB.id)" -Method Delete -TimeoutSec 5
    Assert-Check ($null -eq (Invoke-RestMethod $classRoute).selected_class_id) 'Deleting the selected class clears annotation selection.'
    $classC = Invoke-RestMethod $classRoute -Method Post -ContentType 'application/json' -Body '{"name":"Crate"}' -TimeoutSec 5
    Assert-Check ($classC.class_index -eq 2) 'Deleted class indices are not reused.'
    $renamed = Invoke-RestMethod "$baseUrl/projects/$($created.id)" -Method Patch -ContentType 'application/json' -Body '{"name":"Renamed bundle project"}' -TimeoutSec 5
    Assert-Check ($renamed.name -eq 'Renamed bundle project') 'The packaged backend renames a project.'
    $null = Invoke-RestMethod "$baseUrl/projects/$($created.id)" -Method Delete -TimeoutSec 5
    Assert-Check (-not (Test-Path -LiteralPath $projectFolder)) 'Deleting a project removes its storage folder.'
    $report['database_path'] = $databasePath
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

    $persisted = Invoke-RestMethod "$baseUrl/projects" -Method Post -ContentType 'application/json' -Body '{"name":"Restart persistence check"}' -TimeoutSec 5
    $persistedClass = Invoke-RestMethod "$baseUrl/projects/$($persisted.id)/classes" -Method Post -ContentType 'application/json' -Body '{"name":"Persisted class"}' -TimeoutSec 5
    $persistedImage = Invoke-RestMethod "$baseUrl/projects/$($persisted.id)/datasets/images?filename=sample.png" -Method Post -ContentType 'application/octet-stream' -InFile (Join-Path $qaImages 'sample.png') -TimeoutSec 5
    $annotationRoute = "$baseUrl/projects/$($persisted.id)/datasets/images/$($persistedImage.image.id)/annotations"
    $annotationId = [Guid]::NewGuid().ToString('N')
    $annotationBody = @{ id = $annotationId; class_id = $persistedClass.id; center_x = 0.5; center_y = 0.5; width = 0.4; height = 0.3; expected_revision = 0 } | ConvertTo-Json -Compress
    $annotation = Invoke-RestMethod $annotationRoute -Method Post -ContentType 'application/json' -Body $annotationBody -TimeoutSec 5
    Assert-Check ($annotation.revision -eq 1 -and $annotation.annotated_count -eq 1) 'Creating a normalized annotation updates image progress.'
    $retriedAnnotation = Invoke-RestMethod $annotationRoute -Method Post -ContentType 'application/json' -Body $annotationBody -TimeoutSec 5
    Assert-Check ($retriedAnnotation.annotations.Count -eq 1 -and $retriedAnnotation.revision -eq 1) 'Retrying annotation creation does not duplicate the box.'
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
    $reopened = Invoke-RestMethod "$baseUrl/projects/$($persisted.id)" -TimeoutSec 5
    Assert-Check ($reopened.name -eq 'Restart persistence check') 'Project data persists across executable restarts.'
    $reopenedClasses = Invoke-RestMethod "$baseUrl/projects/$($persisted.id)/classes" -TimeoutSec 5
    Assert-Check ($reopenedClasses.selected_class_id -eq $persistedClass.id -and $reopenedClasses.classes[0].name -eq 'Persisted class') 'Classes and the selected class persist across executable restarts.'
    $savedAnnotation = Invoke-RestMethod $annotationRoute -TimeoutSec 5
    Assert-Check ($savedAnnotation.annotations[0].width -eq 0.4 -and $savedAnnotation.annotations[0].height -eq 0.3 -and $savedAnnotation.annotations[0].class_id -eq $persistedClass.id) 'Normalized coordinates and the assigned class survive backend restart.'
    $annotationUpdate = @{ class_id = $persistedClass.id; center_x = 0.4; center_y = 0.4; width = 0.2; height = 0.2; expected_revision = 1 } | ConvertTo-Json -Compress
    $updatedAnnotation = Invoke-RestMethod "$annotationRoute/$annotationId" -Method Patch -ContentType 'application/json' -Body $annotationUpdate -TimeoutSec 5
    Assert-Check ($updatedAnnotation.revision -eq 2 -and $updatedAnnotation.annotations[0].width -eq 0.2) 'The packaged backend updates annotation geometry.'
    $datasetRoute = "$baseUrl/projects/$($persisted.id)/datasets"
    $invalidDataset = Invoke-RestMethod "$datasetRoute/validate" -Method Post -TimeoutSec 10
    Assert-Check (-not $invalidDataset.valid -and $invalidDataset.images -eq 1) 'Dataset validation requires separate training and validation images.'
    $blockedExport = Invoke-RestMethod "$datasetRoute/export" -Method Post -TimeoutSec 10
    Assert-Check (-not $blockedExport.exported) 'Invalid datasets cannot be exported.'
    $secondImage = Invoke-RestMethod "$datasetRoute/images?filename=sample.jpg" -Method Post -ContentType 'application/octet-stream' -InFile (Join-Path $qaImages 'sample.jpg') -TimeoutSec 5
    $secondBox = @{ id = [Guid]::NewGuid().ToString('N'); class_id = $persistedClass.id; center_x = 0.5; center_y = 0.5; width = 0.4; height = 0.3; expected_revision = 0 } | ConvertTo-Json -Compress
    $null = Invoke-RestMethod "$datasetRoute/images/$($secondImage.image.id)/annotations" -Method Post -ContentType 'application/json' -Body $secondBox -TimeoutSec 5
    $validDataset = Invoke-RestMethod "$datasetRoute/validate" -Method Post -TimeoutSec 10
    Assert-Check ($validDataset.valid -and $validDataset.annotations -eq 2) 'The packaged backend validates an annotated dataset.'
    $exportedDataset = Invoke-RestMethod "$datasetRoute/export" -Method Post -TimeoutSec 20
    Assert-Check ($exportedDataset.exported -and $exportedDataset.train_images -eq 1 -and $exportedDataset.val_images -eq 1) 'YOLO export creates disjoint nonempty training and validation sets.'
    Assert-Check (Test-Path -LiteralPath $exportedDataset.yaml_path) 'The training configuration exists in the exported snapshot.'
    $exportManifest = Get-Content -LiteralPath (Join-Path $exportedDataset.path 'manifest.json') -Raw | ConvertFrom-Json
    Assert-Check ($exportManifest.seed -eq 42 -and $exportManifest.images.Count -eq 2) 'The export manifest records the seed and both images.'
    foreach ($exportImage in $exportManifest.images) {
        $exportLabel = Join-Path $exportedDataset.path "labels/$($exportImage.split)/$($exportImage.image_id).txt"
        Assert-Check ((Test-Path -LiteralPath $exportLabel) -and (Test-Path -LiteralPath (Join-Path $exportedDataset.path "images/$($exportImage.split)/$($exportImage.exported_name)"))) 'Each exported image has a matching YOLO label file.'
    }
    $deletedAnnotation = Invoke-RestMethod "$annotationRoute/$($annotationId)?expected_revision=2" -Method Delete -TimeoutSec 5
    Assert-Check ($deletedAnnotation.annotations.Count -eq 0 -and $deletedAnnotation.annotated_count -eq 1) 'Deleting the final annotation clears only that image progress.'
    $null = Invoke-RestMethod "$baseUrl/projects/$($persisted.id)" -Method Delete -TimeoutSec 5
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
