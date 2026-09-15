"""Executable entry point, shared with the development backend."""

from multiprocessing import freeze_support

from app.__main__ import main


if __name__ == "__main__":
    freeze_support()
    main()
