"""Root execution entry point for SpyQBank."""

import os
import sys

# Ensure root directory and _MEIPASS are in sys.path
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    base_dir = sys._MEIPASS
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

# Windows Flet Desktop optimizations & bundled MSIX client discovery
if sys.platform == "win32":
    os.environ.setdefault("FLET_NO_IMPELLER", "true")
    if "FLET_VIEW_PATH" not in os.environ:
        exe_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else base_dir
        for candidate in (
            os.path.join(exe_dir, "flet_client"),
            os.path.join(base_dir, "flet_client"),
            os.path.join(base_dir, "flet_desktop", "app", "flet"),
        ):
            if os.path.isfile(os.path.join(candidate, "flet.exe")):
                os.environ["FLET_VIEW_PATH"] = candidate
                break

import flet as ft
from src.main import main

if __name__ == "__main__":
    ft.run(main)
