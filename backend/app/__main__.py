import argparse
import logging
import sys
import threading
from logging.handlers import RotatingFileHandler

import uvicorn

from app.paths import initialize_storage


def main():
    parser = argparse.ArgumentParser(description="Vision Studio local backend")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--parent-watch", action="store_true", help="Stop when the desktop closes its input pipe.")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Port must be between 1 and 65535.")
    root = initialize_storage()
    handler = RotatingFileHandler(
        root / "logs" / "backend.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler])
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
            sys.stdin.buffer.read()
            server.should_exit = True

        threading.Thread(target=watch_parent, daemon=True, name="desktop-lifetime").start()
    server.run()


if __name__ == "__main__":
    main()
