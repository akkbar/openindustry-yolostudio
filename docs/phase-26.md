# Phase 26: Full standalone build checkpoint

Implemented on 2026-09-16 as a packaging checkpoint for the local dataset-to-camera detection path.

## Checkpoint scope

- The Windows backend package includes the camera-session module, preview route, active-model inference route, and the Phase 26 manifest marker.
- The bundled-backend QA validates the packaged OpenAPI camera-session route in addition to its existing relocated-runtime, model, registry, and bounded USB-camera checks.
- The desktop installer build and its developer-machine tests remain the Phase 26 verification artifacts.

## Verification

- `npm run build` passed.
- `npm run test:backend` passed: 138 tests. The existing Starlette/AnyIO deprecation warnings remain.
- All 41 browser tests passed serially in isolated groups because the workspace command runner limits a single shell process to 30 seconds.
- `npm run build:backend` and `npm run test:backend-bundle` passed. The relocated Phase 26 backend bundle completed 97 checks; report: `%LOCALAPPDATA%\VisionStudio\qa\Phase 26 2c9f4f72061d435187d0d93d76e0df0a\report.json`.
- `npm run build:installer`, release desktop normal/missing-backend/crash tests, `npm run build:installer:qa`, and `npm run test:installer` passed. The per-user installer QA completed 17 checks.
- `npm run check:desktop` and `npm run test:rust` passed; the Rust suite has one test.

## Remaining environment gate

A fresh Windows x64 computer without Python, Node.js, Git, npm, VS Code, or a preinstalled development environment is required to prove the clean-machine acceptance path. This repository cannot make that claim until that external test is run.
