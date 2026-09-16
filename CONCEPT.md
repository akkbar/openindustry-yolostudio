# OpenIndustry Vision Studio — Technical Concept & Specifications

> **Scope**: Architectural specifications, packaging constraints, internal data models, and component lifecycles for OpenIndustry Vision Studio.

Industrial computer vision applications, from dataset to production, without writing Python. **Implemented through Phase 34: bundled desktop, offline NSIS installer, projects, image import, dataset gallery, classes, a bounding-box annotation editor, validated YOLO dataset export, a bundled CPU YOLO runtime, a verified YOLO11 Nano base checkpoint, durable training jobs, a separate CPU training worker, polling progress metrics, a project model registry with production selection, USB-camera discovery, local JPEG preview, CPU live inference, detection overlays, a full standalone packaging checkpoint, a metadata-driven pretrained model library with shared COCO presets, ByteTrack-style local tracking, persisted counting lines, live crossing counters, polygon ROI filtering, line-cross events with JPEG snapshots, and reconnecting RTSP camera preview. Clean-Windows and elevated installation acceptance remain pending.**

The application always uses **English**, including errors and default content. User-entered data is preserved as entered. The source planning documents retain their original language.

## Planning Authority

Read [the comparison and decisions](docs/plan-comparison.md) first. `phase-plan.md` controls execution order; `step.md` supplies feature task details; `Overall-plan.md` defines product direction. See [Phase 0 verification](docs/phase-0.md), [Phase 1 packaging evidence](docs/phase-1.md), [Phases 2–4 delivery and acceptance](docs/phases-2-4.md), [Phases 5–7 database and projects](docs/phases-5-7.md), [Phase 8 image import](docs/phase-8.md), [Phase 9 dataset gallery](docs/phase-9.md), [Phase 10 class manager](docs/phase-10.md), [Phases 11–12 annotations](docs/phases-11-12.md), [Phases 13 and 14 export and validation](docs/phases-13-14.md), and [Phase 15 runtime packaging](docs/phase-15.md). The user authorized continuation while the unavailable clean-Windows gate stays pending.

See [Phase 16 base-model packaging](docs/phase-16.md) for the verified checkpoint, packaging evidence, and remaining acceptance gates. See [Phases 32–34](docs/phases-32-34.md) for events, snapshots, and RTSP camera support.

See [Phase 17 training-job backend](docs/phase-17.md) for the persisted job contract, migration, and worker/UI boundary.

See [Phase 18 training worker](docs/phase-18.md) for the separate-process lifecycle, local training inputs and outputs, and verification evidence.

See [Phase 19 training UI](docs/phase-19.md) for the Models-page launcher, validation, retry behavior, and browser verification.

See [Phase 20 training progress](docs/phase-20.md), [Phase 21 model registry](docs/phase-21.md), and [Phase 22 USB cameras](docs/phase-22.md) for the training result flow and local camera discovery.

See [Phase 23 camera preview](docs/phase-23.md), [Phase 24 live inference](docs/phase-24.md), [Phase 25 detection overlay](docs/phase-25.md), and [Phase 26 standalone checkpoint](docs/phase-26.md) for the local camera-to-detection path and packaging verification.

See [Phases 27–31 tracking, counting, and ROI](docs/phases-27-31.md) for the first local counting workflow. Before continuing with later feature phases, [the Apple detector demo dataset](docs/apple-detector-demo.md) provides one complete, publicly licensed dataset for exercising the existing workflow end to end. [The model catalog](docs/model-catalog.md) documents the shared built-in presets, specialist model metadata, storage, and inference selection.

## Run the packaged application

Run `artifacts/OpenIndustry-Vision-Studio-Setup.exe` to install for all users (administrator access required). It includes the backend, bundled CPU YOLO runtime, the verified YOLO11 Nano base checkpoint, frontend assets, and offline WebView2 installer. End users do not install Python, Node.js, npm, pip, Rust, or CUDA tooling.

Alternatively, open `artifacts/desktop/OpenIndustry Vision Studio.exe` on a Windows x64 computer with WebView2. Keep the whole `desktop` folder together, including `backend/_internal`. The portable folder does not install WebView2; the setup executable does. These are local proof-of-concept artifacts, not a signed production release.

## Development on Windows

Prerequisites: Node.js 22.12+ (24 supported), Python 3.10 (the packaging baseline), Rust 1.98.1 with the Windows MSVC target (pinned in `desktop/rust-toolchain.toml`), Visual Studio C++ build tools and Windows SDK, and Microsoft Edge WebView2. These are developer requirements; the installer bundles its runtime dependencies. See [Tauri prerequisites](https://v2.tauri.app/start/prerequisites/).

From the repository root:

```powershell
npm ci
npm run setup:backend
npm run build:backend
npm run dev
```

`npm run dev` starts Vite and Tauri. Tauri starts its own hidden Python backend on a dynamically selected loopback port. The UI discovers that address through a Rust command and polls health. Closing the desktop window terminates its backend. Do not start a separate backend for desktop development.

If Rust was installed locally in `.tools/cargo` and `.tools/rustup`, the desktop script automatically uses it without modifying global PATH. Otherwise it uses Rust from PATH. Dependencies must be downloaded during initial developer setup.

For browser-only work, use two terminals:

```powershell
npm run dev:backend
```

```powershell
npm run dev:frontend
```

Open `http://127.0.0.1:1420`. The browser uses port 8765 for the API. `.env.example` documents the optional Vite override; copy it to `.env` when needed. Set `VISION_STUDIO_DATA_DIR` in the process environment to override storage; it must be an absolute path. Backend scripts do not automatically load `.env`.

## Verification

```powershell
npm run build
npm run test:backend
npm run test:backend-bundle
npx playwright install chromium
npm run test:e2e
npm run check:desktop
npm run build:desktop
npm run test:desktop
```

Stop browser development servers before running E2E tests; tests own ports 1420 and 8765. E2E tests connect to the real API, exercise failure/recovery, and verify English UI under an Indonesian browser locale. They run the backend against a per-run temporary data directory, so they never modify your own projects.

`build:desktop` builds the backend and frontend, compiles a packaged debug desktop, and stages `artifacts/desktop-debug/OpenIndustry Vision Studio.exe` with its runtime resources. Unlike `npm run dev`, packaged debug and release builds always launch the bundled backend; they never fall back to development Python.

Build and verify the release installer:

```powershell
npm run build:installer
npm run test:desktop -- --release
npm run test:desktop -- --release --missing-backend
npm run test:desktop -- --release --crash
npm run test:rust
```

The build stages `artifacts/desktop/`, `artifacts/OpenIndustry-Vision-Studio-Setup.exe`, and its SHA-256 checksum. WebView2 is downloaded during the initial build and embedded for offline installation. The installer is English-only and preserves runtime data on uninstall.

For local installation tests without administrator access:

```powershell
npm run build:installer:qa
npm run test:installer
```

The distinctly named QA installer packages the existing release payload for the current user. The test installs into a unique QA directory, checks its shortcut and uninstall registration, runs the installed desktop, uninstalls it, and checks data preservation. This does not verify the production installer's elevated path or a clean machine. See the [installer instructions](installer/README.md).

## Backend executable, YOLO runtime, base model, job backend, and worker (Phases 1, 15-18)

Build and test on Windows x64 with Python 3.10 available to the developer:

```powershell
npm run build:backend
npm run test:backend-bundle
```

The build creates a separate environment in `.tools/backend-build`, installs `backend/requirements-build.lock`, freezes the API with PyInstaller, and generates:

```text
artifacts/backend/backend.exe
artifacts/backend/_internal/
artifacts/backend-manifest.json
artifacts/VisionStudio-Backend-0.1.0-windows-x64.zip
artifacts/VisionStudio-Backend-0.1.0-windows-x64.zip.sha256
```

Run `artifacts\backend\backend.exe --port 8765` to serve the API independently of the development virtual environment. Distribute the entire ZIP or backend folder; the executable requires the adjacent `_internal` directory. The ZIP also contains a PowerShell QA script requiring no Python/Node installation. See [the included instructions](installer/backend-poc-README.md) for clean-machine testing.

The local smoke test relocates the bundle, sanitizes its environment, checks loaded runtime DLLs and English API responses, verifies the bundled Ultralytics, PyTorch, Torchvision, and OpenCV runtime, loads the pinned YOLO11 Nano checkpoint, confirms its provisioned local copy and that no additional model is downloaded, then starts an intentionally invalid job in a second bundled worker process while the API remains responsive. It verifies the persisted failure, worker log, queue cancellation, startup, shutdown, and port failures. It keeps JSON evidence and logs under `%LOCALAPPDATA%\VisionStudio\qa`. A passing local test does not close the clean-Windows gate.

## Repository

```text
frontend/     React + TypeScript + Vite; English copy in src/locales/en.ts
backend/      FastAPI, local storage paths, API tests
desktop/      Tauri 2, packaged/development backend lifecycle
scripts/      Development and verification commands
installer/    Windows packaging strategy
data/         Ignored development fixtures only
docs/         Planning decisions and phase evidence
tests/        Browser integration tests
```

Runtime storage defaults to `%LOCALAPPDATA%\VisionStudio\`, with `data`, `projects`, `logs`, `demo-datasets`, `webview`, `vision-runtime`, and `models/base` directories. The workspace database is `data/visionstudio.db`; each project owns `projects/{project-id}/` with `dataset`, `models`, `runs`, and `events` subfolders. Backend logs rotate under `logs/backend.log`, while child-worker output is stored at `logs/training-workers/{job-id}.log`; the complete AppleBBCH76 demo archive is cached in `demo-datasets`; WebView2 keeps its cache in `webview`; Ultralytics and Matplotlib configuration live in `vision-runtime`; the verified YOLO11 Nano checkpoint is provisioned in `models/base`. No runtime files are written into the installation directory.

`test:desktop` starts the built desktop app, inspects its actual WebView2, checks backend connectivity, closes the window through Tauri, and verifies that the API stops. It enables a local debug port only for that test process; normal launches do not enable remote debugging. Desktop shutdown closes a lifetime pipe so both the Windows Python redirector and its backend process exit.

The API exposes `GET /health`, `GET /system/info`, the read-only base-model status on `/models/base`, the metadata-driven pretrained catalog on `/model-catalog`, project management on `/projects`, the Apple demo importer on `/demo-datasets/apple`, persisted training jobs on `/projects/{project-id}/training-jobs`, registered models on `/projects/{project-id}/models`, local USB camera discovery on `/cameras/usb`, and camera sessions under `/projects/{project-id}/cameras/usb/{camera-index}/sessions`. A session owns one local camera, provides binary JPEG frames, and runs the active production checkpoint when available. `POST /projects/{project-id}/training-jobs/{job-id}/start` returns `202 Accepted` after launching a separate worker process; it never runs Ultralytics inside the API request. OpenAPI documentation is available at `/docs`. The API binds to `127.0.0.1` only. Failures use one English envelope, `{"error": {"code", "message"}}`.

The workspace database is created on first start using the standard library `sqlite3` module, so no database server is involved. Schema changes are append-only migrations keyed to `PRAGMA user_version`; a database written by a newer application version is refused rather than downgraded. Phase 8 uses Pillow 12.3.0 for image validation and thumbnails. Phase 15 bundles the CPU AI runtime; Phase 16 provisions the verified offline base model; Phase 17 persists training-job configuration and lifecycle state; Phase 18 executes each started job in its own CPU worker process; Phase 19 launches it from the Models page; Phase 20 polls its metrics; Phase 21 registers successful checkpoints; Phase 22 discovers openable USB camera indexes; and Phases 23–25 stream local frames, infer with the selected catalog preset or active production model, and render detection overlays.

## Import images

Open a project, or choose one on the Dataset page. Use **Select images** or drop multiple JPG/JPEG, PNG, or WEBP files onto the import area. Each still image may be up to 25 MiB and 25 million pixels. Imports show progress, skip identical file contents, and report individual failures with a retry action.

Original bytes are copied into the project's `dataset/images` folder with unique filenames; the original names remain in SQLite. Oriented thumbnails are stored in `dataset/thumbnails`. The latest 20 results are shown after an import, and the saved count persists across reloads.

## Browse the dataset

Use **View dataset gallery** in a project, or choose the project on the Dataset page. Each page displays up to 60 thumbnails with filenames, dimensions, and annotation status. **Previous page** and **Next page** keep browsing bounded for larger datasets. Select a thumbnail to preview the original image; use **Close preview** or Escape to return.

**Delete** asks for confirmation before removing an image and its annotations. Image counts and the gallery refresh after imports and deletions. Locked files are queued for cleanup on the next deletion or application start. New images initially show **Not annotated** and can be opened in the annotation editor.

## Manage classes

On the Dataset page, use the **Classes** sidebar to add or rename object classes. Select a class to make it active; its name and index also appear in the image preview. The selection is saved per project and restored after reload or restart. **Clear selection** removes the active choice.

Class indices start at zero and remain stable. Deleting a class requires confirmation, clears selection if that class was active, and does not renumber other classes or reuse the deleted index. Classes used by annotations cannot be deleted. Class names are preserved as entered; duplicate names are checked without case or whitespace differences.

## Annotate images

Use **Annotate** on a gallery card. Choose an active class and drag on the image to draw a box. **Select and move** selects boxes for movement; drag a corner handle to resize. The box list can also select a box. **Assign active class** changes its class, and **Delete selected box** removes it. Coordinates are normalized to the oriented image dimensions and saved automatically after each completed change.

Use **Zoom in/out**, the mouse wheel, **Pan image**, middle-button dragging, **Fit image**, and **Reset view** to control the view. Previous/Next and A/D move through the project's image order. Delete removes the selected box; 1–9 choose the first nine classes in the list. Shortcuts ignore form controls. **Annotated N / total** counts images with saved boxes.

Wait for **All changes saved** before closing. A failed save keeps the draft and blocks image navigation until retry succeeds or you confirm discarding the change. If another window changed the annotations, reload the saved version before editing again. Class creation remains in the Dataset sidebar. Use the validation and export panel below the image importer to prepare a training dataset. The Models page starts jobs, reports their persisted metrics, and lets you select a completed model for production. The Cameras page lists locally openable USB camera indexes, saves RTSP cameras for a project, starts a JPEG preview, overlays detections from the active production model, and shows saved line-cross events with their snapshots.

E2E tests use separate ports (backend 18765, frontend 11420 by default), isolated storage, and a Vite-only API proxy so an existing development session can remain running. Override `VISION_STUDIO_TEST_BACKEND_PORT` and `VISION_STUDIO_TEST_FRONTEND_PORT` if those ports are occupied. The production API's allowed origins are unchanged. Restart a running development backend after backend source changes to load the new endpoints and migrations.

Lockfiles: `package-lock.json`, `desktop/Cargo.lock`, `backend/requirements-dev.lock`, and `backend/requirements-build.lock`. The Python locks capture the tested Windows/Python 3.10 environment; regenerate and verify them deliberately when changing the supported Python baseline or dependencies.

## Validate and export a YOLO dataset

In Dataset, choose **Validate dataset** to check image files, boxes, classes, unannotated images, and duplicate pixels. At least two annotated images are required. Fix every issue, then choose **Export YOLO dataset**. Export repeats validation against the current data.

Each successful export creates `projects/<project-id>/dataset-export/<export-id>/` under the application data folder, with `images/train`, `images/val`, matching YOLO labels, `data.yaml`, and a provenance manifest. The deterministic split uses seed 42, approximately 80% training and 20% validation, with at least one image per set. Exported PNGs match the oriented images used for annotation. Stable project class indices are mapped to consecutive YOLO indices without modifying the project.

Copy the displayed training-configuration path for later training. Snapshots remain independent of later edits and are removed with their project. If moving a snapshot elsewhere, update the absolute `path` in `data.yaml`. Validation results reflect the last check; run validation again after editing. Empty images are blocked until an explicit negative-image review workflow is introduced.
