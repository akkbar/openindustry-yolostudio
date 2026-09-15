# Windows packaging

`npm run build:installer` creates `artifacts/VisionStudio-Setup.exe` and a SHA-256 sidecar. The English-only NSIS installer targets Windows x64 and installs for all users in `C:\Program Files\VisionStudio`. It requires administrator access and creates desktop and Start menu shortcuts plus an uninstall entry.

The payload includes the Tauri desktop, embedded React assets, the complete PyInstaller backend folder, and Microsoft's offline WebView2 installer. Initial builds download WebView2 and NSIS tooling; installation does not need those downloads. Python, Node.js, npm, pip, Rust, and CUDA tooling are not end-user prerequisites. No AI libraries are included through Phase 4.

Writable files belong to `%LOCALAPPDATA%\VisionStudio`, including `data`, `projects`, `logs`, and `webview`. Uninstall removes application files and shortcuts while retaining runtime data. Do not add cleanup hooks that remove this data.

## Developer-host QA

```powershell
npm run build:installer
npm run test:desktop -- --release
npm run test:desktop -- --release --missing-backend
npm run test:desktop -- --release --crash
npm run build:installer:qa
npm run test:installer
```

The QA config creates **Vision Studio QA**, a separate current-user installer containing the existing release executable and runtime resources. It allows an install/launch/uninstall check without elevation. It is not the production installer and does not verify `Program Files` permissions or a clean machine. Build the release first; the QA bundling command does not rebuild source code.

The QA script refuses to overwrite an existing QA installation or desktop shortcut. Its report is `artifacts/installer-qa-report.json`; it explicitly records that production per-machine and clean-machine gates are not verified. Native tests use a local WebView2 debugging port only in the test process.

## Pending clean-Windows acceptance

A clean PC/VM is not currently available; the user requested recording this gate as pending and authorized implementation through Phase 4. Elevated production installation also remains unverified on this host.

On a fresh Windows 10/11 x64 PC/VM without development tools or WebView2:

1. Transfer `VisionStudio-Setup.exe` and its matching checksum, then disconnect external networking while retaining loopback.
2. Run the installer, approve Windows elevation, and confirm English installer screens and default `C:\Program Files\VisionStudio` destination.
3. Launch from the desktop shortcut. Confirm no terminal appears and the dashboard reports **Backend Connected**.
4. Visit every navigation page. In Settings, verify the English language, version, OS, processor, and `%LOCALAPPDATA%\VisionStudio` data location. Open the data and logs folders.
5. Close and reopen the application. Confirm the prior backend exits and the next launch connects successfully.
6. Place a recognizable test file in the application data folder. Uninstall from Windows Settings. Confirm application files, shortcuts, and uninstall entry are removed while that file remains.
7. Retain installer checksum, Windows/WebView2 versions, screenshots, logs, and results. Record offline WebView2 installation and elevated install/uninstall separately from developer-host QA.

For the independent Phase 1 backend kit, see [backend QA instructions](backend-poc-README.md). The portable desktop folder described in [desktop instructions](desktop-README.md) requires an existing WebView2 runtime.
