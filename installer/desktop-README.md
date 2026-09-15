# Vision Studio desktop preview

Open `VisionStudio.exe`. Keep the `backend` folder next to it, including its entire `_internal` directory. No Python or Node installation is needed. This portable folder requires Microsoft Edge WebView2 already installed; the Windows setup executable includes its offline installer.

The desktop launches its own local backend, waits for readiness, and then opens the English application interface. Closing the window stops that backend. Application data and logs live under `%LOCALAPPDATA%\VisionStudio`. A failed backend produces an English error in the interface and diagnostic logs instead of connecting to another service.

Dashboard and Settings show actual connection and system information. Projects, Dataset, Models, Cameras, and Runtime are planned workspaces. This preview has no AI, camera capture, or project database yet.
