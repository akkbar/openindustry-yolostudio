# Phase 17: training-job backend

Implemented on 2026-09-16. This phase makes training intent durable without starting training in the FastAPI process. The separate worker belongs to Phase 18 and the training interface belongs to Phase 19.

## Delivered

- Migration 6 upgrades the predeclared `training_jobs` columns from `base_model` and `image_size` to the public `model` and `imgsz` names. Existing rows retain their configuration and gain `updated_at` from their original creation time.
- `POST /projects/{project-id}/training-jobs` creates a queued job. The only accepted base model is the verified bundled `yolo11n`; default configuration is 50 epochs at 640 pixels. Requests reject unknown fields, other model identifiers, and out-of-range values with the standard English validation envelope.
- `GET /projects/{project-id}/training-jobs` returns bounded, newest-first records with `total`, `offset`, and `limit`. `GET /projects/{project-id}/training-jobs/{job-id}` returns one project-scoped job.
- `POST /projects/{project-id}/training-jobs/{job-id}/cancel` persists `cancelled` and `finished_at`. Repeating a cancellation is safe; completed and failed jobs return an English conflict.
- Every response includes the Phase 17 lifecycle fields: id, project id, status, model, epochs, image size, progress, metrics, timestamps, and error. Project deletion cascades to its job records.
- Creating, listing, and cancelling a job never invokes `YOLO.train`, starts a subprocess, downloads a model, writes a model artifact, or changes the dataset.
- Annotation lists now use SQLite insertion order when rapid writes share a timestamp, preventing a flaky UUID tie-breaker from reordering boxes in a response.

## Job states

`queued`, `running`, `completed`, `failed`, and `cancelled` are the only persisted states. Phase 17 creates `queued` records and can persist cancellation. Phase 18 will claim queued work, update running progress and metrics, and execute Ultralytics in a separate worker process.

## Packaging result

The Phase 17 backend manifest lists 4,320 files totaling 810,846,414 bytes, built at `2026-09-16T05:46:16.0107623Z`. The portable backend ZIP is 277,023,993 bytes with SHA-256 `1d3309bb0c04a077c554fd4866b2f8dab9fe420824eca0865061671238a19a6b`.

## Verification

- `npm run test:backend` passed: 126 tests. The existing two Starlette/AnyIO deprecation warnings remain.
- `npm run build` passed.
- `npm run test:e2e` passed: 35 browser tests under an Indonesian browser locale.
- `npm run build:backend` passed and produced a Phase 17 manifest.
- `npm run test:backend-bundle` passed: 91 checks against a relocated executable with a sanitized environment and no Python on PATH. It verified queue, list, and cancellation of a persisted job without starting a worker. Report: `%LOCALAPPDATA%\VisionStudio\qa\Phase 17 4b003658258642eebac289740449853c\report.json`.

## Scope boundary

Phase 17 intentionally has no training worker, training request that runs Ultralytics, progress poller, training UI, model artifact, model registry entry, or camera inference. Those begin in Phase 18 and later phases.

## Remaining acceptance

The relocated backend test proves that the packaged executable exposes the job API and continues to use its bundled Python runtime. This host has Python installed. A fresh Windows x64 computer without Python, elevated production installation in Program Files, and first offline WebView2 installation remain pending. Local results do not claim those gates passed.
