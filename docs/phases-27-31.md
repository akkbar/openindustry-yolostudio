# Phases 27–31: tracking, counting lines, counters, and ROI

These phases turn a live detection preview into the first local counting workflow:

```text
Detection ? ROI filter ? ByteTrack-style tracker ? line crossing ? counter
```

## Phase 27: tracking

Each live detection can include a session-local `track_id`. The tracker uses high- and low-confidence association passes with class-aware IoU matching and bounded missed-frame retention. This compact local ByteTrack-style implementation does not add a Python dependency or write tracker state to disk. A track ID remains stable for a matching object during one preview session.

## Phase 28: counting lines

A project can store any number of named, normalized counting lines. Each line has normalized start and end points, an enabled flag, and a permitted direction: A to B, B to A, or both. The Camera page lets the operator click two points on the live frame to create a line. Coordinates are persisted in SQLite migration 10, so they remain valid as the displayed frame size changes.

## Phase 29 and 30: line crossing and counters

The session compares a tracked object's prior and current centroids. A crossing is counted only when the path intersects the configured line segment and its direction is permitted. The counter records the pair `(track_id, line_id)` after its first crossing, preventing duplicate counts caused by repeated frames or a stationary object on the line. Counters show total, A-to-B, and B-to-A values in the live preview. They reset when tracking configuration is reloaded or the preview session stops; durable event logs begin in Phase 32.

## Phase 31: ROI

One enabled polygon ROI can be stored per project. The camera editor collects at least three normalized points. Detections whose centroids fall outside the polygon are discarded before tracking, so they cannot receive a new track or affect a line counter. Updating a line or ROI reloads the live session's local tracker and counter to make the change deterministic.

## API and storage

- `GET /projects/{project_id}/counting`
- `POST`, `PATCH`, `DELETE /projects/{project_id}/counting/lines`
- `PUT`, `DELETE /projects/{project_id}/counting/roi`
- `POST /projects/{project_id}/cameras/usb/sessions/{session_id}/counting/reload`

Migration 10 adds `counting_lines` and `project_rois`. They hold only normalized configuration in the local workspace database. No runtime files are written to the installation directory or source tree.

## Verification

Backend coverage checks stable track IDs, one crossing per track/line pair, ROI filtering before tracking, normalized configuration persistence, camera-frame tracking metadata, and the existing camera session lifecycle. Browser coverage draws a line and an ROI against a live-preview test frame and verifies both are persisted.
