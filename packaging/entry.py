"""PyInstaller entry point: the `dayafter` command (no arguments starts the app in the browser)."""
import multiprocessing
import sys

from dayafter.cli import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
