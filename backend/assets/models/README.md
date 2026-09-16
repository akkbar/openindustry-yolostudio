# Bundled base model

Vision Studio bundles `yolo11n.pt`, the YOLO11 Nano object-detection checkpoint, for the first offline training workflow. The application verifies its SHA-256 before it is packaged and again when it is provisioned into `%LOCALAPPDATA%\VisionStudio\models\base`.

| Field | Value |
| --- | --- |
| Source | `https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt` |
| File size | 5,613,764 bytes |
| SHA-256 | `0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1` |
| Task | Object detection |
| License | Ultralytics AGPL-3.0 or Enterprise |

The checkpoint is an immutable application resource, not user-generated runtime data. The running application never downloads a model or changes the bundled checkpoint. Redistributing or using the checkpoint is subject to the applicable Ultralytics license terms.
