# Planning comparison and decisions

Compared on 2026-09-14 before implementation. The original planning prose is preserved; this document resolves execution conflicts.

## Document roles

| Document | Purpose | Execution rule |
| --- | --- | --- |
| `Overall-plan.md` | Product vision, architecture, use cases, and five MVP scopes | Product direction and long-term backlog |
| `step.md` | Detailed feature tasks in an earlier 0-30 phase sequence | Reuse task details after mapping to the canonical phases |
| `phase-plan.md` | Revised 0-61 sequence with Windows packaging gates | Canonical phase numbers and delivery order |

All three agree on a project-centered, GUI-driven industrial vision product using React, TypeScript, Tauri, Python/FastAPI, SQLite, and a separate vision/training runtime.

## Conflicts and resolutions

| Topic | Overall plan | Step plan | Phase plan | Decision |
| --- | --- | --- | --- | --- |
| Delivery order | Product features first | Project CRUD immediately after bootstrap | Backend executable, desktop executable, installer before CRUD | Follow the phase plan; Phase 1 is backend packaging, not CRUD |
| Phase 0 | Broad architecture | Repo, health/system API, sidebar | Architecture lock, repo, health API, desktop backend startup | Implement their compatible union: development launcher, APIs, minimal navigation, connection feedback |
| Product shell | Full navigation including Vision Builder and Integrations | Seven base navigation items in Phase 0 | Full base shell in Phase 4 | Phase 0 gets a small scaffold; feature pages are explicitly marked Planned; Phase 4 develops the shell further |
| Repo layout | React under desktop; vision/pipeline/integrations siblings | Separate frontend/backend/desktop | Separate frontend/backend/desktop plus scripts/installer/data | Use phase-plan directories; defer feature modules until needed |
| Runtime storage | Example repo project folders | `data/projects` | `%LOCALAPPDATA%\VisionStudio` | Use writable per-user app storage from the start; repo data is only scratch/fixtures |
| Dataset split | Example 70/20/10 | Deterministic 80/20 | 80/20 | Initial train/validation split is deterministic 80/20; a test split can be added later |
| Training progress | WebSockets | Polling first | Polling first | Begin with polling; add WebSockets when justified |
| Camera preview | Binary JPEG/WebSocket or MJPEG | USB preview first | MJPEG or binary JPEG | MJPEG first, USB before RTSP |
| Pipeline builder | Central product feature | After counter/runtime works | Internal pipeline Phases 40-41, visual editor 42-43 | Build working runtime behavior before the graph editor |
| Auto annotation | Temporary training after a small manual set | Suggestions from an existing model, human review | Phase 47, existing model, human review | Existing-model suggestions first; never silently promote them to ground truth |
| Model naming | Generic YOLO Nano | Example `yolo11n.pt` | One bundled YOLO Nano, offline first training | Defer exact weights/runtime selection to Phases 15-16; do not add downloads to bootstrap |
| Runtime modes | Studio, Test, Production | Studio and Runtime | Studio/Runtime, then fullscreen | Two modes first; detailed debug/locking behavior stays in product backlog |
| Language | English UI examples, Indonesian planning prose | Same | Same | User requirement overrides ambiguity: application-owned text is always English |

## Feature phase mapping

| Earlier step phase | Canonical phase(s) |
| --- | --- |
| 0 Bootstrap | 0 foundation; expanded shell at 4 |
| 1 Projects | 5 database, 6 project management |
| 2 Dataset | 7-9 storage/import/gallery |
| 3 Classes | 10 |
| 4 Annotation | 11-12 |
| 5 Export/validation | 13-14 |
| 6 Training backend/worker | 15-18, including packaging/model prerequisites |
| 7 Training UI/progress | 19-20 |
| 8 Model registry | 21 |
| 9 USB camera | 22-23 |
| 10 Inference/overlay | 24-25, then mandatory standalone checkpoint 26 |
| 11 Tracking | 27 |
| 12 Line drawing | 28 |
| 13 Line crossing/counter | 29-30 |
| 14 ROI | 31 |
| 15 Events/snapshot | 32-33 |
| 16 RTSP | 34-35 |
| 17 MQTT | 36-37 |
| 18 Runtime profiles | 38-39 |
| 19 Pipeline engine | 40-41 |
| 20 Visual builder | 42-43 |
| 21 REST actions | 44 |
| 22 Database actions | No dedicated phase; retain as an explicit integration backlog item |
| 23 Modbus | 45 |
| 24 OPC UA | 46 |
| 25 Auto annotation | 47 |
| 26 Dataset versions | 48; model versions additionally at 49 |
| 27 Active learning | 50 |
| 28 OCR | 51 |
| 29 Classification | 52 |
| 30 Segmentation | 53 |

Phases 1-3, 26, and 54-61 add deployment and reliability work absent from the earlier step sequence. Packaging checkpoints also recur at 15, 30, and 42. The first end-to-end detection milestone is Phase 25, gated by Phase 26 clean-machine packaging; the first counting demo is Phase 30.

## Product backlog not fully scheduled

The phase plan does not explicitly schedule every overall-plan capability. Preserve video frame extraction, camera dataset capture, augmentation, experiment comparison, model export formats, model benchmarking, multiple cameras, templates, zone rules, pre-event recording/ring buffers, measurement calibration, PLC-triggered capture/digital input, external database output, host/license integration, and the future AI assistant as backlog. Do not interpret their omission as implementation or removal. Scope them separately after relevant milestones.

## Phase 0 boundary

- P00-S01: repository structure, Git initialization, frontend/backend dependency manifests and locks, scripts, README, environment examples, English policy.
- P00-S02: `/health`, `/system/info`, CPU/OS/Python/app information, writable storage initialization, explicit loopback CORS.
- P00-S03: Tauri development process ownership, dynamic local backend port, frontend IPC discovery, normal-exit cleanup.
- P00-S04: basic seven-item navigation, actual backend status, Settings/system details, English loading/error/empty states.
- P00-S05: backend tests, browser integration tests, frontend build, native build/start/close checks, recorded results.

Excluded: database/CRUD, dataset features, AI dependencies, model downloads, production sidecar bundling, installer, updater, and crash watchdog. The development Python interpreter is an intentional Phase 0 prerequisite; zero-development-dependency deployment is proven by subsequent packaging gates.

## Architecture references

The bootstrap uses Tauri's documented [build configuration](https://v2.tauri.app/reference/config/) and [Rust command IPC](https://v2.tauri.app/develop/calling-rust/). Windows build prerequisites follow the [official Tauri guide](https://v2.tauri.app/start/prerequisites/). CORS uses explicit frontend origins as described by [FastAPI](https://fastapi.tiangolo.com/tutorial/cors/).
