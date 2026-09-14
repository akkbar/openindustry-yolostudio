# Vision Studio

Industrial computer vision applications, from dataset to production, without writing Python. This repository currently implements **Phase 0: development foundation**.

The application always uses **English**, including errors and default content. User-entered data is preserved as entered. The source planning documents retain their original language.

## Planning

Read [the comparison and decisions](docs/plan-comparison.md) first. `phase-plan.md` controls execution order; `step.md` supplies feature task details; `Overall-plan.md` defines product direction. See [Phase 0 verification](docs/phase-0.md) for current acceptance evidence. The next phase is the backend executable proof of concept.

## Development on Windows

Prerequisites: Node.js 22.12+ (24 supported), Python 3.10+, Rust stable with the Windows MSVC target, Visual Studio C++ build tools and Windows SDK, and Microsoft Edge WebView2. These are developer requirements; the final installer must bundle its runtime dependencies. See [Tauri prerequisites](https://v2.tauri.app/start/prerequisites/).

From the repository root:

```powershell
npm ci
npm run setup:backend
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
```

Stop browser development servers before running E2E tests; tests own ports 1420 and 8765. E2E tests connect to the real API, exercise failure/recovery, and verify English UI under an Indonesian browser locale.

`build:desktop` creates `desktop/target/debug/vision-studio.exe` with embedded frontend assets, but still requires this repository and its Python virtual environment. It is a development executable, **not a standalone distribution**. Backend packaging, bundled sidecar readiness/supervision, and NSIS installer proof are Phases 1, 2, and 3.

## Repository

```text
frontend/     React + TypeScript + Vite; English copy in src/locales/en.ts
backend/      FastAPI, local storage paths, API tests
desktop/      Tauri 2, development backend lifecycle
scripts/      Development and verification commands
installer/    Windows packaging strategy
data/         Ignored development fixtures only
docs/         Planning decisions and phase evidence
tests/        Browser integration tests
```

Runtime storage defaults to `%LOCALAPPDATA%\VisionStudio\`, with `data`, `projects`, and `logs` directories. Backend logs rotate under `logs/backend.log`. No runtime files are written into the installation directory.

The API exposes `GET /health`, `GET /system/info`, and development OpenAPI documentation at `/docs`. It binds to `127.0.0.1` only. Phase 0 has no database, AI runtime, model download, project CRUD, or camera access. Navigation for future features displays an explicit planned state.

Lockfiles: `package-lock.json`, `desktop/Cargo.lock`, and `backend/requirements-dev.lock`. The Python lock captures the tested Windows/Python 3.10 environment; regenerate and verify it deliberately when changing the supported Python baseline or dependencies.
