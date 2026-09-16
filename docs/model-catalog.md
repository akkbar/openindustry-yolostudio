# Model catalog

The Models page includes a metadata-driven library of 27 pretrained model presets. It gives a project a practical inference starting point without replacing the existing image import, annotation, dataset export, training, custom-model registry, or camera workflows.

## Catalog contents

Thirteen built-in presets use the one verified `yolo11n` COCO checkpoint already provisioned by Vision Studio. They do not copy or download another checkpoint. General Object Detection exposes all 80 COCO classes; the person, vehicle, fruit, bottle, people counter, vehicle counter, animal, food, safety-zone person, warehouse, conveyor, and defect presets apply a class filter and recommended confidence setting to that same checkpoint.

Fourteen specialized entries are discoverable in the library: Human Pose, Face Detection, Hand Detection, PPE Detection, Helmet Detection, Fire and Smoke Detection, Person + Forklift Safety, Forklift Detection, Pallet Detection, Carton / Box Detection, Package Detection, License Plate Detection, Can Detection, and Instance Segmentation. They are catalog metadata only until a model source, licence, checksum, and redistribution decision have been reviewed.

Specialized entries deliberately show **Available to install** but cannot be installed in this release. The API returns `model_download_unavailable`; there are no placeholder URLs, unverified downloads, or bundled third-party weights.

## Project selection and inference

Choose **Use in project** for an existing project, or **Create project** from a runnable built-in preset. The selection is stored in the workspace database with its confidence, IoU threshold, class filter, and model version. Selecting a catalog model clears an active custom production model. Activating a custom trained model clears the catalog selection, so a project has one unambiguous inference choice.

When a camera session starts, Vision Studio resolves the selected catalog preset first. A built-in selection uses the shared base checkpoint and filters its detections by the preset class list. The camera session reports whether inference is using a catalog preset or a custom production model. The existing custom-model camera path remains unchanged.

## Storage and API

Migration 9 adds `projects.catalog_model_id`, `projects.catalog_model_settings`, and the `catalog_model_installations` table. Downloaded artifacts are reserved for `%LOCALAPPDATA%\\VisionStudio\\models\\downloaded`; the current release does not create them. No catalog weights are written to the installation directory or source tree.

The local API exposes:

- `GET /model-catalog` with optional `category` and `query`
- `GET /model-catalog/models/{model_id}`
- `PUT`, `GET`, and `DELETE /model-catalog/projects/{project_id}/selection`
- `POST /model-catalog/models/{model_id}/projects`
- `POST /model-catalog/models/{model_id}/install` for the future verified-install flow

Each entry records model ID, task, classes, source type, version, source URL, author, model licence, dataset licence, redistribution status, recommended inference settings, and optional download/checksum fields. Unknown information is explicitly stored as `unknown`.
