# -*- mode: python ; coding: utf-8 -*-
"""Slimmed PyInstaller onedir spec for SpyQBank MSIX (Microsoft Store)."""
import os
from PyInstaller.utils.hooks import collect_data_files

datas = []
# Only include runtime app icons (MSIX uses its own Assets\SplashScreen.png)
if os.path.exists("assets/icon.png"):
    datas.append(("assets/icon.png", "assets"))
if os.path.exists("assets/icon.ico"):
    datas.append(("assets/icon.ico", "assets"))
if os.path.exists("data/school_tree.json"):
    datas.append(("data/school_tree.json", "data"))
if os.path.exists("data/cache"):
    datas.append(("data/cache", "data/cache"))

# Targeted Flet runtime data only (icons JSON — NO .pyi stubs or CLI bloat)
datas += collect_data_files("flet", includes=["**/*.json"])

hiddenimports = [
    "src",
    "src.version",
    "src.models",
    "src.iep_api",
    "src.storage",
    "src.pdf_builder",
    "src.config",
    "src.ui",
    "src.ui.theme",
    "src.ui.log_console",
    "src.ui.question_card",
    "src.ui.settings_dialog",
    "src.main",
    "flet",
    "flet_desktop",
    "flet_desktop.extensions",
    "flet_desktop.version",
    "flet_desktop.win_taskbar",
    "requests",
    "pypdf",
    "reportlab",
    "reportlab.graphics.barcode",
    "PIL.Image",
    "PIL.PngImagePlugin",
    "PIL.JpegImagePlugin",
    "PIL.IcoImagePlugin",
    "PIL.BmpImagePlugin",
]

excludes = [
    # Dev / Build / Packaging / Test / REPL tools
    "setuptools",
    "pkg_resources",
    "wheel",
    "_distutils_hack",
    "pip",
    "_pyrepl",
    "unittest",
    "doctest",
    "pdb",
    "pydoc",
    "test",
    "watchdog",
    # Unused GUI frameworks
    "tkinter",
    "_tkinter",
    # Heavy transitive CLI/auth deps not used at runtime
    "pygments",
    "markdown_it",
    "mdurl",
    "oauthlib",
    # Unused Flet CLI / Test / Auth / Canvas submodules
    "flet.cli",
    "flet.testing",
    "flet.pytest_plugin",
    "flet.auth",
    "flet.canvas",
    "flet.utils.griffe_deprecations",
    # Unused heavy Pillow plugins
    "PIL.AvifImagePlugin",
    "PIL.WebPImagePlugin",
    "PIL.ImageFont",
    "PIL.ImageCms",
    "PIL.SpiderImagePlugin",
]

a = Analysis(
    ["run.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

# Remove duplicate Flet client files injected by flet_cli's hook-flet.py:
# MSIX bundles ONE clean unpacked copy at root `flet_client/` (via FLET_VIEW_PATH).
a.datas = [
    item for item in a.datas
    if not item[0].replace("\\", "/").startswith("flet_desktop/app")
]

# Drop unused heavy Pillow C-extensions AND duplicate Flutter DLLs leaked from hook-flet.py
_DROP_BIN_SUBSTRINGS = (
    "_avif",
    "_imagingft",
    "_webp",
    "_imagingcms",
    "flet_desktop/app",
    "flet_desktop\\app",
    "libmpv-2",
    "flutter_windows",
    "libegl.dll",
    "libglesv2.dll",
    "d3dcompiler_47",
    "vk_swiftshader",
    "vulkan-1",
    "rive_native",
    "_plugin.dll",
    "dartjni",
    "flutter_local_notifications",
    "flet.exe",
)
a.binaries = [
    item for item in a.binaries
    if not any(sub in item[0].lower() for sub in _DROP_BIN_SUBSTRINGS)
]

pyz = PYZ(a.pure)

icon_file = "assets/icon.ico" if os.path.exists("assets/icon.ico") else None

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SpyQBank",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SpyQBank_msix",
)
