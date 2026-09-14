# Windows packaging strategy

Phase 1 will freeze the minimal FastAPI backend with PyInstaller in one-directory mode. Phase 2 will bundle and supervise it from Tauri. Phase 3 will produce an NSIS installer and verify install, launch, shutdown, and uninstall on clean Windows.

The final installation target is `C:\Program Files\VisionStudio`; writable data belongs to `%LOCALAPPDATA%\VisionStudio`. Include an offline WebView2 installation strategy in Phase 3, so the installer does not depend on downloading a runtime during installation.

End users must not install Python, Node.js, npm, pip, Rust, or the CUDA toolkit. GPU hardware and a compatible driver remain external prerequisites for GPU acceleration; CPU fallback is required. Heavy AI libraries and a bundled base model arrive in Phases 15 and 16.

The Phase 0 desktop build still uses the development Python virtual environment. It is not a distributable or self-contained executable.
