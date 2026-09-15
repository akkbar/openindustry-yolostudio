Progress: 15%
Target: YOLO Desktop, Open Industrial YOLO Vision Studio, Run in Windows
About: a Platform to create YOLO model then use your connected camera (USB, RTSP, laptop etc) to run it, then post the result into industrial protocol such as OPC UA, Modbus, MC Protocol, Profinet

#========================Line below updated by AI=====================
# Vision Studio

Industrial computer vision applications, from dataset to production, without writing Python. **Implemented through Phase 9: bundled desktop, offline NSIS installer, local SQLite database, projects, image import, and a dataset gallery with original previews and confirmed deletion. Clean-Windows and elevated installation acceptance remain pending.**

The application always uses **English**, including errors and default content. User-entered data is preserved as entered. The source planning documents retain their original language.

## Planning

Read [the comparison and decisions](docs/plan-comparison.md) first. `phase-plan.md` controls execution order; `step.md` supplies feature task details; `Overall-plan.md` defines product direction. See [Phase 0 verification](docs/phase-0.md), [Phase 1 packaging evidence](docs/phase-1.md), [Phases 2–4 delivery and acceptance](docs/phases-2-4.md), [Phases 5–7 database and projects](docs/phases-5-7.md), [Phase 8 image import](docs/phase-8.md), and [Phase 9 dataset gallery](docs/phase-9.md). The user authorized continuation while the unavailable clean-Windows gate stays pending. Phase 10 class manager has not started.

## Run the packaged application

Run `artifacts/VisionStudio-Setup.exe` to install for all users in `C:\Program Files\VisionStudio` (administrator access required). It includes the backend, Python runtime, frontend assets, and offline WebView2 installer. End users do not install Python, Node.js, npm, pip, or Rust.

Alternatively, open `artifacts/desktop/VisionStudio.exe` on a Windows x64 computer with WebView2. Keep the whole `desktop` folder together, including `backend/_internal`. The portable folder does not install WebView2; the setup executable does. These are local proof-of-concept artifacts, not a signed production release.

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
npx playwright install chromium
npm run test:e2e
npm run check:desktop
npm run build:desktop
npm run test:desktop
```

Stop browser development servers before running E2E tests; tests own ports 1420 and 8765. E2E tests connect to the real API, exercise failure/recovery, and verify English UI under an Indonesian browser locale. They run the backend against a per-run temporary data directory, so they never modify your own projects.

`build:desktop` builds the backend and frontend, compiles a packaged debug desktop, and stages `artifacts/desktop-debug/VisionStudio.exe` with its runtime resources. Unlike `npm run dev`, packaged debug and release builds always launch the bundled backend; they never fall back to development Python.

Build and verify the release installer:

```powershell
npm run build:installer
npm run test:desktop -- --release
npm run test:desktop -- --release --missing-backend
npm run test:desktop -- --release --crash
npm run test:rust
```

The build stages `artifacts/desktop/`, `artifacts/VisionStudio-Setup.exe`, and its SHA-256 checksum. WebView2 is downloaded during the initial build and embedded for offline installation. The installer is English-only and preserves runtime data on uninstall.

For local installation tests without administrator access:

```powershell
npm run build:installer:qa
npm run test:installer
```

The distinctly named QA installer packages the existing release payload for the current user. The test installs into a unique QA directory, checks its shortcut and uninstall registration, runs the installed desktop, uninstalls it, and checks data preservation. This does not verify the production installer's elevated path or a clean machine. See the [installer instructions](installer/README.md).

## Backend executable (Phase 1)

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

The local smoke test relocates the bundle, sanitizes its environment, checks loaded runtime DLLs and English API responses, and validates startup, shutdown, and port failures. It keeps JSON evidence and logs under `%LOCALAPPDATA%\VisionStudio\qa`. A passing local test does not close the clean-Windows gate.

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

Runtime storage defaults to `%LOCALAPPDATA%\VisionStudio\`, with `data`, `projects`, `logs`, and `webview` directories. The workspace database is `data/visionstudio.db`; each project owns `projects/{project-id}/` with `dataset`, `models`, `runs`, and `events` subfolders. Backend logs rotate under `logs/backend.log`; WebView2 keeps its cache in `webview`. No runtime files are written into the installation directory.

`test:desktop` starts the built desktop app, inspects its actual WebView2, checks backend connectivity, closes the window through Tauri, and verifies that the API stops. It enables a local debug port only for that test process; normal launches do not enable remote debugging. Desktop shutdown closes a lifetime pipe so both the Windows Python redirector and its backend process exit.

The API exposes `GET /health`, `GET /system/info`, project management on `/projects`, and OpenAPI documentation at `/docs`. It binds to `127.0.0.1` only. Failures use one English envelope, `{"error": {"code", "message"}}`.

The workspace database is created on first start using the standard library `sqlite3` module, so no database server is involved. Schema changes are append-only migrations keyed to `PRAGMA user_version`; a database written by a newer application version is refused rather than downgraded. Phase 8 uses Pillow 12.3.0 for image validation and thumbnails. AI runtime, model download, annotation, and camera access remain planned.

## Import images

Open a project, or choose one on the Dataset page. Use **Select images** or drop multiple JPG/JPEG, PNG, or WEBP files onto the import area. Each still image may be up to 25 MiB and 25 million pixels. Imports show progress, skip identical file contents, and report individual failures with a retry action.

Original bytes are copied into the project's `dataset/images` folder with unique filenames; the original names remain in SQLite. Oriented thumbnails are stored in `dataset/thumbnails`. The latest 20 results are shown after an import, and the saved count persists across reloads.

## Browse the dataset

Use **View dataset gallery** in a project, or choose the project on the Dataset page. Each page displays up to 60 thumbnails with filenames, dimensions, and annotation status. **Previous page** and **Next page** keep browsing bounded for larger datasets. Select a thumbnail to preview the original image; use **Close preview** or Escape to return.

**Delete** asks for confirmation before removing an image and its annotations. Image counts and the gallery refresh after imports and deletions. Locked files are queued for cleanup on the next deletion or application start. Annotation editing begins in later phases; new images initially show **Not annotated**.

Lockfiles: `package-lock.json`, `desktop/Cargo.lock`, `backend/requirements-dev.lock`, and `backend/requirements-build.lock`. The Python locks capture the tested Windows/Python 3.10 environment; regenerate and verify them deliberately when changing the supported Python baseline or dependencies.
