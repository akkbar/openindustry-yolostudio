# Phase 8: image import

Implementation date: 2026-09-15. This phase implements the Image Import scope in `phase-plan.md`, using the upload details from `step.md`. The full dataset gallery remains Phase 9.

## Behavior

Open a project and use **Import images**, or select a project on the Dataset page. **Select images** accepts multiple files; the drop area accepts file drag-and-drop. Files are processed two at a time with progress, per-file errors, and retry for failed files. Imported files remain saved when navigating away; outstanding client requests are cancelled. Retries are safe because identical file contents are detected per dataset.

JPG, JPEG, PNG, and WEBP still images are supported. Each file is limited to 25 MiB and 25 million pixels. The backend checks the extension against the actual decoded format, rejects damaged and animated files, and generates a JPEG thumbnail with a maximum edge of 256 pixels. EXIF orientation is applied to thumbnail pixels and reported dimensions. Transparent images are composited onto white for their thumbnails.

Original bytes are copied unchanged to `projects/{project-id}/dataset/images/{image-id}.{extension}`. Thumbnails go to `dataset/thumbnails/{image-id}.jpg`. Original names are preserved in SQLite; generated identifiers prevent name collisions and Windows path restrictions from overwriting source or project files. Failed writes roll back the database transaction and remove files created by that request. Imports and project deletion serialize their filesystem changes through the database write lock.

The import panel shows the latest 20 successful or duplicate results, with generated thumbnails, plus errors for failed files. The persisted image count survives reload and restart. This is an import result view; browsing the full dataset, annotation status, and opening full images belong to Phase 9.

## Implementation

- `backend/app/image_import.py`: bounded binary upload, image validation/decoding, original storage, thumbnails, duplicate handling, summary, and thumbnail responses.
- `POST /projects/{id}/datasets/images?filename=...`: one binary image per request with `Content-Type: application/octet-stream`. Returns an `imported` or `duplicate` result. The frontend handles batching and progress.
- `GET /projects/{id}/datasets/summary`: persistent image count.
- `GET /projects/{id}/datasets/images/{image-id}/thumbnail`: project-scoped JPEG thumbnail.
- Database migration 2 adds `thumbnail_path` and a unique non-null content-hash index per dataset without changing released migration 1. A Default dataset is created on the first successful import.
- Pillow 12.3.0 is pinned in the runtime requirements and build lock chain. Its Windows wheel supports the Python 3.10 baseline; see [Pillow Python support](https://pillow.readthedocs.io/en/stable/installation/python-support.html). OpenCV, PyTorch, and training libraries remain deferred.
- Tauri `dragDropEnabled: false` lets WebView2 deliver HTML file-drop events on Windows, as required by the [Tauri configuration reference](https://v2.tauri.app/reference/config/). File drops outside the import area are prevented from navigating the application. CSP permits thumbnails only from the existing loopback API in addition to local assets.
- UI copy stays in `frontend/src/locales/en.ts`; numbers use `en-US`. User names remain unchanged.

## Verification

Executed on the Windows developer host on 2026-09-15:

| Check | Result |
| --- | --- |
| `npm run build` | Passed |
| `npm run test:backend` | 59 passed |
| `npm run test:e2e` | 22 passed |
| `npm run check:desktop` / `npm run test:rust` | Passed / 1 passed |
| Packaged debug desktop | Passed, including image import |
| Final frozen backend | 51 checks passed |
| Release desktop | Normal launch/import/reload/close, missing-backend recovery, and parent-crash cleanup passed |
| `npm run test:installer` | 17 current-user QA checks passed, including the installed desktop's image-import test |

The production NSIS installer is `artifacts/VisionStudio-Setup.exe` (230,108,995 bytes). SHA-256: `55b4a21c4a3e6f21458984a2c97d87048a3b6cc3e8f503add763bfc11ab7b73c`.

The initial release build compiled successfully but bundling failed during Microsoft's WebView2 URL lookup with a DNS error. Retrying `node scripts/desktop.mjs bundle --bundles nsis --verbose` succeeded using the cached offline payload. The interrupted bundler left its NSIS marker in the release executable; the unique marker was restored to its original portable value before staging the portable folder and creating the QA installer.

Local reports are retained under `%LOCALAPPDATA%\VisionStudio\qa`:

- Debug desktop: `Desktop f4a08210-ecd1-4a4e-86c2-d5978571fe5c/report.json`.
- Final frozen backend: `Phase 1 851aa8548b0940a7811a1f39908f41a1/report.json`.
- Release normal: `Desktop cb603fc9-3c85-4ea4-83fa-63b2705b6e01/report.json`.
- Release missing backend: `Desktop 299dae50-8048-400c-abaf-9f3211fb9ee9/report.json`.
- Release parent crash: `Desktop c556ee8c-2860-4bb6-817c-df804e11ad8e/report.json`.
- Installed desktop: `Desktop 6e1ed97d-1b5c-4c8a-8cd4-f74bbc97b8b0/report.json`.
- Installer: `Installer ec4d7c5c33ba400e9ac2b45cc12c24f4/report.json`, also copied to `artifacts/installer-qa-report.json`.

QA installation verified the installed executable against the portable release with only Tauri's expected NSIS marker difference, and every installed backend resource against the build manifest. Uninstall removed the application, shortcut, and registry entry while preserving a user-data sentinel. No desktop or backend process remained after the checks. The separate QA installer SHA-256 is `fc3a308098f0579fda2b77ed7c133c77ee72fc56e55eea2bd390c237547f1a53`.

Backend tests cover all four extensions, original-byte preservation, thumbnail dimensions, EXIF orientation, 105 varied images, restart persistence, concurrent duplicate import, project isolation, same-name files, invalid input, byte/pixel limits, failed thumbnail-write rollback, and migration of an existing Phase 7 database.

Browser tests cover multi-file selection, drop events, duplicate skipping, 105 images with progress, retained counts, bounded results, retry after a connection failure, invalid files alongside valid files, and import from a project at the minimum desktop width. They run against the real backend with an `id-ID` browser locale and isolated QA storage.

The desktop verification script also imports four formats and 105 varied images through the actual packaged WebView2, checks generated thumbnails, delivers file drag events through CDP, and verifies retained counts after reload. This does not claim a physical Explorer drag gesture was manually exercised. The developer test runner uses Python to generate fixtures; the tested desktop process receives a minimal environment with no Python on PATH and starts its bundled backend executable.

## Remaining acceptance

The user previously requested leaving clean-Windows testing pending because no clean PC/VM is available. Elevated production installation and first WebView2 installation on a clean offline machine also remain pending. Local tests do not close those gates.
