# Vision Studio desktop preview

Open `VisionStudio.exe`. Keep the `backend` folder next to it, including its entire `_internal` directory. No Python or Node installation is needed. This portable folder requires Microsoft Edge WebView2 already installed; the Windows setup executable includes its offline installer.

The desktop launches its own local backend, waits for readiness, and then opens the English application interface. Closing the window stops that backend. Application data and logs live under `%LOCALAPPDATA%\VisionStudio`. A failed backend produces an English error in the interface and diagnostic logs instead of connecting to another service.

Dashboard and Settings show actual connection, system, and database information. Projects supports create, open, rename, description edits, and confirmed deletion. SQLite stores the workspace in `data/visionstudio.db`; each project has its own dataset, models, runs, and events folders. Import JPG, JPEG, PNG, and WEBP images through Select images or drag-and-drop. Original files are copied into the project with generated thumbnails. The Dataset gallery shows paginated thumbnails, names, dimensions, and annotation status. Select an image to preview its original or confirm deletion to remove it and its annotations. Annotation editing, AI, and camera capture are planned for later phases.
