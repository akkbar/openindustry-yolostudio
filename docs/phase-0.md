# Phase 0: development foundation

Status: implemented and verified locally on Windows x64. Started 2026-09-14; completed 2026-09-15. This is not the standalone distribution checkpoint.

## Scope delivered

| Task | Result |
| --- | --- |
| P00-S01 Repository | React/TypeScript frontend, FastAPI backend, Tauri desktop, scripts, installer strategy, ignored development data, dependency locks, README, environment example, Git repository and configured origin |
| P00-S02 Base API | `/health` and `/system/info`; CPU, architecture, OS, Python/app versions, storage path; explicit frontend CORS origins |
| P00-S03 Desktop lifecycle | Tauri launches a hidden backend on a dynamic loopback port; UI discovers it through IPC; closing the window closes the backend lifetime pipe and stops both Windows Python processes |
| P00-S04 Base UI | Dashboard, Projects, Dataset, Models, Cameras, Runtime, Settings navigation; live backend status; actual system details; explicit planned feature states |
| P00-S05 Language and verification | Central English copy, `lang="en"`, explicit `en-US` formatting, persistent English policy, API/browser/native checks |

Runtime data and WebView2 cache use `%LOCALAPPDATA%\VisionStudio`. Backend logs rotate in `logs/backend.log`. Optional `VISION_STUDIO_DATA_DIR` must be absolute. A native window uses the same override as the backend.

## Verification evidence

| Check | Result |
| --- | --- |
| `npm run setup:backend` | Passed; installs from the Python dependency lock and installs the local backend package |
| `npm run build` | Passed; strict TypeScript check and Vite production assets |
| `npm run test:backend` | 6 passed: health/system contract, writable directories, three frontend origins, rejected untrusted CORS origin, rejected relative data path |
| `npm run test:e2e` | 3 passed: real API connection and navigation under `id-ID`, English failure/recovery, rejection of an unrelated health service |
| `npm run check:desktop` | Passed; locked Cargo dependency check |
| `npm run build:desktop` | Passed; Windows executable with embedded frontend assets |
| `npm run test:desktop` | Passed; actual executable/WebView2 rendered English UI, discovered its owned backend, closed via the Tauri window command, and stopped its API |
| `npm run dev` | Passed; Vite started on port 1420, Tauri loaded the development frontend, and displayed Backend Connected |
| Process inspection after close | No Python process using the desktop `--parent-watch` entry point remained |
| Visual inspection | Dashboard and Settings inspected from browser/native WebView2 screenshots; no clipping or missing content in the tested desktop layout |

Screenshots are generated locally in ignored `test-results/dashboard.png` and `test-results/desktop.png`. The native automation helper was unavailable, so the executable was verified through its actual WebView2 debugging connection and Tauri's public close command. The debug port is only enabled in the test process environment.

Tested tools: Node.js 24.19.0, npm 11.17.0, Python 3.10.10, Rust 1.98.1, Tauri 2.11.5, React 19, Vite 6.4.3, and the installed Windows WebView2 runtime. Backend tests currently emit two upstream deprecation warnings from Starlette's test client (httpx and AnyIO); there are no failing tests.

When the development window closes, Tauri terminates its Vite subprocess. On this Windows setup, the nested npm process prints a termination message with code 4294967295; the root `npm run dev` command exits successfully with code 0, and neither Vite nor the backend remains running. The built executable does not launch Vite or npm.

## Boundaries and next gate

Phase 0 requires the repository and its development Python environment. It does not prove operation on a clean Windows machine without Python. Production startup/readiness presentation, bundled executable supervision, crash restart, installer behavior, offline WebView2 provisioning, and clean-machine QA remain later gates.

Next is **Phase 1: backend executable proof of concept**: freeze the minimal API with PyInstaller, run the resulting backend independently of the development virtual environment, and verify `/health` and `/system/info` on clean Windows without Python before marking that gate complete. Phase 2 connects the packaged backend to Tauri; Phase 3 creates the initial installer. Project CRUD follows at Phase 6.
