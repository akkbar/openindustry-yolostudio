# Apple detector demo dataset

Vision Studio can download one complete public demonstration dataset from the Projects page. It creates an `Apple detector demo` project only after every source image and its YOLO annotation have been validated and copied into local application storage.

The source is [AppleBBCH76](https://www.kaggle.com/datasets/projectlzp201910094/applebbch76), published by RTA & LatHort projects under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). It contains 3,169 640×640 orchard images and one `apple` class. The original labels use normalized YOLO bounding boxes.

The download is about 233 MiB. Vision Studio keeps the archive in `%LOCALAPPDATA%\VisionStudio\demo-datasets\applebbch76-v1.zip`, then stores imported images, thumbnails, classes, and annotations below the demo project's normal folder. A later retry reuses a valid cached archive. Deleting the demo project leaves the cache available for a future import.

The importer accepts the fixed source layout only: `images/<name>.<image-extension>` and `labels/<name>.txt`. It rejects archives that do not include all 3,169 source images, matching label files, safe paths, valid image data, or in-range class-0 YOLO boxes. A failed import removes its incomplete project data.

Open the demo project to inspect annotations, export a YOLO snapshot, train a local model, promote the completed checkpoint, and test it in the Cameras page. Dataset snapshots use Vision Studio's deterministic 80/20 training/validation split.
