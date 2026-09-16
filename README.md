# OpenIndustry Vision Studio (Industrial YOLO Studio)

> **Empowering factory automation and edge inspection with computer vision — without writing a single line of Python.**

OpenIndustry Vision Studio is a modern, self-contained Windows desktop application designed to streamline the complete lifecycle of industrial vision systems: from collecting images and annotating datasets, to training custom YOLO models, streaming from factory cameras, tracking objects, and dispatching events directly to industrial automation protocols (MQTT, Modbus, OPC UA).

---

## 🎯 Purpose & Vision

Deploying computer vision on the factory floor is often complicated by brittle Python virtual environments, CUDA driver mismatches, fragmented CLI tools, and the absence of native bridges to industrial hardware (PLCs, SCADA, PACs).

**Vision Studio solves this by providing:**
1. **Zero Setup for Operators**: Packaged as a standard Windows x64 executable and installer. Users never need to install Python, Node.js, Git, or developer tooling.
2. **All-in-One Studio**: Everything happens inside one unified desktop interface — dataset collection, annotation, model training, live inference, and analytics.
3. **Industrial Edge Ready**: Built specifically for industrial environments, supporting factory cameras (USB webcams & RTSP industrial cameras), region-of-interest (ROI) filtering, line-crossing counting, snapshot logging, and upcoming fieldbus connectivity.

---

## 🚀 The End-State Product

When completed, Vision Studio will serve as a turnkey edge vision platform featuring:

```text
┌────────────────┐      ┌─────────────────┐      ┌────────────────────┐
│ Factory Cameras│ ───► │  Vision Studio  │ ───► │   Industrial OT    │
│ (USB / RTSP)   │      │  Desktop Engine │      │ (PLC/SCADA/Cloud)  │
└────────────────┘      └─────────────────┘      └────────────────────┘
                               │
       ┌───────────────────────┼────────────────────────┐
       ▼                       ▼                        ▼
┌──────────────┐       ┌───────────────┐       ┌─────────────────┐
│ Dataset &    │       │ 1-Click YOLO  │       │ Real-Time       │
│ Annotations  │       │ Training      │       │ Tracking & ROI  │
└──────────────┘       └───────────────┘       └─────────────────┘
```

- **Intuitive Dataset & Annotation Studio**: Built-in bounding box annotator with keyboard shortcuts, auto-validation, duplicate detection, and standard YOLO dataset export.
- **Background Training Engine**: Train YOLO models directly on your local machine using an isolated worker process that keeps the user interface smooth and responsive.
- **Model Registry & Pretrained Catalog**: Seamlessly switch between built-in COCO presets and custom-trained models for production deployment.
- **Real-Time Vision Analytics**:
  - Live preview with high-performance detection overlays.
  - Multi-object tracking (ByteTrack) maintaining stable identity IDs across frames.
  - Interactive counting lines with bidirectional crossing detection.
  - Polygon Region of Interest (ROI) filtering to ignore background noise.
  - Event logging with automatic JPEG snapshot captures.
- **Visual Pipeline Builder (React Flow)**: Drag-and-drop visual node graph connecting video sources, AI models, tracking logic, counters, and output actions.
- **Industrial Connectivity (OT Integration)**:
  - **MQTT**: Publish real-time detection events and telemetry (FPS, camera health).
  - **Modbus TCP**: Directly toggle PLC coils or write counts to holding registers.
  - **OPC UA Server**: Expose vision counters, statuses, and alarms for SCADA/MES ingestion.
  - **REST Webhooks**: HTTP POST triggers for third-party systems.
- **Dual Operating Modes**:
  - **Studio Mode**: For engineers configuring cameras, labeling data, and training models.
  - **Production Mode**: A 24/7 fullscreen, locked-down kiosk view showing live camera feeds, throughput counts, and health alerts on shop-floor monitors.

---

## 📊 Current Progress & Roadmap

Vision Studio is engineered through an incremental, verification-driven plan consisting of **61 structured phases** (documented in [`phase-plan.md`](phase-plan.md)).

### 🟢 Completed Features (Phases 0 — 34)

| Milestone Area | Status | Key Highlights |
| :--- | :---: | :--- |
| **Desktop Shell & Packaging** | ✅ Completed | Standalone Tauri 2 desktop shell, bundled FastAPI backend, offline NSIS installer with WebView2. Clean desktop startup and shutdown without terminal windows. |
| **Local Persistence** | ✅ Completed | Robust local SQLite database with versioned schema migrations, foreign keys, and WAL mode stored in `%LOCALAPPDATA%\VisionStudio\`. |
| **Project Management** | ✅ Completed | Isolated workspace and project management with dedicated folders for datasets, models, runs, and events. |
| **Dataset & Annotations** | ✅ Completed | Fast image import (JPG, PNG, WEBP), thumbnail generation, stable class management, bounding box annotator (pan, zoom, resize), and YOLO dataset validation & export. |
| **YOLO Runtime & Training** | ✅ Completed | Bundled CPU YOLO runtime (Ultralytics + PyTorch), verified YOLO11 Nano base checkpoint, separate-process training worker, real-time metrics polling, and production model registry. |
| **Camera & Live Preview** | ✅ Completed | Automatic USB webcam discovery, RTSP IP camera support with automatic reconnection, and low-latency JPEG streaming preview. |
| **Live Inference & Overlays** | ✅ Completed | Real-time detection with configurable confidence thresholds and responsive bounding box overlays. |
| **Tracking & Counting** | ✅ Completed | ByteTrack multi-object tracking, interactive counting lines, directional crossing logic (A→B, B→A, both), duplicate prevention, and polygon ROI filtering. |
| **Events & Snapshots** | ✅ Completed | Persistent line-crossing event log with captured JPEG snapshots displayed directly in the UI. |

---

### 🟡 What's Coming Next

The remaining phases focus on factory floor integration, visual programming, and enterprise readiness:

- **Phases 35–37**: Camera health monitoring (FPS, dropped frames) & MQTT event/telemetry publishing.
- **Phases 38–39**: Dedicated Runtime Mode and Fullscreen 24/7 Production Kiosk display.
- **Phases 40–43**: Visual Node Pipeline Builder (drag-and-drop node graph canvas with node inspector).
- **Phases 44–46**: Industrial fieldbus communications (REST Webhooks, Modbus TCP, built-in OPC UA Server).
- **Phases 47–53**: AI workflow enhancements (Auto-annotation with existing models, dataset/model versioning, active learning review queue, classification, segmentation).
- **Phases 54–61**: GPU auto-detection & bundled runtime, crash recovery, logging suite, final QA matrix, and production release installer.

---

## 💻 Quick Start

### Running the Packaged App (Users)

1. Run the installer: `artifacts/OpenIndustry-Vision-Studio-Setup.exe` (Administrator required). (downloadable latest setup: https://drive.google.com/file/d/1bIIfuk8rC36EZ_QBfDo4VrIW0eeQvCAP/view?usp=drive_link)
2. Alternatively, run the portable build from `artifacts/desktop/OpenIndustry Vision Studio.exe`.
3. The application will launch, automatically manage its background service, and connect without requiring any Python or runtime installation.

### Running in Development (Contributors)

**Prerequisites**: Node.js 22+, Python 3.10 (packaging baseline), Rust 1.98.1+ with MSVC target, Visual Studio C++ Build Tools, and Microsoft Edge WebView2.

```powershell
# 1. Install dependencies and prepare environments
npm ci
npm run setup:backend
npm run build:backend

# 2. Launch the desktop app in development mode
npm run dev
```

*For browser-only testing without the Tauri shell, run `npm run dev:backend` and `npm run dev:frontend` in separate terminals and open `http://127.0.0.1:1420`.*

### Testing & Verification

```powershell
# Run full suite of frontend and backend checks
npm run build
npm run test:backend
npm run test:backend-bundle
npm run test:e2e
```

---

## 📚 Documentation Index

- **[`phase-plan.md`](phase-plan.md)** — The master execution plan defining architectural decisions and phase order.
- **[`step.md`](step.md)** — Detailed task breakdowns and prompt-level steps.
- **[`Overall-plan.md`](Overall-plan.md)** — Long-term product vision and feature roadmap.
- **[`CONCEPT.md`](CONCEPT.md)** — Detailed technical specification, packaging architecture, and historical notes.
- **[`docs/`](docs/)** — Implementation evidence, test logs, and phase verification reports.

---

## 📄 License

Open-source under the project's designated license. Built with Tauri, React, FastAPI, and Ultralytics YOLO.
