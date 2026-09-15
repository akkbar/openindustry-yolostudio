# Phases 5–7: database, projects, and project storage

Implementation date: 2026-09-15. The user supplied `files.zip` containing a patch and full replacement files from Claude and requested implementation. The patch was reviewed against the existing repository and canonical `phase-plan.md`, then applied and corrected. Verification claims inside the attachment were treated as supplied context; the results below come from this Windows workspace.

Status: **implementation and local Windows verification complete through Phase 7**. Clean-machine and elevated production installation acceptance remain pending as agreed.

## Delivered

Phase 5 creates `data/visionstudio.db` automatically under `%LOCALAPPDATA%\VisionStudio`. SQLite runs in-process using Python's standard library, with no database server or new Python package. The first schema contains `projects`, `datasets`, `images`, `classes`, `annotations`, `models`, `training_jobs`, `cameras`, and `events`. Foreign keys, WAL, a busy timeout, and versioned migrations are enabled. Migration version checks and upgrades share a write transaction to prevent races between simultaneous desktop launches. Future schemas are refused with an English message.

Phase 6 adds list/create/read/update/delete endpoints on `/projects` and a functional Projects page. Users can create, rename, edit descriptions, open, and confirm deletion. Opening a project uses `#Projects/{id}`, displays its overview and storage location, and survives reload and browser history. Dataset, model, camera, and runtime tools inside the overview remain explicitly planned. Task type is currently Object detection.

Names and descriptions are stored exactly as entered, including Unicode, repeated spaces, and line breaks. A separate normalized, case-folded name key prevents duplicate names without rewriting user content. All application-owned text remains English; frontend copy lives in `frontend/src/locales/en.ts`, dates and numbers use `en-US`, and HTML language stays `en`. Dialogs retain errors and entered values, trap keyboard focus, support Escape, and restore focus when closed.

Phase 7 creates `projects/{project-id}/dataset`, `models`, `runs`, and `events` beneath the writable root. Reading a project repairs missing folders while holding the same database write lock used for deletion. Generated identifiers and resolved paths restrict storage operations to the intended project directory; redirected project folders are rejected.

## Corrections to the supplied patch

- Implemented Open, which the attachment left as a later-phase placeholder despite the Phase 6 acceptance requirement.
- Preserved user text exactly; the supplied validators collapsed name whitespace and stripped descriptions.
- Serialized migration initialization and folder repair against concurrent mutations.
- Corrected annotation foreign-key timing so deleting a project can cascade through both its classes and annotated images in one transaction.
- Made folder deletion recoverable. The folder is first renamed to a reserved `.deleted-{id}` sibling inside a database transaction. A rename failure, including a Windows directory lock, leaves the row and folder intact and returns an English conflict. After commit, cleanup removes the staged folder. If files remain locked, cleanup is retried at the next backend start. If interruption occurs before the database deletion commits, recovery restores the live project's folder. Cleanup touches only validated generated staging paths.
- Added English storage/unexpected-error responses and keyboard focus containment; corrected browser tests that matched two storage fields or failed to reload before simulating an outage.
- Extended native and frozen-bundle checks to exercise project operations and persistence, using isolated QA data rather than the user's workspace.

## Local verification

| Check | Observed result |
| --- | --- |
| Frontend typecheck and production build | Passed |
| Windows/Python 3.10 backend tests | 42 passed |
| Browser integration with `id-ID` locale | 17 passed |
| Tauri desktop compilation check | Passed |
| Packaged debug desktop, including project CRUD and Open | Passed |
| Frozen backend with bundled SQLite and restart persistence | 38 checks passed |
| Relocated release desktop, including project CRUD and Open | Passed |
| Missing-backend English recovery screen | Passed |
| Abrupt desktop termination and backend cleanup | Passed |
| Primary NSIS installer build | Passed |
| Current-user QA install, installed project workflow, and uninstall | 17 checks passed |

The successful QA installation was uninstalled. Its application files, desktop shortcut, and uninstall registration were removed; user data and QA evidence were retained. No claim is made that the primary elevated installer or a clean Windows machine was tested.

Source tests cover database initialization and concurrency, version refusal, constraints and annotation cascades, restart persistence, exact user text, duplicate names, CRUD, folder repair, failed creation rollback, staged deletion recovery, deferred cleanup, and a real Windows directory handle that prevents deletion.

Browser tests run with an Indonesian browser locale and a fresh `%LOCALAPPDATA%\VisionStudio\qa\Browser ...` directory. They cover the shell, project lifecycle, workspace reload/history, keyboard focus, minimum window size, errors, and recovery. Native tests inspect the actual WebView2 and bundled backend process while running create/open/reload/rename/delete against a relocated executable or the installed QA application.

The backend suite still reports two upstream Starlette deprecation warnings. PyInstaller reports the previously documented optional `tzdata` import; these phases do not use named timezone conversion. The actual frozen API, SQLite, and project checks passed.

## Artifacts and evidence

- Primary installer: `artifacts/VisionStudio-Setup.exe`, 226,892,857 bytes (approximately 216 MiB). SHA-256: `d76e420e92af003168716b8f9e943e7973bb15deb8089e31ad8c2afe64495e72`.
- QA installer: `artifacts/VisionStudio-QA-Setup.exe`. SHA-256: `0033bc0704e262256a73598906e0065cc01b2abdd996312f6d2eb3cf8361f2c5`.
- Portable release application: `artifacts/desktop/VisionStudio.exe`, with its complete adjacent `backend` directory.
- Installer report: `artifacts/installer-qa-report.json`, with `passed: true`, `production_per_machine_verified: false`, and `clean_machine_verified: false`.
- Frozen-backend report: `%LOCALAPPDATA%\VisionStudio\qa\Phase 1 43652f8d882241b1ba251488ea6f9e43\report.json`.
- Relocated release report: `%LOCALAPPDATA%\VisionStudio\qa\Desktop 0c158ffc-c26c-4440-8ff9-aa2736bbf9a9\report.json`.
- Missing-backend report: `%LOCALAPPDATA%\VisionStudio\qa\Desktop f6b42818-9796-4b29-8363-28236c884133\report.json`.
- Parent-crash report: `%LOCALAPPDATA%\VisionStudio\qa\Desktop fcebc317-25a0-4eaa-8a09-8fddfddb5257\report.json`.
- Installed project-workflow report: `%LOCALAPPDATA%\VisionStudio\qa\Desktop e6a0d030-13e2-4e20-8c0c-dd7b47dd5121\report.json`.
- Inspected browser screenshots: `test-results/project-workspace.png` and `test-results/projects-small.png`; native project screenshot: `test-results/desktop-projects.png`.

Artifacts and reports are ignored by Git. Rebuilds can change checksums; use the `.sha256` file beside the installer being tested. Earlier phase documents preserve historical build evidence, while these artifacts contain the Phase 7 implementation.

## Packaging and remaining acceptance

PyInstaller explicitly includes `sqlite3` and its binary runtime. Build and verification commands remain in the root README. The standalone backend smoke test now checks database creation, project folders, CRUD, and persistence after restarting the executable, in addition to the existing loopback/lifecycle checks.

The current-user QA installer is a separately named variant for local install/launch/uninstall testing. It does not verify elevated installation in `Program Files`. The previously accepted pending items remain pending: a clean Windows machine without development tools, elevated production installation, and first WebView2 installation on a clean offline machine.

Phase 8 image import has not started. No AI runtime, training dependencies, image import, annotation UI, or camera access is introduced in these phases.
