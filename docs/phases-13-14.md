# Phases 13 and 14: YOLO export and dataset validation

Implemented on 2026-09-15 following `phase-plan.md` and `step.md` Steps 5.1–5.3. Phase 15 has not started. No dependencies or database migrations were added.

## Behavior

The Dataset page includes **Validate dataset** and **Export YOLO dataset**. Reports show image, annotation, and class counts, plus issues with the affected image name. Reports are snapshots of the last check; export always validates the current dataset again. All application copy is English, frontend copy is in `frontend/src/locales/en.ts`, and displayed counts use `en-US`.

Validation blocks missing/unreadable images, mismatched image dimensions, nonfinite or nonpositive boxes, boxes outside image bounds, missing/foreign classes, images without annotations, and duplicate oriented RGB pixels. At least two annotated images and one class are required. Empty images are not silently treated as reviewed negatives. Reports return the full issue count and the first 200 details.

Each export writes a new immutable snapshot under `%LOCALAPPDATA%\VisionStudio\projects\<project-id>\dataset-export\<export-id>`. The snapshot contains:

```text
images/train/*.png
images/val/*.png
labels/train/*.txt
labels/val/*.txt
data.yaml
manifest.json
```

Images are losslessly encoded as RGB PNG after EXIF orientation, matching the image coordinate system in the annotation editor. Original imported files are preserved. Generated image IDs prevent filename collisions. Labels contain zero-based class indices followed by normalized center-x, center-y, width, and height. Class indices are remapped consecutively in project-index order; the manifest records the original IDs/indices and exported indices. User class names are safely serialized as JSON-compatible YAML values.

Image IDs are sorted, then shuffled with a local seed of 42. Validation receives approximately 20% (rounded, at least one); training receives the rest. Both sets are nonempty and disjoint. Re-exporting an unchanged dataset preserves split membership. The database's image split fields are not changed. Adding/removing images may change split membership.

`data.yaml` includes the absolute snapshot path and relative train/validation directories. If moving a snapshot, update its `path` value. The UI shows selectable export-folder and training-configuration paths. Prior snapshots survive edits and re-exports; deleting the project removes its snapshots. Snapshot storage use grows with each successful export.

## Consistency and recovery

`POST /projects/{project-id}/datasets/validate` returns the report. `POST /projects/{project-id}/datasets/export` returns `exported: false` plus the report for invalid data, or snapshot paths, counts, seed, and the report on success. Storage failures use the existing English API error shape.

Validation/export run in the backend thread pool under the same SQLite write lock used by mutations, preventing application imports, annotation edits, and deletion from changing a snapshot mid-copy. Work processes one decoded image at a time. Large datasets can delay concurrent writes; training/background-job infrastructure remains deferred. A completed staging folder is atomically renamed into its final generated snapshot name. Failed writes remove partial staging files. Startup retries cleanup of generated unpublished folders left by termination, while preserving completed snapshots and unrelated folders.

## Compatibility and verification

The file layout and normalized label format follow the [official Ultralytics detection dataset specification](https://docs.ultralytics.com/datasets/detect/). Format checks read emitted labels, class mappings, split manifests, image dimensions, and configuration paths. Actual Ultralytics loading/training remains deferred to Phase 15, when the heavy runtime is introduced.

- Production frontend build passed.
- 114 backend tests passed. New coverage includes label values, safe class names, stable class-index gaps, deterministic/disjoint splits, preserved snapshots, EXIF orientation, empty/single-image projects, corrupt/missing/duplicate images, invalid boxes/classes/paths, disk-write failure cleanup, and interrupted-export cleanup. Existing migration tests also passed after making cleanup tolerant of invalid legacy storage IDs.
- 35 browser E2E tests passed with an Indonesian browser locale. New tests cover blocked exports, successful file creation, counts, validation after edits, retained earlier snapshots, request failure recovery, and disabled duplicate clicks. The 900-pixel-wide export panel screenshot was visually inspected.
- 77 frozen-backend checks passed, including validation, invalid-export rejection, successful YOLO export, manifest/configuration files, and paired images/labels. Report: `%LOCALAPPDATA%\VisionStudio\qa\Phase 1 f76278d1a1f24472aee6c46b5b49798c\report.json`.
- Release WebView2 QA passed project/import/gallery/class workflows, actual desktop close/relaunch annotation persistence, and validation/export through the desktop UI. It verified configuration and manifest files, image/label pairs, exact normalized values, and snapshot removal with project deletion. The desktop screenshot was visually inspected. Report: `%LOCALAPPDATA%\VisionStudio\qa\Desktop 754c0612-d087-4972-852d-6852b29a9c3e\report.json`.
- The final production installer build passed. `artifacts/VisionStudio-Setup.exe` is 230,128,173 bytes; SHA-256: `0da2bb52caba4342e90d5c51b3a505b8db6681ea5ca41312e528c86e52691c16`.
- The QA installer build and all 17 install/launch/uninstall checks passed, including release payload/resource matching and user-data preservation. The installed application passed the same annotation restart and dataset export workflow. Installed desktop report: `%LOCALAPPDATA%\VisionStudio\qa\Desktop 91e21fad-f94b-4150-87b5-bc843272dc00\report.json`. Installer report: `artifacts/installer-qa-report.json` (QA directory `Installer 2c1b9e8b6e4542dcb6ad0280deda2686`). QA installer SHA-256: `2c52eb4cc15e0a032b5975a1106d7107b202919925e1a00e99a566e412194165`.
- `git diff --check` passed. No QA desktop or bundled backend process remained after the final checks.

The bundled checks run relocated executables with a sanitized environment and no Python on PATH. The native QA runner uses developer Python only to generate fixtures. No Rust source changed; the release build compiled successfully. These results do not replace clean-machine or actual Ultralytics runtime acceptance.

## Remaining acceptance

The previously accepted clean-Windows/no-development-tools check, elevated production installation, and first offline WebView2 installation remain pending. Local QA does not claim those checks passed.
