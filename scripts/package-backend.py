"""Create a portable QA archive without PowerShell's nested-ZIP file locking."""

from pathlib import Path
import time
import zipfile

artifacts = Path(__file__).resolve().parent.parent / "artifacts"
archive = artifacts / "VisionStudio-Backend-0.1.0-windows-x64.zip"
temporary = archive.with_suffix(".zip.tmp")
files = sorted(path for path in (artifacts / "backend").rglob("*") if path.is_file())
files.extend(artifacts / name for name in ("README.md", "Test-Backend.ps1", "backend-manifest.json"))
files.extend(sorted((artifacts / "qa-images").glob("sample.*")))

for attempt in range(3):
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for path in files:
                bundle.write(path, path.relative_to(artifacts).as_posix())
        with zipfile.ZipFile(temporary) as bundle:
            if bundle.testzip() is not None:
                raise RuntimeError("Backend archive integrity validation failed.")
        temporary.replace(archive)
        break
    except PermissionError:
        if attempt == 2:
            raise
        time.sleep(1)
