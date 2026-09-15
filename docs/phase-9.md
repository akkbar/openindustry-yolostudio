# Phase 9: dataset gallery

Implemented on 2026-09-15. `phase-plan.md` defines the thumbnail grid, filenames, annotation status, dimensions, scrolling, and opening images. `step.md` Step 2.3 additionally specifies deletion; Phase 9 includes confirmed image deletion. Class management and annotation editing remain later phases.

## Behavior

The Dataset page displays the selected project's images in a responsive grid, with 60 cards per page. Thumbnails use lazy loading, asynchronous decoding, and fixed display dimensions. Previous/next controls keep the DOM bounded even for large datasets. Changing pages returns focus and scroll to the gallery heading. This avoids loading every original while browsing.

Each card shows the preserved filename, oriented pixel dimensions, and the database's annotated flag. New imports are not annotated. The original preview uses a native modal dialog with Escape dismissal, keyboard focus containment, and focus restoration. Missing previews have an English error and retry action. The existing original bytes are served unchanged with their image media type; the browser applies EXIF orientation.

Deletion requires a separate confirmation. It removes the image and associated annotations, updates the gallery and import count, and removes original and thumbnail files. If Windows locks a file, the database deletion remains durable and the file is queued for cleanup at startup or the next deletion. Reimport uses a new generated filename, so deferred cleanup cannot remove the replacement. Empty pages after concurrent deletion fall back to the last available page.

All frontend copy is centralized in `frontend/src/locales/en.ts`. Numbers use `en-US`; user filenames remain unchanged. Runtime data stays under `%LOCALAPPDATA%\VisionStudio`.

## Implementation

- `GET /projects/{id}/datasets/images?offset=0&limit=60`: deterministic oldest-first pagination, total count, thumbnail/original URLs, annotation status, and dimensions. Limit is bounded to 1–100; negative offsets are rejected.
- `GET /projects/{id}/datasets/images/{image-id}/original`: project-scoped original bytes with `no-store` and `nosniff` headers. Files are resolved only inside reserved project image directories.
- `DELETE /projects/{id}/datasets/images/{image-id}`: remove metadata/annotations and commit a file-cleanup queue in one SQLite transaction. Cleanup serializes filesystem changes with imports and project deletion.
- Migration 3 adds `pending_image_files` and the image-order index. Released migrations are unchanged. An existing first-open WAL race is handled with a bounded retry during connection setup; failed connections are closed.
- `Gallery.tsx` owns pagination, preview, loading/retry/empty states, and deletion confirmation. Dataset import completion refreshes the gallery; deletion refreshes the count and clears stale import thumbnails. Project overview links to its dataset gallery.

## Verification

Source build passed. Backend: 71 tests passed. Browser: 25 tests passed against the real backend with an Indonesian browser locale.

Backend coverage includes 105 images across pages, stable order, both annotation states, exact original bytes, Unicode names, project isolation, parameter bounds, missing/corrupt paths, annotation/file cleanup, failed-delete rollback, simulated file-lock recovery across restart, safe reimport, and migration from schema 2.

Browser coverage includes responsive scrolling at 900×640, bounded 60/45-card pages for 105 images, original preview, focus restoration, cancel/confirm deletion, persisted removal, live import refresh, and recovery from gallery/preview/delete failures. These checks verify functional scrolling and bounded rendering; they are not a frame-rate benchmark.

`npm run build:installer` passed and regenerated the release portable folder, frozen backend, portable backend QA kit, and production NSIS installer. The installer includes the offline WebView2 payload. `artifacts/VisionStudio-Setup.exe` is 230,097,115 bytes; SHA-256 is `e50a1f7afa0e9123ec53825892a53164bb8df128f2a98cd9ec314a2c16efa911`.

The frozen backend passed 57 checks. Release native WebView2 tests passed normal close, English missing-backend recovery, and parent-crash cleanup. The normal and crash runs import four formats plus 105 files, browse the resulting 109-image gallery, open an original, delete one image, and verify the retained 108-image count after reload. The desktop runs outside the repository with a sanitized environment and no Python on PATH. The developer test runner uses Python only to prepare fixtures. Native and browser screenshots were visually inspected. No Rust source changed in this phase.

Local reports under `%LOCALAPPDATA%\VisionStudio\qa`:

- Frozen backend: `Phase 1 0824d00b1b7449f9b2de8f5c29cc4c2e/report.json`.
- Release normal: `Desktop 182765ed-f735-4cac-bd16-7700228874d5/report.json`.
- Release missing backend: `Desktop 12615962-cecf-4510-94e4-7ef0031ca355/report.json`.
- Release parent crash: `Desktop 85040616-0289-4008-87a3-120dafd370e1/report.json`.
- Installed desktop: `Desktop e639ff08-4e0f-43ce-a345-f5e9c7a455df/report.json`.
- Installer QA: `Installer 25e1ab09deab477ea884b8b5a331d754/report.json`, also available at `artifacts/installer-qa-report.json`.

`npm run build:installer:qa` and all 17 `npm run test:installer` checks passed. The installed desktop completed the import/gallery/preview/delete workflow and matched the release payload, including Tauri's expected NSIS marker difference. Every installed backend resource matched the build manifest. Uninstall removed the application, shortcut, and registry entry while preserving the user-data sentinel. No desktop or backend process remained afterward. The QA installer SHA-256 is `dde3a70ada6aaa4ed284036d0e8411d26d78518eefb32b77863677857dcde01c`.

## Remaining acceptance

Clean Windows without development tools, elevated production installation, and first offline WebView2 installation remain pending under the user's earlier decision. Local QA does not close those gates. Phase 10 has not started.
