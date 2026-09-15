# Phases 11–12: bounding-box annotations and productivity

Implemented on 2026-09-15 using the canonical scope in `phase-plan.md` and annotation details in `step.md` Steps 4.1–4.6. Core canvas interactions were tested before enabling Phase 12 keyboard shortcuts. Phase 13 export has not started.

## Delivered behavior

**Annotate** opens a dedicated editor from each gallery card. The original preview remains available separately. The editor renders the oriented original with an SVG box overlay. Users can draw, select, move, resize with four corner handles, reassign a class, and delete boxes. Drawing uses the active project class from Phase 10; the editor includes a class selector and a selectable box list.

The view supports wheel/button zoom (25%–1,200% relative to fit), pan mode or middle-button pan, fit, and reset. Pointer coordinates are transformed back to normalized image coordinates; movement and resizing stay inside the image. Subpixel boxes smaller than one original-image pixel are discarded. Cancelling a pointer gesture restores the last saved geometry. Zoom and pan do not change saved coordinates.

Each completed edit saves automatically. The editor reports loading/saving/saved/error states. A failed save retains the draft, disables further edits and navigation, and offers retry or confirmed discard/reload. Closing the editor and Escape dismissal are blocked while saving or an unsaved change remains. A browser unload warning covers an outstanding save; a forced process termination during an unacknowledged write is not a guaranteed save.

Previous/Next navigate the full project's deterministic image order, independently of gallery pagination. A/D provide the same navigation. Delete removes the selected box; 1–9 select the first nine listed classes, even when stable class indices have gaps. Shortcuts are limited to the open editor, ignore editable controls, modifier combinations, and key repeats, and do not navigate while a save is outstanding. Escape cancels an active gesture.

The editor displays **Annotated N / total**, counting images with at least one saved annotation. Deleting the final box clears that image's annotation flag. The gallery refreshes statuses when the editor closes, and class usage refreshes so referenced classes remain protected. Explicit review of empty/negative images is not part of these phases.

## API and data integrity

Base route: `/projects/{project-id}/datasets/images/{image-id}/annotations`.

- GET returns boxes, image metadata, revision, previous/next IDs, position, total, and annotated-image count.
- POST creates a box with a client-generated 32-character hex ID, project-owned `class_id`, normalized `center_x`, `center_y`, `width`, `height`, and `expected_revision`.
- PATCH `/{annotation-id}` replaces that box's class and geometry with an expected revision.
- DELETE `/{annotation-id}?expected_revision=...` removes a box.

All mutations return the saved annotation state. The backend validates finite, positive dimensions, normalized bounds, project/image/class ownership, and optimistic image revision inside a SQLite write transaction. An outdated edit returns an English 409 conflict. Exact creation/update retries and repeated deletion are idempotent, so a lost response does not duplicate an annotation or repeat a geometry change. Image annotation status and revision change in the same transaction as the boxes.

Migration 5 appends `images.annotation_revision`. Existing box IDs and coordinates remain unchanged. No vision/training dependency was introduced. Frontend copy remains in `frontend/src/locales/en.ts`, numbers use `en-US`, and user names are preserved. Runtime files remain under `%LOCALAPPDATA%\VisionStudio`.

Coordinates refer to the EXIF-oriented image shown in the editor. Future exports must preserve that orientation when pairing image pixels with annotation coordinates.

## Verification

- Frontend production build passed.
- 99 backend tests passed, including normalized CRUD, restart persistence, neighbors and boundaries, project/class isolation, invalid coordinates, concurrent writer conflicts, idempotent retries, annotation progress, class protection, and schema-4 migration.
- 33 browser tests passed against the actual backend with `id-ID` locale. Annotation coverage includes draw/reload/move/resize/reassign/delete, zoom/pan/fit, failed-save retry, blocked navigation, stale-write conflict/discard confirmation, shortcuts, editable-control isolation, counters, and 900×640 layout. The editor screenshot was visually inspected.

E2E moved to dedicated configurable ports after finding the user's development ports occupied. Default QA ports are 18765 and 11420; a test-only Vite proxy keeps browser requests same-origin. Each run still gets isolated runtime storage and refuses to reuse another server. Production CORS remains unchanged.

`npm run build:installer` passed, regenerating the backend, portable QA kit, release desktop, and production NSIS installer with offline WebView2. `artifacts/VisionStudio-Setup.exe` is 230,112,277 bytes; SHA-256: `0d26ca23ffab871ba75918c8bd1cc076c79a2b3c570fae53f6f5aadeac4f8521`.

The frozen backend passed 69 checks, including annotation creation/retry, restart persistence, geometry updates, deletion, and annotation counts. The final frontend loading-state adjustment also passed a targeted rerun of all four annotation browser tests.

Release WebView2 tests passed the complete existing project/import/gallery/class workflow plus drawing a box, closing the actual desktop, waiting for its backend to stop, relaunching the same executable with the same isolated data directory, and comparing all four normalized rectangle values exactly. The reopened editor passed A/D navigation and Delete. Separate missing-backend and final parent-crash cleanup scenarios also passed. The native screenshot was visually inspected. No Rust source changed.

The current-user QA installer build and all 17 install/launch/uninstall checks passed. The installed application also passed the actual close/relaunch annotation persistence workflow. Checks verified installed executable/resource hashes, shortcut and registry creation/removal, and preservation of a user-data sentinel after uninstall. `artifacts/VisionStudio-QA-Setup.exe` SHA-256: `43a1f379fba2b85fb4c96ededae285aa451bad2d1d37ccfca6033392a8734295`. No QA desktop or bundled backend process remained after verification.

The desktop runs outside the repository with a sanitized environment and no Python on PATH. The developer test runner uses Python only to generate image fixtures. Local reports under `%LOCALAPPDATA%\VisionStudio\qa`:

- Frozen backend: `Phase 1 c622560405f84283861e20e16887729f/report.json`.
- Release normal/restart: `Desktop 2e908a6a-15c7-4a05-bc94-8171f3fe1156/report.json`.
- Release missing backend: `Desktop 9e5a84a2-29d0-486d-bcb8-d9b47ef22f41/report.json`.
- Release parent crash: `Desktop 9ce8ed88-4a49-40f0-b0cf-8b12f3094bda/report.json`.
- Installed desktop/restart: `Desktop d0c90fb0-2615-497a-b690-62206bf73258/report.json`.
- Installer: `Installer c733cc7c840a448e8cc0b5b198cb5759/report.json` (also copied to `artifacts/installer-qa-report.json`).

## Remaining acceptance

Clean Windows without development tools, elevated production installation, and first offline WebView2 installation remain pending under the user's earlier decision. Local QA does not close those gates.
