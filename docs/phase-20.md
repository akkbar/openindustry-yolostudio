# Phase 20: Training progress

Implemented on 2026-09-16. The Models page now presents the persisted state of local training work without a WebSocket connection.

## Delivered

- The client polls the selected job every second and falls back to the latest job for the selected project after a reload.
- It shows `Epoch n / total`, completion percentage, box loss, precision, recall, and mAP50 whenever the worker has reported those values.
- Completed, failed, and cancelled job states remain visible with their timestamps or English error message. A running or queued job can be cancelled from the page.
- The API job response includes the persisted Auto device and update timestamp needed by the poller.

## Scope boundary

Polling is deliberately bounded to the Models page. There is no WebSocket or server-side push channel in this phase.

## Verification

- The browser suite covers epoch and metric updates from the poll API, completed-state presentation, and cancellation controls through the real frontend API client.
- `npm run build` passed.
- `npm run test:backend` passed: 136 tests. The existing Starlette/AnyIO deprecation warnings remain.
- All 40 browser tests passed serially in isolated groups because the workspace command runner limits a single shell process to 30 seconds.
- `npm run build:backend` and `npm run test:backend-bundle` passed. The relocated Phase 22 bundle completed 97 checks.
