# Phase 19: GUI training launcher

Implemented on 2026-09-16. Operators can now create and start a local training job from the Models page without invoking a command line.

## Delivered

- The Models page keeps the verified YOLO11 Nano checkpoint details and adds a **Train model** form. It loads local projects, supports a direct `#Models/{project-id}` link from a project overview, and preserves the selected project in the browser URL.
- The form shows the single verified base model, defaults to 50 epochs and an image size of 640 pixels, and exposes the backend's Auto device setting. The shipped runtime accurately explains that training currently uses CPU.
- **Start training** creates a durable Phase 17 job and immediately calls the Phase 18 start endpoint. The API response returns after the separate worker is launched, so the frontend never invokes Python, Ultralytics, or a shell command.
- Client-side validation rejects non-integer epoch values outside 1–10,000 and image sizes outside 32–4,096 before a job is created. Backend validation remains authoritative.
- If a job record is created but the worker cannot start, such as while another job is running, the form keeps that exact queued job and offers **Retry starting training**. It does not create a duplicate job.
- A launch confirmation identifies the running job and explains that the operator can continue using the application. The worker still validates the current dataset snapshot before it trains.

## Scope boundary

Phase 19 launches training only. It does not poll a job, display epoch metrics, cancel a running job, register a trained checkpoint, or expose alternate models. Progress and result status belong to Phase 20; model registry starts at Phase 21.

## Verification

- `npm run build` passed with TypeScript checking and the production Vite build.
- `npm run test:backend` passed: 132 tests. The existing Starlette/AnyIO deprecation warnings remain.
- `npm run test:e2e` passed: 38 browser tests under an Indonesian browser locale.
- The primary Models-page browser test uses the real API and starts an isolated worker from the form. It verifies the persisted `yolo11n`, 12-epoch, 320-pixel configuration and waits for the deliberately empty project's worker validation failure. This verifies the GUI-to-worker boundary without presenting it as a model-quality run.
