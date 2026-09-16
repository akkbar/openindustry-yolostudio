# Phase 15: bundled YOLO runtime

Implemented on 2026-09-16. This phase adds the CPU vision runtime to the packaged backend and validates it before any model-selection or training UI work. The follow-on base-model implementation is recorded in [Phase 16 evidence](phase-16.md).

## Delivered

- The backend imports OpenCV, PyTorch, Torchvision, Ultralytics, and the Ultralytics YOLO entry point during application startup.
- The locked Windows x64 CPU runtime is Ultralytics 8.4.153, PyTorch 2.14.0+cpu, Torchvision 0.29.0+cpu, and OpenCV 5.0.0. The packaged OpenCV distribution is opencv-python 5.0.0.93.
- `GET /system/info` reports the runtime readiness and the loaded versions.
- PyInstaller includes the Torch, OpenCV, Ultralytics, LAP, and native Torchvision extensions required by the frozen executable. The explicit Torchvision extension collection preserves the extensions that Torchvision loads through `torch.ops.load_library()`.
- Ultralytics and Matplotlib state is confined to `%LOCALAPPDATA%\VisionStudio\vision-runtime`. Ultralytics datasets, weights, and runs defaults resolve under the same application-data root. Background synchronization and editor messages are disabled.
- Startup sets `YOLO_AUTOINSTALL=False`. No base-model weights are bundled or downloaded; the bundle QA asserts that runtime initialization creates no `.pt` files.
- The desktop lifetime watcher now polls its Windows stdin pipe with nonblocking `PeekNamedPipe`. This avoids holding the Python GIL while the desktop keeps the pipe open, so the frozen backend can import the heavy runtime and still stop when its parent closes.

## Packaging result

The final backend manifest is Phase 15 and lists 4,318 files totaling 805,224,881 bytes (about 767.9 MiB). The portable backend ZIP is 271,989,976 bytes and the production NSIS installer is 403,243,043 bytes. The larger payload is the expected packaging cost of the local CPU inference runtime.

The runtime is CPU-only. CUDA tooling is not an end-user prerequisite, and GPU packaging remains a later phase.

## Verification

- `npm run test:backend` passed: 114 tests. The existing two Starlette/AnyIO deprecation warnings remain.
- `npm run build` passed.
- `npm run test:e2e` passed: 35 browser tests under an Indonesian browser locale.
- `npm run test:backend-bundle` passed: 85 checks against a relocated executable launched with a sanitized environment and no Python on PATH. It verified the exact runtime versions, application-data settings, no bundled or downloaded model, the bundled Python DLL, parent-pipe shutdown, standalone restart, and existing project/dataset/export behavior. Report: `%LOCALAPPDATA%\VisionStudio\qa\Phase 15 f97b2998df8f45f0a3393af87612dcbf\report.json`.
- `npm run check:desktop` passed and `npm run test:rust` passed: 1 Rust test.
- Debug desktop QA passed against a relocated packaged application, including runtime verification and close/relaunch behavior. Report: `%LOCALAPPDATA%\VisionStudio\qa\Desktop aaa17574-2f72-48ec-acc9-51b249923d1f\report.json`.
- Production NSIS build passed. Release desktop QA passed normal operation, missing-backend recovery, and parent-crash cleanup. Reports: `Desktop 3fd20c2a-1f5f-49b1-b918-9e4099c1601c`, `Desktop 551ce6eb-ec0f-4ef6-9dce-85a4e2be2e82`, and `Desktop fa5fbf93-3ddc-4de3-b66a-9d43e8571e45` under the QA root.
- The current-user QA installer passed all 17 install/launch/uninstall checks. It verified resource hashes, installed runtime startup, shortcut and uninstall registration, and user-data preservation. Report: `artifacts/installer-qa-report.json`.

## Scope boundary

Phase 15 does not select, download, or bundle a base model. It does not add training, worker processes, camera capture, inference, or a model UI. Phase 16 defines the model strategy; training remains in the later worker phases.

## Remaining acceptance

The developer-host bundle test proves that the executable does not use Python from PATH, but this host has Python installed. A fresh Windows x64 machine without Python, an elevated production installation in Program Files, and first offline WebView2 installation remain pending. Local results do not claim those gates passed.
