> Planning authority: `phase-plan.md` defines execution order; `step.md` provides detailed tasks; `Overall-plan.md` defines product vision. See [comparison and decisions](docs/plan-comparison.md) and [Phase 0 status](docs/phase-0.md). All application-owned text must always be English.

Bisa. Untuk Codex, paling efektif kalau tiap phase dibuat kecil, punya acceptance criteria, dan sebisa mungkin menghasilkan sesuatu yang langsung bisa dijalankan. Jangan suruh Codex “build full Vision Studio” karena konteksnya cepat melebar.

Saya sarankan urutannya seperti ini.

## Phase 0 — Bootstrap project

Goal: desktop app bisa jalan, backend hidup, frontend bisa konek.

**Step 0.1 — Init repo**

* `frontend/` React + TypeScript
* `backend/` FastAPI
* `desktop/` Tauri
* root README
* `.env.example`

Acceptance:

* frontend run
* backend run
* Tauri desktop membuka frontend

**Step 0.2 — Base API**
Buat:

* `GET /health`
* `GET /system/info`

Return CPU, OS, Python version.

Acceptance:

* UI menampilkan `Backend Connected`

**Step 0.3 — Base layout**
Sidebar:

* Dashboard
* Projects
* Dataset
* Models
* Cameras
* Runtime
* Settings

Belum perlu functionality.

---

# Phase 1 — Project Management

Goal: semua data punya project container.

## Step 1.1 — Project model

Buat schema:

```ts
Project {
  id
  name
  description
  taskType
  createdAt
  updatedAt
}
```

Task type awal:

```text
object_detection
```

Backend:

* create project
* list project
* get project
* update project
* delete project

Acceptance:

* CRUD berhasil dari Swagger.

## Step 1.2 — Project UI

Page:

```text
Projects

[ + New Project ]

Banana Counter
Carton Counter
```

Acceptance:

* Create dari GUI
* rename
* delete
* open project

## Step 1.3 — Project workspace

Saat project dibuka:

```text
Project: Banana Counter

Overview
Dataset
Train
Models
Camera
Runtime
```

Semua tab masih kosong.

---

# Phase 2 — Dataset Manager

Goal: user bisa import image ke project.

## Step 2.1 — Dataset entity

Schema:

```text
Dataset
id
project_id
name
path
image_count
created_at
```

Buat struktur lokal:

```text
data/
└── projects/
    └── {project_id}/
        └── datasets/
```

## Step 2.2 — Upload image

Backend:

```text
POST /projects/{id}/datasets/images
```

Support:

* jpg
* jpeg
* png
* webp

Acceptance:

* upload image
* file tersimpan
* database terupdate

## Step 2.3 — Dataset gallery

Grid:

```text
[image][image][image]
[image][image][image]
```

Feature:

* thumbnail
* image name
* annotation status
* delete

## Step 2.4 — Folder import

Support multi-file upload.

Jangan dulu recursive filesystem browser.

Acceptance:

* drag/drop 100 image
* semuanya masuk dataset

---

# Phase 3 — Classes

Goal: user bisa mendefinisikan object class.

## Step 3.1 — Class CRUD

Schema:

```text
ClassDefinition
id
project_id
name
index
```

Contoh:

```text
0 banana
1 pallet
```

## Step 3.2 — UI class manager

Sidebar annotation:

```text
Classes

1 Banana
2 Pallet

[ + Add Class ]
```

Acceptance:

* add
* rename
* delete
* class index konsisten

---

# Phase 4 — Bounding Box Annotator

Ini phase pertama yang agak besar. Pecah lagi.

## Step 4.1 — Image annotation viewer

Buat canvas/image workspace.

Harus bisa:

* load image
* fit to viewport
* zoom
* pan

Belum gambar box.

Acceptance:

* image besar tetap bisa dinavigasi.

## Step 4.2 — Draw rectangle

Mouse:

```text
mousedown
→ drag
→ mouseup
→ rectangle
```

Store coordinate relatif terhadap original image, bukan viewport.

Contoh:

```json
{
  "x": 0.21,
  "y": 0.31,
  "width": 0.32,
  "height": 0.18
}
```

Normalized `0..1`.

## Step 4.3 — Assign class

Setelah draw:

```text
Select class:
[ Banana ]
```

atau gunakan selected class dari sidebar.

## Step 4.4 — Annotation database

Schema:

```text
Annotation
id
image_id
class_id
x
y
width
height
```

Backend:

* create
* update
* delete
* list annotations per image

## Step 4.5 — Edit box

Support:

* select
* move
* resize
* delete

Acceptance:

* refresh page, annotation tetap sama.

## Step 4.6 — Keyboard shortcut

Tambahkan:

```text
D next
A previous
Delete remove
1..9 class select
```

Codex jangan disuruh implement shortcut sebelum core annotator stabil.

---

# Phase 5 — YOLO Dataset Export

Goal: annotation GUI bisa digunakan oleh Ultralytics.

## Step 5.1 — Export labels

Convert normalized annotation ke:

```text
class x_center y_center width height
```

Generate:

```text
images/
labels/
data.yaml
```

## Step 5.2 — Train/Val split

Default:

```text
80% train
20% val
```

Deterministic random seed.

## Step 5.3 — Validate dataset

Sebelum export cek:

* missing image
* invalid box
* deleted class
* image tanpa annotation

UI:

```text
Dataset Valid
212 images
538 annotations
```

---

# Phase 6 — Training Worker

Jangan training langsung dari request FastAPI.

Goal: job background terpisah dari API process.

## Step 6.1 — Training job entity

```text
TrainingJob
id
project_id
dataset_id
status
epochs
imgsz
model
started_at
finished_at
```

Status:

```text
queued
running
completed
failed
cancelled
```

## Step 6.2 — Basic YOLO training

Mulai sangat simple:

```text
yolo11n.pt
imgsz 640
epoch 50
```

Jangan bikin semua setting dulu.

## Step 6.3 — Worker process

Architecture:

```text
FastAPI
   ↓
job
   ↓
training worker
   ↓
Ultralytics
```

Bisa pakai `multiprocessing` dulu.

Belum perlu Redis/Celery.

## Step 6.4 — Training logs

Capture:

* epoch
* box_loss
* cls_loss
* precision
* recall
* mAP50

Backend menyediakan progress.

---

# Phase 7 — Training UI

## Step 7.1 — Training form

```text
Base Model
[ YOLO11n ]

Epochs
[ 50 ]

Image Size
[ 640 ]

Device
[ Auto ]

[ Train ]
```

## Step 7.2 — Progress

UI:

```text
Epoch 23 / 50
46%

Loss
Precision
Recall
mAP
```

Polling dulu.

Jangan WebSocket dulu kalau belum perlu.

## Step 7.3 — Training result

Ketika selesai tampilkan:

```text
Training completed

Best model
best.pt

mAP50
0.91
```

---

# Phase 8 — Model Registry

Goal: setiap training result menjadi model reusable.

## Step 8.1 — Model entity

```text
Model
id
project_id
training_job_id
name
path
status
metrics
created_at
```

## Step 8.2 — Model list

```text
banana-v1
banana-v2
banana-v3
```

Action:

* rename
* delete
* production
* test

## Step 8.3 — Active model

Project punya:

```text
active_model_id
```

Hanya satu model production untuk MVP.

---

# Phase 9 — USB Camera

Sekarang baru masuk camera.

## Step 9.1 — Detect camera index

Backend scan:

```text
0
1
2
...
```

Return camera yang bisa dibuka.

Jangan dulu paksa display device name.

## Step 9.2 — Camera preview

Endpoint/start worker untuk satu camera.

Frontend live preview.

Untuk MVP pakai MJPEG.

## Step 9.3 — Camera settings

Minimal:

```text
camera_index
width
height
fps
```

---

# Phase 10 — Live Detection

Goal milestone utama pertama.

## Step 10.1 — Inference worker

Input:

```text
camera
active model
confidence
```

Output:

```json
{
  "detections": [
    {
      "class": "banana",
      "confidence": 0.92,
      "bbox": []
    }
  ]
}
```

## Step 10.2 — Overlay

Frontend menggambar:

* bounding box
* class
* confidence

## Step 10.3 — Runtime controls

```text
Start
Stop

Confidence
[0.5]
```

### Milestone A

Pada titik ini user sudah bisa:

```text
Upload
→ Annotate
→ Train
→ Webcam
→ Detect
```

Kalau ini stabil, baru lanjut.

---

# Phase 11 — Tracking

## Step 11.1 — Add ByteTrack

Detection mendapatkan:

```text
track_id
```

Contoh:

```text
banana #12
banana #16
```

## Step 11.2 — Preserve track

Pastikan ID tidak terlalu mudah berubah.

Tambahkan setting:

```text
track_buffer
```

Jangan expose terlalu banyak option di UI dulu.

---

# Phase 12 — Line Drawing

## Step 12.1 — Drawing overlay

Di preview:

```text
[ Draw Line ]
```

User klik 2 titik.

Simpan normalized:

```json
{
  "x1": 0.1,
  "y1": 0.7,
  "x2": 0.9,
  "y2": 0.7
}
```

## Step 12.2 — Line entity

```text
VisionLine
id
project_id
name
coordinates
```

## Step 12.3 — Render line

Line tetap muncul setelah restart.

---

# Phase 13 — Line Crossing Counter

## Step 13.1 — Crossing detection

Gunakan centroid tracked object.

Bandingkan posisi frame sebelumnya dan sekarang terhadap line.

## Step 13.2 — Prevent duplicate count

Key:

```text
line_id + track_id
```

Jangan count object sama berkali-kali.

## Step 13.3 — Direction

Support:

```text
A → B
B → A
Both
```

## Step 13.4 — Counter UI

```text
Banana Count

184
```

### Milestone B

Sekarang user sudah bisa:

```text
Train banana model
→ choose webcam
→ draw line
→ detect + track
→ count crossing banana
```

Ini versi yang menurut saya sudah layak direkam demo.

---

# Phase 14 — ROI

## Step 14.1 — Polygon drawing

User klik beberapa titik.

```text
click
click
click
close polygon
```

## Step 14.2 — ROI filter

Detection hanya diteruskan jika centroid berada di ROI.

## Step 14.3 — Multiple ROI

Belum perlu.

MVP satu active ROI saja dulu.

---

# Phase 15 — Event System

## Step 15.1 — Event entity

```text
Event
id
project_id
camera_id
type
class
track_id
timestamp
metadata
```

## Step 15.2 — Counter event

Saat line cross:

```text
LINE_CROSS
```

Save ke DB.

## Step 15.3 — Snapshot

Ketika event:

* capture frame
* save jpg
* link ke event

## Step 15.4 — Event browser

Page:

```text
Time
Event
Class
Track
Snapshot
```

---

# Phase 16 — RTSP Camera

Setelah USB stabil.

## Step 16.1 — Camera entity

```text
Camera
id
name
type
source
```

Type:

```text
usb
rtsp
```

## Step 16.2 — RTSP input

URL:

```text
rtsp://...
```

Implement:

* reconnect
* timeout
* error status

## Step 16.3 — Camera selector

Runtime:

```text
Source
[ Packing Camera ▼]
```

---

# Phase 17 — MQTT Output

Ini baru mulai industrial integration.

## Step 17.1 — MQTT connection

Setting:

```text
host
port
username
password
```

## Step 17.2 — Test connection

Button:

```text
Test MQTT
```

## Step 17.3 — Publish event

Saat line cross:

```json
{
  "project": "banana-counter",
  "class": "banana",
  "event": "line_cross",
  "count": 185,
  "track_id": 26
}
```

Topic:

```text
vision/{project}/events
```

## Step 17.4 — Publish telemetry

Every x second:

```json
{
  "count": 185,
  "fps": 21,
  "camera": "online"
}
```

---

# Phase 18 — Runtime Profiles

Pisahkan edit dan run.

## Step 18.1 — Studio mode

Semua config editable.

## Step 18.2 — Runtime mode

Hide:

* annotation
* training
* project edit

Display:

* camera
* count
* status
* events

## Step 18.3 — Fullscreen mode

Untuk industrial monitor.

---

# Phase 19 — Pipeline Engine

Baru setelah feature dasar bekerja.

Jangan langsung bikin drag-drop.

## Step 19.1 — Define pipeline schema

Misalnya:

```json
{
  "nodes": [],
  "edges": []
}
```

## Step 19.2 — Hardcoded node types

Mulai:

```text
Camera
Detection
Tracking
ROI
LineCross
Counter
MQTT
```

## Step 19.3 — Pipeline executor

Topological execution.

## Step 19.4 — Convert existing runtime

Runtime lama harus dijalankan lewat pipeline engine.

Ini penting sebelum UI graph dibuat.

---

# Phase 20 — Visual Pipeline Builder

Sekarang pakai React Flow.

## Step 20.1 — Canvas

Drag node.

## Step 20.2 — Connect edge

```text
Camera
 ↓
Detection
```

## Step 20.3 — Property inspector

Klik node:

```text
Detection

Model
Confidence
Class
```

## Step 20.4 — Save/load

Persist graph sebagai JSON.

### Milestone C

Sekarang Vision Studio sudah menjadi **no-code vision builder**.

---

# Phase 21 — REST Actions

Node:

```text
HTTP Request
```

Support:

* POST
* URL
* headers
* JSON template

Trigger dari event.

---

# Phase 22 — Database Actions

MVP cukup:

* SQLite built-in
* PostgreSQL external

Action:

```text
Insert event
```

---

# Phase 23 — Modbus TCP

Node:

```text
Modbus Write
```

Mapping:

```text
counter → register
alarm → coil
```

Harus ada simulator/test UI.

---

# Phase 24 — OPC UA

Bisa dua pendekatan.

Untuk awal lebih simpel:

Vision Studio sebagai **OPC UA server**.

Expose:

```text
Vision.Count
Vision.FPS
Vision.CameraOnline
Vision.LastEvent
```

Lebih gampang untuk SCADA subscribe.

---

# Phase 25 — Auto Annotation

Baru setelah manual annotation stabil.

## Step 25.1

User pilih model existing.

## Step 25.2

Inference seluruh unannotated images.

## Step 25.3

Generate annotation dengan state:

```text
suggested
```

## Step 25.4

User:

* approve
* adjust
* reject

---

# Phase 26 — Dataset Versioning

```text
dataset-v1
dataset-v2
dataset-v3
```

Training job harus refer exact version.

---

# Phase 27 — Active Learning

Collect:

* low-confidence detection
* manually marked false detection

Masukkan ke:

```text
Review Queue
```

User bisa convert ke training data.

---

# Phase 28 — OCR Pipeline

Jangan dicampur dengan YOLO.

Nodes:

```text
Detection
→ Crop
→ OCR
→ Text Filter
```

Use case:

```text
license_plate
```

---

# Phase 29 — Classification

Tambah project task:

```text
classification
```

Baru sesudah detection flow matang.

---

# Phase 30 — Segmentation

Task berikutnya:

```text
segmentation
```

Annotator baru perlu polygon/mask.

Jangan implement polygon segmentation di awal hanya karena ingin future-proof.

---

# Cara kasih task ke Codex

Jangan prompt seperti:

> Build dataset manager.

Lebih baik satu task seperti:

> Implement backend project CRUD only. Do not modify the frontend except API types if required. Use SQLite and SQLAlchemy. Create Project model with id UUID, name, description, task_type, created_at, updated_at. Add REST endpoints under `/api/projects`. Add validation and pytest tests. Do not implement datasets yet.

Lalu task berikutnya:

> Implement the Projects page in React using the existing project API. Add list, create, rename, delete and open actions. Do not modify backend behavior. Preserve existing layout and styling.

Pola setiap Codex task:

```text
GOAL
SCOPE
FILES LIKELY INVOLVED
REQUIREMENTS
DO NOT
ACCEPTANCE CRITERIA
TEST
```

Contoh:

```text
GOAL
Add rectangle annotation drawing.

SCOPE
Frontend annotation canvas only.

REQUIREMENTS
- Load existing image.
- User can drag to create rectangle.
- Store coordinates normalized 0..1.
- Rectangle stays correctly positioned after zoom.
- Selected class comes from annotation sidebar.

DO NOT
- Add polygon annotation.
- Add YOLO export.
- Add keyboard shortcuts.
- Change backend schema.

ACCEPTANCE
- Draw rectangle.
- Resize browser window.
- Rectangle remains aligned.
- Saved rectangle reloads correctly.
```

Ini jauh lebih aman untuk Codex daripada prompt panjang lintas subsystem.

## Urutan repo commit yang saya sarankan

Bikin commit atau checkpoint setelah tiap unit:

```text
001 bootstrap
002 project-api
003 project-ui
004 dataset-upload
005 dataset-gallery
006 class-manager
007 annotation-viewer
008 bounding-box-draw
009 annotation-persistence
010 annotation-editing
011 yolo-export
012 training-job
013 training-worker
014 training-ui
015 model-registry
016 usb-camera
017 camera-preview
018 live-inference
019 overlay
020 tracking
021 line-builder
022 line-counter
023 roi
024 event-log
025 snapshot
026 rtsp
027 mqtt
028 runtime-mode
029 pipeline-engine
030 pipeline-builder
```

Kalau ada masalah di phase 24, Codex tidak perlu menyentuh 30 fitur sekaligus.

Untuk versi pertama, saya bahkan akan **stop dulu di commit 022**. Kalau sampai sana stabil, kamu sudah punya aplikasi end-to-end:

**dataset → annotate → train → webcam → YOLO → tracking → draw line → counter.**

Setelah itu baru industrialize dengan ROI, RTSP, MQTT, pipeline builder, Modbus, dan OPC UA.
