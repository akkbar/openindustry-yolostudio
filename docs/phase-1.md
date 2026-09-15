# Phase 1: backend executable proof of concept

Status on 2026-09-15: **implementation and local verification complete; clean-Windows acceptance pending**. The user explicitly requested leaving that acceptance pending until a clean PC/VM is available, and subsequently authorized continuation through Phase 4. See [Phases 2–4](phases-2-4.md) for subsequent work; this document preserves the original Phase 1 evidence.

## Delivered

- A Windows x64 `backend.exe` with bundled Python 3.10.10, FastAPI, Uvicorn, Pydantic, and required DLLs, built with PyInstaller 6.22.3 in one-directory mode.
- A dedicated, locked build environment and checked-in PyInstaller specification. Optional test tooling and heavy vision libraries are excluded from the executable.
- A frozen entry point with multiprocessing freeze support. Development and executable entry points share the same API implementation and lifecycle behavior.
- Explicit asyncio/h11/lifespan configuration. WebSocket transport is disabled for this minimal API; no optional event-loop or protocol packages are required.
- A portable QA ZIP with PowerShell tests, runtime file SHA-256 manifest, usage instructions, and an adjacent archive checksum.
- Tests for the actual relocated executable without development tools on its PATH. Reports identify whether the clean-machine gate was requested and verified.

The choice of one-directory packaging follows [PyInstaller's operating-mode guidance](https://pyinstaller.org/en/stable/operating-mode.html): the Python interpreter is bundled, and the folder provides a straightforward packaging baseline. The checked-in [specification](../backend/packaging/backend.spec) is based on the official [spec-file format](https://pyinstaller.org/en/stable/spec-files.html).

## Reproduce

```powershell
npm run build:backend
npm run test:backend-bundle
```

Developer requirements: Windows x64, Python 3.10, and initial access to package downloads. The build automatically creates `.tools/backend-build`, reads `backend/requirements-build.lock`, and writes only to the build/cache and `artifacts` output directories. The environment reuses the locked API/test dependencies; the specification excludes test tooling from the bundle.

Run the API directly:

```powershell
.\artifacts\backend\backend.exe --port 8765
```

The standalone backend does not require the repository, `.venv`, Python installation, Node.js, npm, or pip at runtime. Keep `backend.exe` and `_internal` together. It listens only on loopback and stores runtime data separately from the executable.

## Local verification

| Check | Observed result |
| --- | --- |
| Backend executable build | Passed |
| Portable ZIP creation and CRC check | Passed |
| Extracted ZIP and its included PowerShell QA script | 26 checks passed; included script hash matches the repository script |
| Relocated executable test | 26 checks passed |
| Backend source API regression | 6 tests passed |
| Frontend production build | Passed |
| Browser integration regression | 3 tests passed, including English under `id-ID` |
| Desktop lifecycle regression | Passed with the updated shared backend launcher |
| Clean Windows, no Python installed | Pending; not run |

The 26 executable checks cover API identity/version, CPU/OS/Python data, English responses, writable storage, loaded bundled Python DLLs, allowed/denied CORS origins, OpenAPI, occupied ports, invalid port messages, lifetime-pipe shutdown, standalone startup with closed stdin, loopback binding, and an unchanged bundle directory after execution.

The test creates a fresh copy under `%LOCALAPPDATA%\VisionStudio\qa\Phase 1 <id>\Relocated backend bundle` and launches it from another working directory. The child receives only necessary Windows environment variables, `PATH=%SystemRoot%\System32`, and a separate runtime data directory. Python environment variables and virtual-environment settings are absent. Process inspection confirmed that `python310.dll` loaded from the copied `_internal` directory.

Local evidence is a JSON report and stdout/stderr logs in each QA directory. A passing developer-host report sets `clean_machine_verified` to `false`. Source API tests still emit the two previously recorded upstream Starlette deprecation warnings.

The final archive tested on 2026-09-15 has SHA-256 `1c925ee4e8477400f02c09aa953ec0379a0a3fbb47146276a44d70baf531b347`. Its extracted-kit verification report is `%LOCALAPPDATA%\VisionStudio\qa\Phase 1 c22a691c0de4452abf70fce5701e7899\report.json`. Rebuilding regenerates the manifest timestamp and archive checksum; retain the checksum corresponding to the archive actually used for clean-machine QA.

PyInstaller's missing-module report was reviewed. Remaining entries concern optional or platform-specific imports, including Unix modules, alternate Uvicorn transports/reload workers, Trio, type-checking/test plugins, multipart/email extras, and timezone data. The Phase 1 routes do not use named timezone conversion; `tzdata` must be added and verified when that functionality is introduced. No missing import prevented the actual API, error, or lifecycle checks.

## Clean-Windows handoff

The QA archive is `artifacts/VisionStudio-Backend-0.1.0-windows-x64.zip` (approximately 10.4 MiB; 21.3 MiB for the backend folder). Extract the entire archive onto a clean Windows 10/11 x64 machine without Python. Disconnect external networking after transfer, leaving loopback available, and run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Test-Backend.ps1 -BundlePath .\backend -RequireNoPython
```

Keep the resulting `report.json` with the VM/PC description and the ZIP checksum. The switch rejects detected Python executables/standard registry installations; it is intended for a genuinely fresh VM and cannot prove that an arbitrary existing machine is pristine.

This environment has installed Python, no Windows Sandbox executable, a Linux Docker engine, and insufficient permission to enumerate Hyper-V VMs. No Windows feature or permission was changed. The user confirmed that no clean PC/VM is currently available, so this gate remains pending.

Phase 1 itself added no AI dependencies, database, installer, or project CRUD. Subsequent Phase 2 work now launches the bundled backend from packaged desktop builds, while `npm run dev` keeps the development launcher.
