> Planning authority: `phase-plan.md` defines execution order; `step.md` provides detailed tasks; `Overall-plan.md` defines product vision. See [comparison and decisions](docs/plan-comparison.md) and [Phase 0 status](docs/phase-0.md). All application-owned text must always be English.

Bisa. Karena sekarang requirement deployment sudah jelas, plan-nya perlu direvisi supaya dari awal memang mengarah ke **Windows executable yang self-contained**.

Saya akan jadikan target utamanya:

> **User install Vision Studio di Windows, tanpa perlu install Python, Node.js, npm, pip, CUDA toolkit, atau dependency development lain.**

Urutan eksekusinya saya sarankan seperti ini.

## Phase 0 — Lock architecture dan packaging strategy

Goal: semua keputusan teknis dari awal compatible dengan Windows standalone.

Pilih arsitektur:

```text
Frontend
React + TypeScript

Desktop Shell
Tauri

Backend
FastAPI + Python

Vision
Ultralytics + OpenCV + PyTorch/ONNX

Packaging
Tauri bundler
+
PyInstaller atau Nuitka untuk Python backend
```

Struktur repo:

```text
vision-studio/
├── desktop/
├── frontend/
├── backend/
├── scripts/
├── installer/
└── data/
```

Acceptance:

* repo terbentuk
* frontend jalan
* backend jalan
* Tauri membuka frontend

**Codex task 0.1:** bootstrap repo saja.

**Codex task 0.2:** tambahkan FastAPI `/health`.

**Codex task 0.3:** Tauri start backend process saat app dibuka.

---

## Phase 1 — Backend executable proof-of-concept

> Status (2026-09-15): executable and portable QA package implemented; local tests passed. Fresh-Windows/no-Python acceptance remains pending at the user's request because a clean PC/VM is not available. The user subsequently authorized continuation through Phase 4 with this gate still pending. See [Phase 1 evidence](docs/phase-1.md) and [Phases 2–4 evidence](docs/phases-2-4.md).

Ini saya pindahkan sangat awal.

Goal: memastikan Python backend bisa dibundle sebelum project menjadi besar.

Backend minimal:

```text
GET /health
GET /system/info
```

Lalu build:

```text
backend.exe
```

dengan PyInstaller/Nuitka.

Acceptance:

```text
Fresh Windows
No Python installed

backend.exe
↓
starts
↓
localhost API responds
```

Kalau ini gagal, jangan lanjut fitur lain dulu.

---

## Phase 2 — Desktop executable proof-of-concept

> Status (2026-09-15): implemented and locally verified in packaged debug/release builds. Relocated startup, bundled child process, English missing-backend recovery, normal close, and parent-crash cleanup passed native tests. See [Phases 2–4 evidence](docs/phases-2-4.md).

Goal:

```text
VisionStudio.exe
```

bisa:

1. start
2. launch bundled `backend.exe`
3. wait backend ready
4. render React UI
5. shutdown backend ketika app ditutup

Flow:

```text
VisionStudio.exe
      ↓
start backend.exe
      ↓
GET /health
      ↓
React UI
```

Acceptance:

```text
double-click VisionStudio.exe
↓
UI muncul
↓
Backend Connected
```

Tanpa terminal.

---

## Phase 3 — Installer proof-of-concept

> Status (2026-09-15): production NSIS installer built with offline WebView2 and English-only copy; 17 current-user QA install/launch/uninstall checks passed. See [Phases 2–4 evidence](docs/phases-2-4.md). Elevated per-machine and clean-Windows acceptance remain pending.

Sebelum fitur AI.

Buat:

```text
VisionStudio-Setup.exe
```

Install ke:

```text
C:\Program Files\VisionStudio\
```

Data writable ke:

```text
%LOCALAPPDATA%\VisionStudio\
```

Acceptance:

* install
* uninstall
* desktop shortcut
* app jalan
* no dependency external

Ini penting supaya nanti kita tidak menemukan masalah packaging setelah project sudah besar.

---

# Phase 4 — Base application shell

> Status (2026-09-15): implemented; seven-page navigation, connection status, app version, system information, and Settings are available in English. Browser and native shell tests passed. Later feature pages remain explicitly planned; Phase 5 has not started.

Baru mulai UI produk.

Navigation:

```text
Dashboard
Projects
Dataset
Models
Cameras
Runtime
Settings
```

Tambahkan:

* backend connection indicator
* app version
* system info

Acceptance:

* desktop shell stabil
* no feature AI dulu

---

# Phase 5 — Local database

Gunakan SQLite dulu.

Simpan di:

```text
%LOCALAPPDATA%\VisionStudio\data\
```

Database:

```text
visionstudio.db
```

Tables awal:

```text
projects
datasets
images
classes
annotations
models
training_jobs
cameras
events
```

Acceptance:

* database otomatis dibuat pertama kali app dijalankan
* tidak butuh PostgreSQL

---

# Phase 6 — Project Management

Buat project CRUD.

Schema:

```text
Project
id
name
description
task_type
created_at
updated_at
```

UI:

```text
Projects

+ New Project

Banana Counter
Carton Counter
```

Acceptance:

* create
* rename
* open
* delete

---

# Phase 7 — Dataset Storage

Setiap project punya folder:

```text
%LOCALAPPDATA%\VisionStudio\
└── projects\
    └── {project-id}\
        ├── dataset\
        ├── models\
        ├── runs\
        └── events\
```

Jangan hardcode development path.

Acceptance:

* project folder otomatis dibuat

---

# Phase 8 — Image Import

Support:

```text
JPG
JPEG
PNG
WEBP
```

Actions:

* select images
* drag/drop multiple images

Acceptance:

* 100+ images import
* thumbnails dibuat
* files copied ke project storage

---

# Phase 9 — Dataset Gallery

Grid:

```text
[img][img][img]
[img][img][img]
```

Display:

* filename
* annotated/not annotated
* dimensions

Acceptance:

* smooth scroll
* open image

---

# Phase 10 — Class Manager

CRUD classes.

Contoh:

```text
0 banana
1 pallet
```

Acceptance:

* add
* rename
* delete
* selected class available to annotator

---

# Phase 11 — Annotation Canvas

Pecah kecil.

### 11.1 Image viewer

Support:

* zoom
* pan
* fit
* reset

### 11.2 Draw bounding box

Normalized coordinates.

### 11.3 Save annotation

### 11.4 Select existing box

### 11.5 Move box

### 11.6 Resize box

### 11.7 Delete box

Acceptance:

```text
annotate
↓
close app
↓
open app
↓
annotation still correct
```

---

# Phase 12 — Annotation productivity

Tambahkan:

```text
Next
Previous

D next
A previous
Delete
1..9 choose class
```

Tambahkan status:

```text
Annotated 72 / 300
```

---

# Phase 13 — YOLO Dataset Export

Generate internal training dataset:

```text
dataset-export/
├── images/
│   ├── train/
│   └── val/
├── labels/
│   ├── train/
│   └── val/
└── data.yaml
```

Default split:

```text
80% train
20% validation
```

Acceptance:

* dataset valid untuk Ultralytics

---

# Phase 14 — Dataset Validation

Sebelum train:

check:

* invalid box
* box outside image
* missing class
* missing image
* zero annotation
* duplicate image

Result:

```text
Dataset Validation

Images       300
Annotations  972
Classes      1

✓ Valid
```

---

# Phase 15 — Bundle YOLO runtime

Sebelum training UI, test packaging lagi.

Backend sekarang import:

```python
ultralytics
torch
opencv
```

Build `backend.exe`.

Acceptance:

```text
Fresh Windows
No Python
↓
backend.exe
↓
imports YOLO successfully
```

Ini kemungkinan mulai membuat executable besar. Itu normal.

---

# Phase 16 — Model download/bundling strategy

Jangan paksa aplikasi download base model diam-diam.

Untuk MVP, bundle satu base model:

```text
YOLO nano
```

misalnya:

```text
models/base/yolo-nano.pt
```

Nanti model lain optional download.

Acceptance:

* training pertama bisa dilakukan offline

Ini penting untuk zero-dependency deployment.

---

# Phase 17 — Training Job Backend

Table:

```text
training_jobs
```

Fields:

```text
id
project_id
status
model
epochs
imgsz
progress
metrics
started_at
finished_at
error
```

Status:

```text
queued
running
completed
failed
cancelled
```

---

# Phase 18 — Training Worker

Training jangan dilakukan dalam FastAPI main process.

Flow:

```text
FastAPI
  ↓
Training Job
  ↓
Training Worker Process
  ↓
Ultralytics
```

Untuk MVP:

* Python subprocess/multiprocessing

Belum perlu Celery/Redis.

Acceptance:

* UI/backend tetap responsive saat training

---

# Phase 19 — Training UI

Form:

```text
Base Model
YOLO Nano

Epochs
50

Image Size
640

Device
Auto

[ Start Training ]
```

Acceptance:

* start dari GUI
* no CLI

---

# Phase 20 — Training Progress

Display:

```text
Epoch 24 / 50

Loss
Precision
Recall
mAP50
```

Polling dulu.

Tidak perlu WebSocket sebelum memang perlu.

---

# Phase 21 — Model Registry

Saat training selesai:

```text
banana-v1
```

Store:

* model file
* dataset version
* training settings
* metrics

Status:

```text
development
production
archived
```

Acceptance:

* select active model

---

# Phase 22 — USB Camera Detection

Backend scan USB camera.

Awal cukup:

```text
Camera 0
Camera 1
Camera 2
```

Acceptance:

* camera list muncul
* test open/close

---

# Phase 23 — Camera Preview

UI live camera.

Untuk MVP:

```text
MJPEG
```

atau binary JPEG stream.

Acceptance:

* camera preview stabil
* start/stop tidak leak process

---

# Phase 24 — Live YOLO Inference

Pipeline:

```text
USB Camera
↓
YOLO
↓
Detections
```

Output:

```text
class
confidence
bbox
```

Acceptance:

* banana detected live

---

# Phase 25 — Detection Overlay

Frontend overlay:

```text
Bounding box
Class
Confidence
```

Setting:

```text
Confidence: 0.50
```

Milestone pertama selesai:

```text
Dataset
→ Annotation
→ Training
→ USB Camera
→ Detection
```

Di sini lakukan packaging test lagi.

---

# Phase 26 — Full standalone build checkpoint

Build:

```text
VisionStudio-Setup.exe
```

Test di PC bersih.

Acceptance:

```text
No Python
No Node.js
No Git
No npm
No VS Code

Install VisionStudio
↓
Import images
↓
Train
↓
Open USB camera
↓
Detect
```

**Jangan lanjut tracking sebelum milestone ini benar-benar lolos.**

---

# Phase 27 — Tracking

Tambahkan ByteTrack.

Detection menjadi:

```text
banana
confidence: 0.92
track_id: 17
```

Acceptance:

* object yang sama mempertahankan ID reasonably

---

# Phase 28 — Draw Counting Line

Camera preview punya:

```text
[ Draw Line ]
```

Store coordinates normalized.

Example:

```text
A ---------------- B
```

Persist ke project.

---

# Phase 29 — Line Crossing

Use tracked centroid.

Detection:

```text
previous side
current side
```

Jika pindah sisi:

```text
crossing event
```

Support:

* A→B
* B→A
* both

---

# Phase 30 — Counter

Counter:

```text
Banana Count

184
```

Prevent duplicate:

```text
track_id + line_id
```

Milestone kedua:

```text
Train
→ Camera
→ Detect
→ Track
→ Draw Line
→ Count
```

Ini versi demo produk pertama.

---

# Phase 31 — ROI

Tambahkan polygon ROI.

Workflow:

```text
camera
↓
detection
↓
ROI filter
↓
tracker
```

Ignore object di luar area.

---

# Phase 32 — Events

Table:

```text
events
```

Event types awal:

```text
line_cross
```

Store:

* timestamp
* class
* track id
* count
* confidence

---

# Phase 33 — Snapshot

Saat event:

```text
frame
↓
save JPEG
↓
event snapshot
```

UI event list.

---

# Phase 34 — RTSP Camera

Camera type:

```text
usb
rtsp
```

Support:

* URL
* username
* password

Tambahkan reconnect mechanism.

---

# Phase 35 — Camera Health

Track:

* online/offline
* FPS
* dropped frame
* reconnect count

UI:

```text
Packing Camera
ONLINE
23 FPS
```

---

# Phase 36 — MQTT

Sekarang baru industrial integration.

Config:

```text
host
port
username
password
```

Action:

```text
publish line crossing
```

Topic:

```text
vision/{project}/events
```

---

# Phase 37 — MQTT Telemetry

Periodic:

```json
{
  "camera": "online",
  "count": 184,
  "fps": 22.1
}
```

Topic:

```text
vision/{project}/status
```

---

# Phase 38 — Runtime Mode

Pisahkan:

```text
Studio Mode
Runtime Mode
```

Studio:

* edit
* annotation
* training

Runtime:

* camera
* count
* events
* health

---

# Phase 39 — Fullscreen Production Mode

Untuk monitor pabrik:

```text
F11 / Fullscreen
```

UI minimal:

* camera
* count
* alarms
* status

---

# Phase 40 — Pipeline Internal Model

Sebelum visual builder, definisikan pipeline format.

Example:

```json
{
  "nodes": [],
  "edges": []
}
```

Node types:

```text
camera
detector
tracker
roi
line-cross
counter
mqtt
```

---

# Phase 41 — Pipeline Executor

Runtime yang sebelumnya hardcoded harus dipindah ke pipeline execution engine.

Contoh:

```text
Camera
↓
Detector
↓
Tracker
↓
Line Crossing
↓
Counter
```

Acceptance:

* existing counter behavior tetap sama

---

# Phase 42 — Visual Pipeline Builder

Baru sekarang gunakan React Flow atau equivalent.

User drag:

```text
Camera
Detector
Tracker
Counter
MQTT
```

Connect dengan lines.

---

# Phase 43 — Node Inspector

Klik node:

```text
Detection

Model:
banana-v3

Confidence:
0.45
```

Save ke pipeline JSON.

---

# Phase 44 — REST Action

Node:

```text
HTTP POST
```

Support:

* URL
* headers
* JSON payload

---

# Phase 45 — Modbus TCP

Action:

```text
write register
write coil
```

Example:

```text
Counter → HR40001
Alarm → Coil 1
```

---

# Phase 46 — OPC UA

Untuk awal saya sarankan Vision Studio sebagai OPC UA server.

Expose:

```text
Vision.Count
Vision.FPS
Vision.CameraOnline
Vision.LastEvent
```

SCADA tinggal subscribe.

---

# Phase 47 — Auto Annotation

User sudah punya model.

Workflow:

```text
Unannotated images
↓
Run model
↓
Suggested bounding boxes
↓
Approve / Edit / Reject
```

Jangan auto-save sebagai ground truth tanpa review.

---

# Phase 48 — Dataset Versions

```text
dataset-v1
dataset-v2
dataset-v3
```

Model mencatat:

```text
trained_from_dataset_version
```

---

# Phase 49 — Model Versions

```text
banana-v1
banana-v2
banana-v3
```

Support:

* production
* rollback

---

# Phase 50 — Active Learning

Production detection dengan confidence rendah:

```text
0.30–0.60
```

bisa masuk:

```text
Review Queue
```

Lalu:

* annotate
* add to dataset
* retrain

---

# Phase 51 — OCR

Pipeline:

```text
License Plate Detector
↓
Crop
↓
OCR
↓
Text
```

Jangan dimasukkan ke detection model.

---

# Phase 52 — Classification

Tambah project type:

```text
classification
```

Reuse:

* dataset management
* training jobs
* models
* camera runtime

---

# Phase 53 — Segmentation

Baru setelah itu tambah:

* polygon annotator
* segmentation model

Jangan dari awal.

---

# Phase 54 — GPU Detection

System service detect:

```text
NVIDIA GPU
CPU
```

Display:

```text
Compute Device
NVIDIA RTX xxxx
```

Fallback CPU wajib.

---

# Phase 55 — GPU runtime packaging

Ini perlu dites khusus.

Goal:

> User tidak install CUDA Toolkit sendiri.

Bundle runtime/library yang memang diperlukan oleh aplikasi.

Yang tetap external:

* Windows
* GPU hardware
* compatible NVIDIA driver

Jika driver tidak tersedia:

```text
GPU unavailable
Running on CPU
```

---

# Phase 56 — Offline-first behavior

Core feature harus tetap bekerja tanpa internet:

```text
Create project
Dataset
Annotation
Training
Camera
Inference
Counter
```

Internet hanya untuk optional:

* downloading extra models
* updates
* cloud sync

---

# Phase 57 — Update mechanism

Setelah stable baru buat updater.

Target:

```text
Current 1.2.0
Available 1.3.0

[ Update ]
```

Jangan implement updater sebelum packaging stabil.

---

# Phase 58 — Crash recovery

Persist state:

* last project
* active model
* pipeline state
* camera settings

Jika backend crash:

* desktop detects
* restart backend
* notify user

---

# Phase 59 — Logs

Store:

```text
%LOCALAPPDATA%\VisionStudio\logs\
```

Separate:

* desktop.log
* backend.log
* runtime.log
* training.log

Sediakan:

```text
Open Logs Folder
```

---

# Phase 60 — Final Windows QA

Test matrix minimal:

```text
Windows 10 x64
Windows 11 x64

PC without Python
PC without Node
PC without CUDA Toolkit

CPU-only PC
NVIDIA PC

USB webcam
RTSP camera
```

---

# Phase 61 — Final installer

Final artifact:

```text
VisionStudio-Setup-x64.exe
```

Installer includes:

```text
VisionStudio.exe
backend.exe
Python runtime bundled
OpenCV
YOLO
PyTorch / inference runtime
base model
frontend assets
SQLite support
required DLLs
```

User experience:

```text
Download

VisionStudio-Setup-x64.exe
      ↓
Install
      ↓
Launch Vision Studio
```

Selesai.

---

## Cara saya akan eksekusi dengan Codex

Saya sarankan jangan kasih satu phase sebagai satu prompt kalau phase-nya masih besar.

Gunakan unit:

```text
P01-S01
P01-S02
P01-S03
```

Misalnya:

```text
P11-S01 image viewer
P11-S02 draw bbox
P11-S03 save bbox
P11-S04 move bbox
P11-S05 resize bbox
```

Setiap Codex task wajib punya:

```text
GOAL

CURRENT STATE

SCOPE

REQUIREMENTS

DO NOT CHANGE

ACCEPTANCE CRITERIA

TEST COMMANDS
```

Dan hal yang sekarang paling penting: **buat packaging checkpoint berkala**, bukan hanya sekali di akhir.

Saya akan checkpoint pada:

```text
Phase 3
Basic installer

Phase 15
YOLO bundled

Phase 26
Full train + webcam standalone

Phase 30
Counter standalone

Phase 42
Pipeline builder standalone

Final
Production installer
```

Dengan begitu, kalau ada library yang ternyata tidak bisa dibundle dengan baik di Windows, ketahuan **lebih awal**, bukan setelah 2–3 bulan coding.

Kalau kamu ingin menjalankannya langsung di Codex, urutan paling masuk akal untuk sekarang adalah mulai dari **Phase 0 → Phase 3 dulu**, sampai kita benar-benar punya `VisionStudio-Setup.exe` kosong yang sudah membawa React + Tauri + FastAPI backend secara self-contained. Setelah fondasi deployment itu beres, baru masuk Project/Dataset/Annotator.
