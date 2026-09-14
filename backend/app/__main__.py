import argparse
import logging
from logging.handlers import RotatingFileHandler

import uvicorn

from app.paths import initialize_storage


def main():
    parser = argparse.ArgumentParser(description="Vision Studio local backend")
    parser.add_argument("--port", type=int, default=8765)
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
    uvicorn.run("app.main:app", host="127.0.0.1", port=args.port, log_config=None)


if __name__ == "__main__":
    main()
