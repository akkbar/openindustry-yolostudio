# Phase 23: Camera preview

Implemented on 2026-09-16. The Cameras page can now start and stop a local USB camera preview for a selected project.

## Delivered

- Starting a session opens one local USB capture in a dedicated worker thread. It provides successive binary JPEG frames without a browser plug-in or external server.
- The frame endpoint waits for a newer frame, returns `image/jpeg`, and disables caching. The browser replaces its local object URL as frames arrive.
- Stopping a session, leaving the Cameras page, and backend shutdown all signal the worker, release the capture handle, and join the thread. A stopped or failed session cannot be read again.

## Scope boundary

Preview is local and USB-index based. RTSP, recording, and multi-camera orchestration are not part of this phase.

## Verification

- Backend tests verify JPEG delivery and capture release when the session is stopped.
- Browser coverage starts and stops a binary-JPEG preview through the Cameras page.
