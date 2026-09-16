import argparse
import ctypes
import logging
import msvcrt
import os
import sys
import threading
import time
from ctypes import wintypes
from logging.handlers import RotatingFileHandler

import uvicorn

from app.paths import initialize_storage
from app import training_worker


def wait_for_parent_pipe_close() -> None:
    """Wait for the desktop's stdin pipe without holding the Python GIL."""
    if sys.platform != "win32":
        while os.read(sys.stdin.fileno(), 1024):
            pass
        return

    peek_named_pipe = ctypes.WinDLL("kernel32", use_last_error=True).PeekNamedPipe
    peek_named_pipe.argtypes = [
        wintypes.HANDLE,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
        wintypes.LPVOID,
    ]
    peek_named_pipe.restype = wintypes.BOOL
    handle = wintypes.HANDLE(msvcrt.get_osfhandle(sys.stdin.fileno()))
    bytes_available = wintypes.DWORD()
    while peek_named_pipe(handle, None, 0, None, ctypes.byref(bytes_available), None):
        if bytes_available.value:
            os.read(sys.stdin.fileno(), min(bytes_available.value, 1024))
        time.sleep(0.1)


def _configure_logging(root, filename: str) -> None:
    handler = RotatingFileHandler(
        root / "logs" / filename, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler])


def main() -> int:
    parser = argparse.ArgumentParser(description="Vision Studio local backend")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--parent-watch", action="store_true", help="Stop when the desktop closes its input pipe.")
    parser.add_argument(
        "--training-worker",
        metavar="JOB_ID",
        help="Run one claimed training job in a separate worker process.",
    )
    args = parser.parse_args()
    if args.training_worker:
        root = initialize_storage()
        _configure_logging(root, "training-worker.log")
        return training_worker.run_training_job(args.training_worker, root)
    if not 1 <= args.port <= 65535:
        parser.error("Port must be between 1 and 65535.")
    root = initialize_storage()
    _configure_logging(root, "backend.log")
    logging.info("Starting Vision Studio backend on port %s", args.port)
    # Explicit implementations make the executable independent of optional
    # event loops, HTTP parsers, and WebSocket packages on a developer machine.
    server = uvicorn.Server(uvicorn.Config(
        "app.main:app", host="127.0.0.1", port=args.port, log_config=None,
        loop="asyncio", http="h11", ws="none", lifespan="on",
    ))
    if args.parent_watch:
        def watch_parent():
            # The desktop owns the write end. EOF also handles the Windows
            # virtual-environment redirector without leaving its child orphaned.
            try:
                wait_for_parent_pipe_close()
            except OSError:
                pass
            server.should_exit = True

        threading.Thread(target=watch_parent, daemon=True, name="desktop-lifetime").start()
    server.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
