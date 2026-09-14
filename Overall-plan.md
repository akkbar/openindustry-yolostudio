> Planning authority: `phase-plan.md` defines execution order; `step.md` provides detailed tasks; `Overall-plan.md` defines product vision. See [comparison and decisions](docs/plan-comparison.md) and [Phase 0 status](docs/phase-0.md). All application-owned text must always be English.

Bisa. Saya akan arahkan produknya bukan sebagai **“YOLO Desktop”**, tapi sebagai **Vision Studio / Industrial Vision Builder** yang bisa dipakai operator atau engineer tanpa harus coding Python.

Secara besar, produk akhirnya seperti ini:

```text
Dataset
   ↓
Annotate
   ↓
Train
   ↓
Validate
   ↓
Deploy Model
   ↓
Connect Camera
   ↓
Build Vision Logic
   ↓
Run
   ↓
Counter / Alarm / MQTT / PLC / API / DB
```

## 1. Goal produk

Target utama:

> User bisa membuat aplikasi computer vision dari nol sampai production hanya lewat GUI.

Contoh user ingin menghitung box di pallet:

```text
1. Create Project
2. Upload 300 foto box
3. Buat class "carton"
4. Bounding box semua carton
5. Train model
6. Test model
7. Pilih USB Camera / RTSP
8. Draw ROI
9. Draw counting line
10. Pilih "carton crosses Line 1"
11. Counter +1
12. Publish hasil via MQTT
```

Tidak perlu user membuka:

```text
Python
Terminal
YOLO CLI
OpenCV code
training script
```

---

# 2. Positioning

Saya akan bagi menjadi 3 layer produk:

```text
VISION STUDIO
│
├── Dataset Studio
│   ├── Dataset
│   ├── Annotation
│   └── Training
│
├── Vision Runtime
│   ├── Camera
│   ├── Inference
│   ├── Tracking
│   └── Vision Logic
│
└── Industrial Integration
    ├── MQTT
    ├── REST
    ├── Modbus
    ├── OPC UA
    ├── Database
    └── PLC
```

Ini lebih kuat daripada sekadar:

> “GUI buat training YOLO.”

---

# 3. Tech stack

Karena kamu sudah menggunakan FastAPI dan React, saya sarankan tetap di stack itu.

```text
Desktop UI
React + TypeScript
        │
        ▼
Desktop wrapper
Tauri
        │
        ▼
FastAPI
Python
        │
        ├── Ultralytics
        ├── OpenCV
        ├── PyTorch
        ├── ByteTrack
        ├── ONNX Runtime
        └── OCR engine
```

Kenapa **Tauri** daripada Electron:

```text
Tauri
+ executable lebih kecil
+ RAM lebih rendah
+ React tetap bisa dipakai
+ cocok untuk industrial PC
+ backend Python tetap independent
```

Arsitekturnya:

```text
┌───────────────────────────────┐
│        Tauri Desktop          │
│                               │
│ React + TypeScript            │
│                               │
│ Dataset                       │
│ Annotator                     │
│ Camera                        │
│ Pipeline Builder              │
│ Dashboard                     │
└──────────────┬────────────────┘
               │ HTTP / WS
               ▼
┌───────────────────────────────┐
│          FastAPI              │
│                               │
│ dataset-service               │
│ training-service              │
│ inference-service             │
│ camera-service                │
│ pipeline-engine               │
└──────────────┬────────────────┘
               │
               ▼
┌───────────────────────────────┐
│ Vision Engine                 │
│                               │
│ YOLO                          │
│ OpenCV                        │
│ ByteTrack                     │
│ OCR                           │
│ ONNX                          │
└───────────────────────────────┘
```

---

# 4. Main navigation

Saya sarankan UI utamanya:

```text
Dashboard

Projects

Dataset
├─ Images
├─ Annotation
├─ Classes
└─ Augmentation

Models
├─ Training
├─ Experiments
├─ Models
└─ Benchmark

Cameras
├─ Connected Cameras
├─ USB Cameras
├─ RTSP
└─ Test Stream

Vision Builder
├─ Pipelines
├─ ROI
├─ Rules
└─ Actions

Runtime
├─ Live View
├─ Events
├─ Counters
└─ Logs

Integrations
├─ MQTT
├─ REST
├─ Modbus
├─ OPC UA
└─ Database

Settings
```

---

# 5. Project concept

Semua harus berbasis **Project**.

Misalnya:

```text
Projects
│
├── Banana Counter
├── Pallet Box Counter
├── PPE Detection
├── License Plate
└── Product Inspection
```

Project menyimpan:

```text
project
├── dataset
├── annotations
├── classes
├── models
├── cameras
├── pipelines
├── counters
├── integration
└── runtime settings
```

---

# 6. Project creation wizard

Saat Create Project:

```text
New Vision Project

Project Name:
[ Pallet Carton Counter ]

Task:
(•) Object Detection
( ) Classification
( ) Segmentation
( ) Pose
( ) OCR
( ) Anomaly Detection

Template:
[ Object Counter ▼]

Hardware:
[ Auto Detect ▼]

Project Location:
D:\VisionProjects\PalletCounter
```

Template sangat penting.

Contoh:

```text
Blank Project

Object Detection

Object Counter

People Counter

PPE Detection

License Plate Detection

Vehicle Counter

Quality Inspection
```

---

# 7. Dataset Manager

Dataset page:

```text
Dataset: pallet-box

Images:        824
Annotated:     712
Unannotated:   112

Classes:
carton      5,724 instances
pallet        824 instances
```

Import:

```text
Add Data

[ Upload Images ]

[ Upload Folder ]

[ Import Video ]

[ Capture Camera ]

[ RTSP Capture ]

[ Existing YOLO Dataset ]
```

---

# 8. Video → dataset

Ini menurut saya wajib.

User bisa:

```text
Video:
production.mp4

Extract Frame Every:
[ 2 seconds ]

Maximum:
[ 500 images ]

☑ Avoid similar frames
```

Kemudian:

```text
video
 ↓
frame extraction
 ↓
similarity filtering
 ↓
dataset
```

Nanti similarity filtering bisa menggunakan perceptual hash atau embedding.

---

# 9. Camera capture dataset

User juga bisa langsung ambil dataset dari kamera:

```text
Camera:
[ USB Camera Logitech C920 ]

Preview

[ Capture ]

Auto Capture:
Every [ 3 ] sec

Target:
[ 300 images ]
```

---

# 10. Annotation Studio

Ini salah satu fitur paling penting.

Layout:

```text
┌─────────────┬────────────────────────┬──────────────┐
│ Dataset     │                        │ Classes      │
│             │                        │              │
│ img001.jpg  │       IMAGE            │ carton       │
│ img002.jpg  │                        │ pallet       │
│ img003.jpg  │      [ BOX ]           │              │
│             │                        │              │
│             │                        │              │
└─────────────┴────────────────────────┴──────────────┘

Prev    21 / 500    Next
```

Shortcut:

```text
W = draw box
D = next
A = previous
Delete = remove box
1 = carton
2 = pallet
```

---

# 11. Auto annotation

Setelah user annotate misalnya:

```text
50 dari 500 images
```

dia bisa klik:

```text
Auto Annotate Remaining
```

Workflow:

```text
50 manual annotation
       ↓
temporary training
       ↓
model detects remaining 450
       ↓
user review
       ↓
approve / reject / adjust
```

Ini bakal sangat menghemat effort.

---

# 12. Annotation types

Tahap awal cukup:

```text
Bounding Box
```

Kemudian:

```text
Phase 2

Polygon
Segmentation Mask
Keypoints
Rotated Bounding Box
```

---

# 13. Dataset split

GUI:

```text
Dataset Split

Training      70%
Validation    20%
Testing       10%

[ Generate Split ]
```

User tidak perlu paham struktur:

```text
images/train
labels/train
images/val
labels/val
```

---

# 14. Data augmentation

GUI:

```text
Augmentation

☑ Horizontal Flip
☑ Brightness
☑ Contrast
☑ Blur
☑ Rotation

Rotation:
[-10° ────── 10°]

Brightness:
[0.8 ─────── 1.2]
```

Ada preview sebelum diterapkan.

---

# 15. Training UI

Training page:

```text
Train Model

Model:
[ YOLO Nano ▼ ]

Dataset:
[ pallet-box-v3 ]

Image Size:
[ 640 ]

Epoch:
[ 100 ]

Batch:
[ Auto ]

Device:
[ NVIDIA RTX 3060 ]

Advanced Settings >
```

Button:

```text
[ Start Training ]
```

---

# 16. Training progress

Display:

```text
Training

Epoch:
46 / 100

Progress:
██████████████░░░ 46%

GPU:
72%

VRAM:
4.8 / 6 GB

mAP50:
0.92

Precision:
0.90

Recall:
0.88

Loss:
0.31
```

Chart:

```text
Epoch vs Loss
Epoch vs mAP
Epoch vs Precision
Epoch vs Recall
```

---

# 17. Experiment management

Jangan overwrite training lama.

Struktur:

```text
Experiments

EXP-001
YOLO Nano
640
100 epochs
mAP 0.91

EXP-002
YOLO Small
640
120 epochs
mAP 0.94

EXP-003
YOLO Nano
960
100 epochs
mAP 0.93
```

Kemudian user bisa:

```text
Compare Experiments
```

---

# 18. Model Registry

Model management:

```text
Models

pallet-v1
pallet-v2
pallet-v3

Status:

Development
Validated
Production
Archived
```

Misalnya:

```text
pallet-v3

Task:
Detection

Accuracy:
mAP50 94.2%

Input:
640×640

Size:
6.3 MB

Runtime:
23ms

Status:
Production
```

---

# 19. Export model

User bisa export:

```text
.pt
ONNX
OpenVINO
TensorRT
```

Tidak perlu semuanya di MVP.

MVP cukup:

```text
.pt
ONNX
```

---

# 20. Camera Manager

Page:

```text
Connected Cameras

USB
────────────────

Logitech C920
USB Camera #1

[Preview] [Use]


Network
────────────────

Packing Line Camera
rtsp://192.168.1.20/stream

[Preview] [Use]
```

---

# 21. USB camera discovery

FastAPI/OpenCV detect:

```text
Camera 0
Camera 1
Camera 2
```

Kalau Windows bisa dikembangkan menggunakan DirectShow/WMI supaya nama device muncul:

```text
Logitech C920
Integrated Webcam
Hikvision USB Camera
```

---

# 22. RTSP camera

Form:

```text
Add Network Camera

Name:
Packing Camera

Protocol:
[ RTSP ]

URL:
rtsp://192.168.10.20:554/stream

Username:
admin

Password:
••••••••

[ Test Connection ]
```

---

# 23. Camera settings

```text
Resolution
FPS
Rotation
Flip
Reconnect

Buffer size
Frame skip
```

Contoh:

```text
Source FPS: 30

Inference FPS:
10
```

Supaya GPU tidak perlu proses semua frame.

---

# 24. Vision Builder

Ini menurut saya harus menjadi **killer feature**.

UI drag-and-drop:

```text
┌────────┐
│ Camera │
└───┬────┘
    │
    ▼
┌────────────┐
│ Detection  │
└─────┬──────┘
      │
      ▼
┌────────────┐
│ Tracker    │
└─────┬──────┘
      │
      ▼
┌────────────┐
│ ROI Filter │
└─────┬──────┘
      │
      ▼
┌───────────────┐
│ Line Crossing │
└───────┬───────┘
        │
        ▼
┌─────────┐
│ Counter │
└────┬────┘
     │
     ▼
┌──────────┐
│ MQTT Out │
└──────────┘
```

---

# 25. Node categories

Saya akan buat nodes:

```text
SOURCE

Camera
Video
Image
RTSP


AI

Detection
Classification
Segmentation
OCR
Pose


PROCESSING

Resize
Crop
ROI
Filter
Debounce
Tracking


LOGIC

Line Crossing
Zone Enter
Zone Exit
Object Present
Object Missing
Count
Timer
Compare


OUTPUT

Counter
Alarm
Snapshot
Video Record

MQTT
REST API
Database
Modbus
OPC UA
```

---

# 26. Detection node

Properties:

```text
Model:
[ banana-v3 ]

Confidence:
0.45

IoU:
0.5

Classes:
☑ banana
☐ person
☐ truck
```

---

# 27. Tracker node

Untuk counter tracking itu penting.

Misalnya:

```text
Tracker

Type:
[ ByteTrack ]

Track Buffer:
30

Minimum Confidence:
0.3
```

Object punya:

```text
Track ID: 27
Track ID: 28
Track ID: 29
```

Supaya pisang yang sama tidak dihitung 20 kali.

---

# 28. ROI Builder

User tinggal klik:

```text
Draw ROI
```

lalu bikin polygon:

```text
     __________________
    /                  \
   /      ACTIVE        \
  |       ZONE           |
   \                    /
    \__________________/
```

Object di luar ROI diabaikan.

---

# 29. Line drawing

User:

```text
[ Draw Counting Line ]
```

Lalu drag:

```text
A -------------------------- B
```

Properties:

```text
Name:
Line 1

Direction:

A → B
B → A
Both
```

---

# 30. Counting

Misalnya:

```text
IF

Object:
carton

Cross:
Line 1

Direction:
A → B

THEN

Increment:
CartonCounter
```

Hasil:

```text
Carton Counter

IN:
184

OUT:
12

Current:
172
```

---

# 31. Zone events

Selain counting line:

```text
Object enters Zone A

Object exits Zone A

Object stays > 10 seconds

Object count > 5

Object missing > 30 seconds
```

Ini penting untuk industrial use case.

---

# 32. Rule builder

Selain node graph, sediakan versi simple:

```text
WHEN

[ carton ]

[ crosses ]

[ Line 1 ]

THEN

[ increment counter ]
```

Atau:

```text
WHEN

[ person ]

[ enters ]

[ dangerous-zone ]

THEN

[ trigger alarm ]
```

---

# 33. Actions

Setiap rule bisa punya banyak action.

```text
Action

☑ Increment Counter

☑ Save Snapshot

☑ Publish MQTT

☑ Send REST API

☑ Store Event

☑ Trigger PLC
```

---

# 34. MQTT integration

Sangat cocok dengan OpenAIoT.

Configuration:

```text
Broker:
192.168.1.20

Port:
1883

Topic:
factory/packing/carton-counter
```

Payload:

```json
{
  "camera": "packing-line-1",
  "class": "carton",
  "count": 184,
  "timestamp": "2026-09-14T15:32:41"
}
```

---

# 35. MQTT event

Untuk detection:

```json
{
  "event": "line_cross",
  "track_id": 124,
  "class": "carton",
  "confidence": 0.91,
  "direction": "in"
}
```

---

# 36. Modbus integration

Kemudian industrial user bisa mapping:

```text
Counter → Holding Register 40001

Alarm → Coil 00001

Object Present → Coil 00002
```

Contoh:

```text
Carton Counter
↓
Modbus TCP
↓
PLC
↓
D4000
```

---

# 37. OPC UA

Mapping:

```text
Vision.Cartons.Count

Vision.Cartons.Rate

Vision.Camera.Status

Vision.Alarm.Active
```

Sehingga SCADA bisa subscribe.

---

# 38. REST API

User bisa:

```text
POST
http://mes.local/api/production/count
```

Payload bisa dikustom.

---

# 39. Runtime screen

Production mode harus simpel.

```text
Packing Line Vision
─────────────────────────────

LIVE CAMERA


 [BOX 97%]
      ┌───────────┐
      │   carton  │
      └───────────┘

-------------------------------- Counting Line


Today Count

        12,482


Rate

        41/min


Camera: ONLINE
Model: pallet-v3
GPU: 48%
```

---

# 40. Runtime overlay

User bisa memilih:

```text
☑ Bounding Box
☑ Class Name
☑ Confidence
☑ Track ID
☑ ROI
☑ Counting Line
☑ Counter
☑ FPS
```

---

# 41. Runtime modes

Saya akan buat 3 mode:

```text
Studio Mode

Development / configuration


Test Mode

Run pipeline + debug


Production Mode

Locked runtime
```

Production operator tidak bisa edit model sembarangan.

---

# 42. Event system

Setiap event disimpan:

```text
2026-09-14 13:21:12
Carton crossed Line 1

Track:
#1832

Confidence:
94%

Snapshot:
event_1832.jpg
```

---

# 43. Event filtering

```text
Camera

Event

Class

Date

Confidence

Rule
```

---

# 44. Snapshot & recording

Rule:

```text
WHEN

person enters dangerous zone

THEN

snapshot
+
record 5 sec before
+
record 10 sec after
```

Ini sangat berguna buat HSE.

---

# 45. Ring buffer

Untuk bisa record **sebelum event**, runtime punya:

```text
Video Ring Buffer

Last 10 sec
```

Jadi alarm terjadi pada detik 10:

```text
Video:

00:00 - 00:10 before
00:10 event
00:10 - 00:20 after
```

---

# 46. Dashboard

Global:

```text
CAMERAS

12 Online
1 Offline


PIPELINES

9 Running
1 Stopped


EVENTS TODAY

4,829


GPU

61%
```

---

# 47. Health monitoring

Vision deployment sering gagal bukan karena AI, tapi kamera.

Monitor:

```text
Camera Connected

FPS

Inference latency

Dropped Frames

GPU

RAM

CPU

Model status
```

---

# 48. Watchdog

Kalau RTSP disconnect:

```text
retry 1 sec

retry 3 sec

retry 5 sec

retry 10 sec
```

Tidak langsung crash.

---

# 49. Dataset versioning

Jangan cuma satu dataset.

```text
Pallet Dataset

V1
300 images

V2
550 images

V3
824 images
```

Model harus tahu berasal dari dataset mana.

```text
pallet-v3

Dataset:
pallet-dataset-v3
```

---

# 50. Misclassification feedback

Production bisa membantu training baru.

Operator klik object salah:

```text
[ Wrong Detection ]
```

otomatis:

```text
snapshot
↓
review queue
↓
dataset
↓
retrain
```

Ini sangat powerful.

---

# 51. Active learning

Nanti sistem otomatis cari:

```text
low confidence

unknown object

false detection candidate

edge cases
```

Misalnya:

```text
confidence:
0.3 - 0.6
```

masuk:

```text
Needs Review
```

---

# 52. OCR

Setelah detection matang:

```text
License Plate Detection
         ↓
crop plate
         ↓
OCR
         ↓
B 1234 XYZ
```

Jangan gabungkan OCR ke detection model.

Pipeline:

```text
YOLO License Plate
        ↓
Crop
        ↓
OCR
        ↓
Regex
        ↓
Plate Event
```

---

# 53. Classification

Contoh:

```text
Product
 ↓
Good / NG
```

Pipeline:

```text
Camera
 ↓
Crop ROI
 ↓
Classifier
 ↓
Good / Reject
```

---

# 54. Segmentation

Nanti:

```text
Detection
Segmentation
```

Untuk:

```text
defect area
surface
material
liquid
shape
```

---

# 55. Measurement

Industrial feature yang menarik:

```text
Pixel → mm calibration
```

User:

```text
Draw calibration line

known length:
100 mm
```

Kemudian:

```text
Object width:
98.7 mm

Tolerance:
100 ± 2 mm

PASS
```

---

# 56. PLC trigger capture

Selain continuous camera:

```text
PLC Trigger
      ↓
capture frame
      ↓
AI inspection
      ↓
PASS / FAIL
      ↓
PLC
```

Ini sangat common industrial.

---

# 57. Digital input support

Later:

```text
PLC

Modbus

GPIO

Industrial IO
```

bisa trigger inference.

---

# 58. Database

Saya sarankan:

```text
SQLite
```

untuk desktop standalone.

Simpan:

```text
projects
datasets
models
cameras
pipelines
events
counters
settings
```

Untuk deployment besar:

```text
PostgreSQL
```

---

# 59. Folder architecture

Misalnya:

```text
vision-studio/
│
├── desktop/
│   └── React + Tauri
│
├── backend/
│   └── FastAPI
│
├── vision/
│   ├── detection/
│   ├── tracking/
│   ├── segmentation/
│   └── ocr/
│
├── pipeline/
│
├── integrations/
│   ├── mqtt/
│   ├── modbus/
│   ├── opcua/
│   └── rest/
│
└── projects/
```

---

# 60. Backend module structure

Saya akan buat:

```text
backend/
│
├── api/
│
├── cameras/
│
├── datasets/
│
├── annotations/
│
├── training/
│
├── inference/
│
├── tracking/
│
├── pipelines/
│
├── integrations/
│
├── events/
│
└── system/
```

---

# 61. FastAPI APIs

Contoh:

```text
GET /api/cameras

POST /api/cameras

GET /api/projects

POST /api/projects

GET /api/datasets

POST /api/datasets/import

POST /api/training/start

GET /api/training/{id}

POST /api/inference/start

POST /api/inference/stop

GET /api/pipelines

POST /api/pipelines

GET /api/events
```

---

# 62. WebSocket

Untuk:

```text
camera frames

detections

training progress

GPU usage

runtime events
```

Gunakan:

```text
/api/ws/runtime
/api/ws/training
```

---

# 63. Frame streaming

Saya tidak sarankan kirim 30 FPS raw lewat JSON.

Gunakan:

```text
JPEG stream

WebRTC

atau websocket binary
```

MVP:

```text
JPEG websocket / MJPEG
```

nanti optimize.

---

# 64. Process architecture

Jangan satu Python process menangani semua.

Minimal:

```text
vision-desktop

fastapi-api

training-worker

vision-worker
```

Karena training bisa berat.

---

# 65. Worker architecture

```text
React
   │
FastAPI
   │
   ├── Training Worker
   │
   └── Runtime Worker
```

Kalau training crash, UI tetap jalan.

---

# 66. GPU manager

System page:

```text
Compute

NVIDIA RTX 3060

CUDA:
Available

VRAM:
6 GB

Driver:
OK
```

Fallback:

```text
GPU unavailable

Use CPU
```

---

# 67. Benchmark

Model bisa dites:

```text
Benchmark

Model:
pallet-v3

Device:
RTX3060

Average:
18ms

FPS:
55

mAP:
94%
```

Jadi user tahu apakah cocok untuk production.

---

# 68. Deployment profile

Contoh:

```text
Deployment Profile

High Accuracy
Balanced
High Speed
```

High speed otomatis:

```text
image 416
smaller model
frame skip
```

---

# 69. Model hot swap

Production:

```text
Model V3 → V4
```

tanpa restart app.

Dan bisa rollback:

```text
Rollback to V3
```

---

# 70. Licensing

Karena sebelumnya kamu sudah punya host installer/license manager, Vision Studio bisa masuk ke situ.

```text
License

Vision Basic

Vision Pro

Vision Industrial
```

Contoh:

```text
Basic

USB camera
1 pipeline
Detection
Counter


Pro

RTSP
Multiple camera
OCR
Training


Industrial

MQTT
Modbus
OPC UA
PLC
Multiple runtime workers
```

---

# 71. Host integration

Arsitektur dengan platform kamu:

```text
Host Manager
│
├── License
├── Container Manager
├── Connected Camera
└── Vision Service
```

Bisa detect:

```text
vision-service running

GPU available

Camera 3 connected
```

---

# 72. OpenAIoT integration

Saya akan posisikan:

```text
OpenAIoT
│
├── SCADA
├── MES
├── Maintenance
├── Production
├── AI Chat
│
└── Vision Studio
```

Vision adalah data source tambahan:

```text
Machine
Sensor
PLC
Camera
```

jadi:

```text
OT DATA
├── PLC
├── OPC UA
├── Modbus
├── MQTT
└── Vision
```

---

# 73. Project templates

Ini sangat penting untuk adoption.

Buat template:

```text
Object Counter

People Counter

Pallet Box Counter

Vehicle Counter

License Plate

PPE

Danger Zone

Product Inspection

Missing Component

Production Counter
```

User tidak mulai dari kosong.

---

# 74. Banana example

Workflow lengkap:

```text
Create Project
Banana Counter
      ↓
Import
500 images
      ↓
Class
banana
      ↓
Annotate
100 images
      ↓
Train preliminary
      ↓
Auto annotate
400 images
      ↓
Review
      ↓
Train final
      ↓
Test
      ↓
USB Camera
      ↓
YOLO
      ↓
ByteTrack
      ↓
Draw Line
      ↓
Line Crossing
      ↓
Counter
      ↓
Dashboard
```

---

# 75. Pallet carton case

Untuk project kamu nanti:

```text
Camera
    ↓
Carton Detector
    ↓
Tracker
    ↓
Pallet ROI
    ↓
Unique object counter
    ↓
Pallet complete?
```

Nanti bahkan bisa:

```text
Expected:
48 cartons

Detected:
47

Status:
MISSING 1
```

---

# 76. MVP scope

Jangan langsung bangun semuanya.

### MVP 1

Target:

> foto → annotation → training → webcam detection.

Fitur:

```text
Project

Dataset Import

Bounding Box Annotation

YOLO Training

Model Manager

USB Camera

Live Detection
```

Kalau ini belum stabil, jangan bikin PLC dulu.

---

# 77. MVP 2

Tambahkan:

```text
RTSP

ByteTrack

ROI

Line

Counter

Event

Snapshot
```

Sudah bisa jadi produk usable.

---

# 78. MVP 3

Tambahkan:

```text
Pipeline Builder

MQTT

REST

Database

Multiple Camera
```

Ini titik mulai **industrial product**.

---

# 79. MVP 4

Tambahkan:

```text
Modbus

OPC UA

PLC trigger

OCR

Classification

Segmentation
```

---

# 80. MVP 5

Smart dataset:

```text
Auto annotation

Active learning

Training recommendations

Dataset versioning

Model comparison

Edge case detection
```

---

# 81. Later AI assistant

Baru setelah semuanya matang, tambahkan assistant.

User bisa bilang:

> Count cartons crossing the lower line and publish the result to `factory/packing/count`.

AI generate:

```text
Camera
↓
Detection(carton)
↓
Tracking
↓
Line Crossing
↓
Counter
↓
MQTT
```

Ini akan sangat menarik.

---

# 82. Recommended development order

Kalau saya yang build, urutannya:

```text
1 Project management

2 Dataset manager

3 Image viewer

4 Bounding box annotator

5 YOLO dataset export

6 Train worker

7 Training monitor

8 Model registry

9 USB camera discovery

10 Live inference

11 Bounding box overlay

12 Tracking

13 ROI

14 Line drawing

15 Line crossing

16 Counter

17 Runtime mode

18 Event database

19 Snapshot

20 RTSP

21 MQTT

22 Pipeline builder

23 REST output

24 Multi camera

25 Modbus

26 OPC UA

27 OCR

28 Auto annotation

29 Dataset versioning

30 Active learning
```

---

# 83. First real milestone

Saya akan menetapkan milestone pertama:

> **User bisa membuat Banana Counter tanpa mengetik satu baris kode.**

Acceptance test:

```text
☑ create project

☑ upload banana images

☑ annotate banana

☑ train

☑ see training progress

☑ save model

☑ select USB camera

☑ live detection

☑ draw counting line

☑ banana crosses line

☑ count increases
```

Kalau 10 item ini sudah berjalan, sebenarnya kamu sudah punya **produk yang demonstrable**, bukan sekadar proof-of-concept.

---

# Bentuk produk akhirnya

Menurut saya arahnya jangan:

```text
YOLO GUI
```

tetapi:

```text
OpenAIoT Vision Studio

Dataset
   ↓
Annotation
   ↓
Training
   ↓
Vision Logic
   ↓
Industrial Deployment
```

Dan value proposition-nya bisa sangat sederhana:

> **Build industrial computer vision applications without writing code.**

Yang paling menarik adalah kombinasi pengalamanmu di **PLC + SCADA + MQTT + industrial software** dengan vision. Kebanyakan annotation/training tools berhenti di **“model berhasil mendeteksi object”**. Produkmu justru bisa melanjutkan sampai:

```text
Object detected
       ↓
Decision
       ↓
Production logic
       ↓
PLC / MES / SCADA / MQTT
```

Itu yang menurut saya pantas dijadikan pembeda utama Vision Studio di OpenAIoT.



repo: https://github.com/akkbar/openindustry-yolostudio