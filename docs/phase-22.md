# Phase 22: USB camera detection

Implemented on 2026-09-16. The application can now find locally openable USB camera indexes.

## Delivered

- `GET /cameras/usb?limit=4` probes a bounded index range with OpenCV and returns stable identities such as `usb-0` and English names such as `Camera 0`.
- Every probe releases its capture handle, whether the index opens or fails, so scanning does not reserve a camera for later work.
- The Cameras page scans on entry and offers **Scan USB cameras** to refresh the list. It explains when no local camera opens and reports API failures in English.

## Scope boundary

Detection only confirms that a local index can be opened at scan time. Live video, model selection for a stream, and inference begin in later phases.

## Verification

- Backend tests cover bounded probing, camera response shape, and release behavior for successful and failed probes.
- A browser test checks the list and explicit rescan behavior using the Cameras page.
- The Phase 20–22 source verification passed: `npm run build`, 136 backend tests, and all 40 browser tests. The rebuilt Phase 22 bundle passed 97 checks; its report is under `%LOCALAPPDATA%\VisionStudio\qa\Phase 22 1de91b3a11cd4a08a520f8281bf83db6\report.json`.
