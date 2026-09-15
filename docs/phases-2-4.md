# Phases 2–4: desktop packaging and application shell

Status on 2026-09-15: **implementation and local verification complete through Phase 4; clean-Windows and elevated production installation acceptance pending**. Execution follows `phase-plan.md`; phase numbers in `step.md` describe a different feature sequence. The user authorized work through Phase 4 after explicitly leaving the unavailable clean-Windows/no-Python acceptance pending. Phase 5 database work has not started.

## Phase 2: desktop executable

Packaged debug and release builds launch `backend/backend.exe` relative to the desktop resources. They include the frontend and the complete Python runtime folder and work outside the repository. Development mode continues to use `.venv`; mode selection follows Tauri's generated `dev` configuration, including when Tauri enables its dependency feature directly.

The desktop reserves a dynamic loopback port, launches the backend without a console window, and waits up to 20 seconds for the expected health service and version before opening the UI. The backend retains a lifetime pipe from the desktop. Closing the window or abruptly terminating the parent closes that pipe and shuts down the backend. A missing bundle produces an English recovery screen. Readiness failures are written to `logs/desktop.log`; backend launch output goes to `logs/backend-launch.log`.

The native test relocates the entire application outside the repository, launches it with development tools absent from PATH, inspects its actual WebView2, and verifies that the child process path points to the relocated `backend.exe`. It checks English UI, packaged mode, separate writable storage, normal shutdown, missing-backend recovery, and parent-crash cleanup. Test reports and runtime logs remain under `%LOCALAPPDATA%\VisionStudio\qa`.

## Phase 3: installer executable

`artifacts/VisionStudio-Setup.exe` installs the desktop, backend resources, bundled Python, and offline WebView2 runtime. The primary NSIS configuration is English-only, Windows x64, and per-machine, with default destination `C:\Program Files\VisionStudio`. It adds shortcuts and an uninstall entry. Runtime storage remains `%LOCALAPPDATA%\VisionStudio`, and uninstall retains user data. Build output includes a SHA-256 sidecar and the generated NSIS source for inspection.

The current host is not elevated. `VisionStudio-QA-Setup.exe` therefore provides a separately named current-user installation of the same release payload for local QA. The installation test verifies the executable byte-for-byte (accounting for Tauri's three-byte NSIS bundle marker), every backend resource against its SHA-256 manifest, shortcuts, registration, native application launch/shutdown, uninstall removal, and data preservation. QA metadata explicitly does not claim production per-machine or clean-machine verification. The test waits for the temporary NSIS uninstaller to finish removing files, shortcuts, and registration.

The offline WebView2 installer is embedded, but this host already has WebView2. Its first installation on a clean offline machine remains an acceptance item. See [the clean-Windows procedure](../installer/README.md).

## Phase 4: base shell

- Dashboard, Projects, Dataset, Models, Cameras, Runtime, and Settings navigation, with hash routing, reload persistence, history, and keyboard focus management.
- Live backend connection indicator, retry behavior, application version, CPU/OS information, storage location, and native data/log folder actions.
- An English render-error recovery screen and explicit planned states for later features.
- All frontend copy centralized in `frontend/src/locales/en.ts`, explicit `en-US` number formatting, and `<html lang="en">`. The UI never derives its language from the OS or browser.
- Windows 11 workstation builds are displayed correctly despite their NT 10.0 kernel version. Tests also preserve Windows 10 and Windows Server labels.

No database, AI dependencies, training, project management, annotation, or camera functionality is introduced in these phases.

## Verification and remaining acceptance

| Check | Result |
| --- | --- |
| Frontend production build (`npm run build`, also run by packaging) | Passed |
| Backend source API tests | 9 passed |
| Frozen backend regression | 26 checks passed |
| Browser integration | 5 passed, including `id-ID` locale, failure/recovery, history, and 900 × 640 navigation |
| Rust check, readiness unit test, formatting check | Passed; 1 unit test |
| Packaged debug native test | Passed |
| Relocated release native test | Passed; packaged backend process path confirmed |
| Missing-backend release test | Passed; English recovery screen remains usable |
| Abrupt parent termination | Passed; backend API shuts down |
| Primary NSIS build and generated configuration inspection | Passed; per-machine, English-only, offline WebView2 |
| Current-user QA install/launch/uninstall | 17 checks passed |
| Clean Windows without Python/development tooling | Pending; unavailable |
| Elevated primary installer in `Program Files` | Pending; not executed |
| First WebView2 installation on a clean offline machine | Pending; host already has WebView2 |

The final installer is `artifacts/VisionStudio-Setup.exe`, 226,218,598 bytes (approximately 216 MiB), SHA-256 `7312e8ba6963916d2c591b649b773d48b1bfa91e4af3b141a4f7fbec5cb1f05f`. Its size includes the offline WebView2 installer. The separate QA artifact is `artifacts/VisionStudio-QA-Setup.exe`, SHA-256 `c180d891045a4bfdc9805b71484050246994a64883544e039b40c739365cbc55`. Rebuilds may change checksums; always retain the matching `.sha256` file.

Evidence:

- `artifacts/installer-qa-report.json`: final successful 17-check current-user installation report, with both pending gate flags explicitly false.
- `artifacts/VisionStudio-Setup.exe.nsi` and `artifacts/VisionStudio-QA-Setup.exe.nsi`: generated primary and QA installer configurations.
- `test-results/desktop.png` and `test-results/desktop-missing-backend.png`: inspected native screenshots.
- `%LOCALAPPDATA%\VisionStudio\qa\Phase 1 a30f1d97e494446ea54c6e021f5ed89d\report.json`: final frozen-backend regression.
- `%LOCALAPPDATA%\VisionStudio\qa\Desktop 1b6887b8-ea21-4a68-b62b-0c960db665ec\report.json`: relocated release.
- `%LOCALAPPDATA%\VisionStudio\qa\Desktop b1fd842d-6dbd-427a-aa1d-2fbf5f09c32f\report.json`: missing backend.
- `%LOCALAPPDATA%\VisionStudio\qa\Desktop f2510b53-84a3-4eb4-98d0-98111d59bd66\report.json`: parent crash cleanup.
- `%LOCALAPPDATA%\VisionStudio\qa\Desktop fbfea38e-8e9f-4174-9f15-8de0a8ba19bb\report.json`: final installed application check.

The test installation was uninstalled successfully. Local QA data and reports remain for review. Artifacts and machine-specific reports are ignored by Git. Clean-machine and elevated production installation acceptance remain pending regardless of developer-host results.

Reproduce with the commands in the [root README](../README.md). Native tests require the developer's Node/Playwright tooling; normal installed application startup does not.

Known build/test messages: the source backend suite reports two upstream Starlette deprecation warnings. PyInstaller reports an optional `tzdata` import; these phases do not perform named timezone conversion, and all frozen API checks pass. Revisit that dependency before adding timezone-aware scheduling or reporting.
