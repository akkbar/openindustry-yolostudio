# Phases 32–34: events, snapshots, and RTSP cameras

Phase 32 persists a `line_cross` event for each accepted counting-line crossing. Every event records its UTC timestamp, detected class, tracker ID, line total, and detection confidence in the project database.

Phase 33 stores the encoded live frame as `events/{event-id}.jpg` under `%LOCALAPPDATA%\VisionStudio\projects\{project-id}`. The API lists recent events and serves only the event's own JPEG snapshot; the Cameras page refreshes the recent-event list while a preview is active.

Phase 34 adds project-scoped RTSP camera records with URL, optional username, and optional password. API responses never return a password. USB camera preview routes remain available. RTSP preview reconnects with a bounded increasing delay after an open or read failure, and its session exposes a reconnect count.

Validation: `npm run build`, `npm run test:backend`, and `npm run test:e2e` cover the frontend, event snapshot persistence, RTSP credential redaction, RTSP reconnect behavior, and the camera UI flow.
