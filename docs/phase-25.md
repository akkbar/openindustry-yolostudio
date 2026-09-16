# Phase 25: Detection overlay

Implemented on 2026-09-16. The Cameras page now makes live inference understandable to an operator.

## Delivered

- The preview frame has an SVG overlay with normalized detection boxes, class labels, and confidence percentages.
- A 0.00–1.00 confidence slider filters both the overlay and the live detection list locally, without restarting the camera or model.
- The page clearly distinguishes preview-only mode from active production-model inference.

## Verification

- Browser coverage starts a mocked JPEG session, displays a Banana overlay, applies a 0.85 confidence threshold, and confirms session stop.
- Backend coverage verifies JPEG delivery, normalized inference metadata, and capture release.
