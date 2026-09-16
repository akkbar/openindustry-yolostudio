# Phase 18: separate training worker

Implemented on 2026-09-16. Training work now runs outside the FastAPI process. The Phase 17 job API remains the durable record of intent; Phase 18 adds the explicit transition that launches one isolated worker for a queued job.

## Delivered

- `POST /projects/{project-id}/training-jobs/{job-id}/start` atomically changes a queued job to `running` and returns `202 Accepted` after creating a child process. A job cannot be started twice, and one backend instance starts one worker at a time to avoid competing CPU training workloads.
- Development launches `python -m app --training-worker {job-id}`. The packaged application launches the same frozen executable as `backend.exe --training-worker {job-id}`. The child mode does not start Uvicorn.
- The worker initializes the existing local runtime, verifies and provisions the bundled `yolo11n.pt` checkpoint, creates an immutable validated YOLO snapshot, then calls Ultralytics with that local checkpoint, `device="cpu"`, and `workers=0`. It disables Ultralytics' package-update lookup in the worker.
- Ultralytics callbacks persist bounded epoch progress and finite scalar metrics. The final record includes losses, precision, recall, mAP values, timestamps, and either `completed`, `failed`, or `cancelled` without allowing a worker to overwrite a cancellation.
- Run inputs and artifacts remain under `projects/{project-id}/runs/{job-id}/`, including `training-context.json`, Ultralytics results, and checkpoint files. Child stdout and stderr go to `%LOCALAPPDATA%\VisionStudio\logs\training-workers\{job-id}.log`, outside a project folder so a finished worker cannot hold that folder open on Windows.
- A running job blocks project deletion. Backend shutdown terminates workers it owns and marks them failed; the next backend startup also changes stale `running` records to an English interrupted-training failure.

## Scope boundary

The API can now start a worker, but the frontend training form and progress poller belong to Phase 19 and Phase 20. This phase does not add a model registry entry, promoted model version, camera inference, or automatic background queue dispatch.

## Verification

- `npm run test:backend` passed: 132 tests. The existing Starlette/AnyIO deprecation warnings remain.
- `npm run build` passed.
- `npm run test:e2e` passed: 35 browser tests under an Indonesian browser locale.
- `npm run build:backend` produced the Windows x64 PyInstaller bundle.
- `npm run test:backend-bundle` passed: 95 checks against a relocated executable with a sanitized environment and no Python on PATH. It started a second bundled executable for an intentionally invalid job, confirmed API responsiveness and the worker log, then completed project deletion. Report: `%LOCALAPPDATA%\VisionStudio\qa\Phase 18 54a8286583b84c73bf62dc9cda05e96f\report.json`.
- A real isolated CPU run with two annotated 64x64 images, one epoch, and `imgsz=64` completed in approximately 17 seconds. It produced `results.csv`, `best.pt`, `last.pt`, and persisted box loss, class loss, distribution-focal loss, precision, recall, mAP50, and mAP50-95. Evidence remains under `%LOCALAPPDATA%\VisionStudio\qa\Phase 18 real training ec0507f55d854b88bb8a5631343ad983`.

## Packaging result

The final Phase 18 backend manifest lists 4,320 files totaling 810,854,664 bytes, built at `2026-09-16T06:45:45.4641210Z`. The portable backend ZIP is 277,033,765 bytes with SHA-256 `0f428a7c64eee592b30dabac6336b5b3dde3651a703797c7d14d107e797f6887`.

## Remaining acceptance

The bundle evidence uses this developer machine, where Python is installed. A fresh Windows x64 computer without Python, elevated production installation in Program Files, and first offline WebView2 installation remain pending. The intentionally small CPU run confirms the worker path only; it is not a model-quality evaluation.
