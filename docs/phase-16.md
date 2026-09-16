# Phase 16: bundled offline base model

Implemented on 2026-09-16. This phase pins one object-detection base checkpoint for the later training worker without allowing a running application to download models.

## Delivered

- `yolo11n.pt` is the single bundled base model: YOLO11 Nano, 5,613,764 bytes, SHA-256 `0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1`.
- The checked-in build asset records its official source, integrity data, task, and licensing notice in `backend/assets/models/README.md`. PyInstaller refuses to build when the checkpoint is missing or fails that integrity check.
- The frozen backend packages the immutable source checkpoint at `_internal/assets/models/yolo11n.pt`. On startup it verifies the source, deserializes it through `YOLO(path)` without a fallback download, then atomically provisions an identical copy at `%LOCALAPPDATA%\VisionStudio\models\base\yolo11n.pt`.
- Every startup verifies the writable copy. A damaged copy is replaced from the verified bundled asset; user-created models and project data are never touched.
- `GET /models/base` and `GET /system/info` report the pinned identifier, local path, SHA-256, size, distribution, license, and successful checkpoint-load verification.
- The Models page presents the ready local checkpoint and its integrity data. It deliberately has no download, train, or inference controls.
- Gallery and annotation image navigation now use SQLite insertion order as a stable tie-breaker when rapid imports share a timestamp.

## Source and licensing

The model is the official YOLO11 Nano detection checkpoint described in the [Ultralytics YOLO11 documentation](https://docs.ultralytics.com/models/yolo11/), retrieved from `https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt` and pinned to the checksum above. The checkpoint is supplied under Ultralytics AGPL-3.0 or Enterprise terms; its redistribution and use remain subject to the applicable license.

## Packaging result

The final Phase 16 backend manifest lists 4,320 files totaling 810,842,798 bytes (about 773.3 MiB), built at `2026-09-16T04:33:25.8989919Z`. The portable backend ZIP is 277,020,809 bytes (`071b79f4b27e16db05d836538bb5b36b37d44512311174dca4393d6e3fbf341f`) and the production NSIS installer is 408,124,048 bytes (`755678370d5b5806ce395ee94ec8cf6bd8f8be87b6da95d530691d228b4d03ce`). The increase over Phase 15 is primarily the 5.35 MiB checkpoint and its compressed packaging overhead.

## Verification

- `npm run test:backend` passed: 116 tests. The existing two Starlette/AnyIO deprecation warnings remain.
- `npm run build` passed.
- `npm run test:e2e` passed: 35 browser tests under an Indonesian browser locale.
- `npm run test:backend-bundle` passed: 88 checks against a relocated executable with a sanitized environment and no Python on PATH. It loaded the bundled checkpoint, checked its source and provisioned copy hashes, and confirmed no additional `.pt` file was created. Report: `%LOCALAPPDATA%\VisionStudio\qa\Phase 16 49677b8f6c0e4e3e9827b60597eb5028\report.json`.
- `npm run check:desktop` passed and `npm run test:rust` passed: 1 Rust test.
- Debug desktop QA passed with the model endpoint and provisioned file: `%LOCALAPPDATA%\VisionStudio\qa\Desktop 761d985d-4b88-419f-8dfc-ed1abf793a13\report.json`.
- Production NSIS build passed. Release desktop QA passed normal operation, missing-backend recovery, and parent-crash cleanup: `Desktop dad21d2c-a195-459a-ad59-09f7bd95231f`, `Desktop 8b6187ff-9f27-405b-b67c-0adc7902b70c`, and `Desktop dfc1fd06-e550-4d95-b418-5982a3af2d6a` under the QA root.
- The current-user QA installer passed all 17 install, launch, resource-hash, uninstall, and user-data-preservation checks. It also ran the installed application with the provisioned checkpoint. Report: `artifacts/installer-qa-report.json`.

## Scope boundary

Phase 16 provides one verified offline base checkpoint and a read-only status surface. It does not create a training job, start a worker process, train a model, manage project model versions, offer optional downloads, or add camera inference. Those functions begin in Phases 17 through 25.

## Remaining acceptance

The developer-host bundle and installer tests prove that the launched executable uses the bundled checkpoint rather than Python from PATH. This host still has Python installed. A fresh Windows x64 machine without Python, elevated production installation in Program Files, and first offline WebView2 installation remain pending. Local results do not claim those gates passed.
