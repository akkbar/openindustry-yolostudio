# Phase 10: class manager

Implemented on 2026-09-15. This phase follows `phase-plan.md` for class CRUD and selected-class availability, and `step.md` Steps 3.1–3.2 for stable class indices and sidebar behavior. It does not implement the Phase 11 annotation canvas.

## Behavior and decisions

The Dataset workspace has a Classes sidebar (stacked above the gallery at narrower widths). It supports add, rename, explicit selection, clearing selection, and confirmed deletion. Modal dialogs contain keyboard focus and support Escape dismissal. The class list scrolls within a bounded panel, and long names wrap without widening the workspace.

Names are preserved exactly, including Unicode and surrounding spaces. Blank names, names over 80 characters, and control characters are rejected with English messages. Duplicate checks are per project, case-insensitive, and whitespace-normalized; those normalized values are not substituted for display names. Class color is assigned from a fixed palette using the index and remains stable on rename.

Indices begin at zero and increase monotonically per project. Rename preserves the class ID, index, and color. Deletion does not renumber existing classes or reuse deleted indices, even when the highest or every class is removed. Export in Phase 13 must construct its own dense class-ID mapping without rewriting stored indices.

The first added class is selected automatically when no class is selected. Selection is stored per project and can be cleared explicitly. Deleting the selected class clears the selection. Used classes return an English conflict response without deleting annotations; their names may still be changed without modifying annotation class IDs.

`ProjectClassesProvider` and `useProjectClasses()` expose the class list, selected class, read state, and mutation actions to the workspace. Both the manager and original-image preview consume this shared state. This provides the selection contract for the future annotation canvas; the preview displays the selected class's index and name now. It does not draw annotations.

Frontend copy remains in `frontend/src/locales/en.ts`, formatting uses `en-US`, and names remain user data. No new runtime dependency or AI library was introduced.

## API and persistence

- `GET /projects/{id}/classes`: classes ordered by stable index, annotation usage count, and `selected_class_id`.
- `POST /projects/{id}/classes`: add with `{ "name": "Banana" }`; returns 201.
- `PATCH /projects/{id}/classes/{class-id}`: rename; name is the only accepted field.
- `DELETE /projects/{id}/classes/{class-id}`: returns 204, or 409 when annotations use the class.
- `PATCH /projects/{id}/annotation-state`: set `{ "selected_class_id": "..." }` or clear it with null. IDs from another project are rejected.

Migration 4 appends `project_annotation_state`, with the selected-class foreign key and next-index counter. It initializes counters from existing class indices without changing released migrations or existing class rows. Foreign keys clear a deleted selection and remove state when a project is deleted. SQLite write transactions serialize index allocation, duplicate checks, selection, and deletion.

Frontend mutations are serialized. A successful write followed by a failed refresh closes the completed form and offers a read retry; it does not repeat the write. Project changes cancel outstanding reads and discard old workspace state. Explicit refresh handles changes from another window.

## Verification

- Production frontend build passed.
- 84 backend tests passed, including concurrent creates, duplicate rejection, stable indices after deletion/restart, exact names, invalid payloads, cross-project isolation, protected annotated classes, project deletion, and migration from schema 3.
- 29 browser tests passed against the actual backend with an `id-ID` locale. Class coverage includes CRUD, selection in image preview, clear/reload, project switching, long Unicode names at 900×640, confirmation cancellation, duplicate errors, successful-write/read-failure recovery, and rejected-delete feedback.
- Browser class-manager screenshot inspected for layout and English copy.

`npm run build:installer` passed. It regenerated the frozen backend, portable QA archive, release desktop folder, and production installer with offline WebView2. `artifacts/VisionStudio-Setup.exe` is 230,114,754 bytes; SHA-256: `8f263cd000b7b0f9daa910c423f41b0c20fcf6e162b575e30ad60537953017fb`.

The frozen backend passed 64 checks, including class CRUD, stable indices, selection clearing, and selected-class persistence across executable restarts. Release native WebView2 tests passed normal close, English missing-backend recovery, and parent-crash cleanup. The normal and crash runs execute class creation, selection, rename, deletion without renumbering, reload, and selected-class consumption in the image preview alongside the existing import/gallery workflows. Native class-manager screenshot inspected. No Rust source changed.

The application runs outside the repository with a sanitized environment and no Python on PATH; its backend uses the bundled interpreter. The developer test runner uses Python only to prepare image fixtures. These tests do not represent a clean-machine install.

Local reports under `%LOCALAPPDATA%\VisionStudio\qa`:

- Frozen backend: `Phase 1 502e8f5f006e4cf68b5a14acedbe4fe7/report.json`.
- Release normal: `Desktop 0ab8b8c1-44ea-4bd3-bdf5-33a0583a62a8/report.json`.
- Release missing backend: `Desktop 83710ac0-6acb-4bc2-a7ff-42c98d3b60ec/report.json`.
- Release parent crash: `Desktop 1c8a02f5-adf7-45d6-bfd2-6882b2cddf33/report.json`.
- Installed desktop: `Desktop 45d7fab5-9e2c-4eaf-859a-4d7eb3ada562/report.json`.
- Installer QA: `Installer 6430f893596c4fdd819b010356cb9368/report.json`, also copied to `artifacts/installer-qa-report.json`.

`npm run build:installer:qa` and all 17 `npm run test:installer` checks passed. The installed desktop completed the class-manager and preview workflow, matched the release payload with Tauri's expected NSIS marker difference, and loaded backend resources matching the build manifest. Uninstall removed the application, shortcut, and registry entry while preserving the user-data sentinel. No desktop or backend process remained after testing. The QA installer SHA-256 is `4aa76e3548fd83fbe2be3c0a6bdbf6460874dc167a7b1e95d3ec9cbc1840520d`.

## Remaining acceptance

Clean Windows without development tools, elevated production installation, and first offline WebView2 installation remain pending under the user's earlier decision. Local QA does not close those gates. Phase 11 has not started.
