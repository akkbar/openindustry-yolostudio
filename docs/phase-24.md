# Phase 24: Live YOLO inference

Implemented on 2026-09-16. A camera session now uses the selected project's active production checkpoint for CPU inference.

## Delivered

- Session startup resolves the active project model before opening the camera. Missing or archived checkpoints return an English API error.
- The worker loads the local checkpoint once, runs YOLO on each frame with `device="cpu"`, and returns class ID, class name, confidence, and normalized bounding box coordinates.
- Frame metadata travels with each JPEG in response headers and is exposed to the Tauri frontend through CORS.

## Scope boundary

The implementation supports any completed object-detection checkpoint selected as production. Hardware-camera and model-quality acceptance requires a physical camera and suitable trained data.

## Verification

- Backend coverage injects a production model and verifies its normalized Banana detection metadata in a live frame response.
- Browser coverage renders the returned live detection in the Cameras page.
