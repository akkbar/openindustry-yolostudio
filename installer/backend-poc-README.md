# Vision Studio Backend - standalone QA package

This package contains the local API, bundled Python runtime, and CPU YOLO runtime for Windows x64. Keep `backend.exe` together with the entire `_internal` directory. It includes Ultralytics 8.4.153, PyTorch 2.14.0+cpu, Torchvision 0.29.0+cpu, and OpenCV 5.0.0. Python, Node.js, pip, npm, and CUDA are not required to run this package.

This is a backend proof of concept, not the desktop installer. The API only listens on `127.0.0.1`.

## Run

Extract the complete ZIP into a writable folder, then use PowerShell:

```powershell
.\backend\backend.exe --port 8765
```

In another PowerShell window:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/health
Invoke-RestMethod http://127.0.0.1:8765/system/info
```

Stop with Ctrl+C. Default data and logs live in `%LOCALAPPDATA%\VisionStudio`. The optional `VISION_STUDIO_DATA_DIR` process environment variable accepts an absolute path. Do not place writable runtime data in Program Files.

## Verify on clean Windows

Use a fresh Windows 10/11 x64 VM or PC with no installed Python. Disconnect external networking after copying this archive; the test needs loopback only. No installation or administrator privileges are required.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Test-Backend.ps1 -BundlePath .\backend -RequireNoPython
```

The test copies the bundle to a separate path with spaces, removes development tools and Python variables from the child environment, checks the API, verifies that the loaded Python DLL is inside the bundle, checks CORS and English responses, tests port collision and invalid port errors, and verifies shutdown through the desktop lifetime pipe. It creates a JSON report and diagnostic logs under `%LOCALAPPDATA%\VisionStudio\qa`.

The `-RequireNoPython` check rejects detected Python executables and standard Python registry installations. Use it only on a genuinely clean VM; detection checks do not prove that an arbitrary existing machine is pristine. Keep the report with the VM/OS description as acceptance evidence. On a developer PC, omit the switch; the report records that the clean-machine gate is not verified.

`backend-manifest.json` lists bundled file hashes. The adjacent ZIP `.sha256` file identifies the archive. The API includes SQLite, projects, image import, the gallery, classes, normalized annotations, dataset validation, YOLO snapshot export, the Phase 15 runtime verification endpoint, the Phase 16 read-only base-model endpoint, Phase 17 persisted training-job endpoints, and the Phase 18 worker-start endpoint. Starting a queued job launches a separate `backend.exe --training-worker` process; it uses the verified local `yolo11n.pt` checkpoint and an immutable snapshot without downloading a model. Ultralytics settings, worker output logs, and all model artifacts live under application data. The QA script checks the locked runtime versions, checkpoint hash and local provisioning in addition to project folders, queue/list/start/cancel behavior, a separate worker failure for an invalid dataset while the API remains responsive, project deletion after that worker releases its files, rename/delete, database persistence, import/thumbnail generation for JPEG, PNG, and WEBP, gallery pagination, original previews, image deletion, class CRUD, selected-class persistence, annotation CRUD, safe creation retries, and coordinates retained across restart using the included `qa-images` fixtures. The training UI, model registry, and camera functionality remain later phases.
