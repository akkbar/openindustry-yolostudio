# Phase 21: Model registry

Implemented on 2026-09-16. Each successful training worker result now becomes a durable, project-scoped model record.

## Delivered

- Database migration 7 adds an active-model reference to projects plus dataset-export and settings metadata to registered models.
- On success, the worker copies `runs/{job-id}/weights/best.pt` into `projects/{project-id}/models/` before creating a development model record. The record keeps the immutable dataset export identifier, training settings, final metrics, training job ID, creation time, and project-relative model path.
- A project lists its registered models and can rename a model, archive it, or promote it. Promotion makes one non-archived model the project's active production model.
- Registry writes are idempotent per training job. A registry failure is logged after job completion and does not rewrite a completed job as failed.

## Scope boundary

The active model is a selection for later preview and inference work. This phase does not load it into a camera pipeline.

## Verification

- Backend tests cover checkpoint registration, metadata retention, active-model promotion, archive behavior, and invalid project or model cases.
- The browser suite promotes a completed model from the Models page.
- The Phase 20–22 source verification passed: 136 backend tests, 40 browser tests, and 97 relocated bundled-backend checks.
