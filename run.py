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

import flet as ft
from src.main import main

if __name__ == "__main__":
    ft.run(main)
