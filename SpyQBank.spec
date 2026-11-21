# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.building.api import Splash

datas = []
if os.path.exists("assets"):
    datas.append(("assets", "assets"))
if os.path.exists("data/school_tree.json"):
    datas.append(("data/school_tree.json", "data"))
if os.path.exists("data/cache"):
    datas.append(("data/cache", "data/cache"))

# Targeted Flet runtime data only (icons JSON — NO .pyi stubs or CLI bloat)
datas += collect_data_files("flet", includes=["**/*.json"])

binaries = []
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
    "PIL.Image",
    "PIL.PngImagePlugin",
    "PIL.JpegImagePlugin",
    "PIL.IcoImagePlugin",
    "PIL.BmpImagePlugin",
]

excludes = [
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
    "tkinter",
    "_tkinter",
    "pygments",
    "markdown_it",
    "mdurl",
    "oauthlib",
    "flet.cli",
    "flet.testing",
    "flet.pytest_plugin",
    "flet.auth",
    "flet.canvas",
    "flet.utils.griffe_deprecations",
    "PIL.AvifImagePlugin",
    "PIL.WebPImagePlugin",
    "PIL.ImageFont",
    "PIL.ImageCms",
    "PIL.SpiderImagePlugin",
]

a = Analysis(
    ["run.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

# Drop unused heavy Pillow C-extensions AND root-level duplicate Flutter DLLs
# (keep the single complete copy inside flet_desktop/app/flet/ for 100% offline standalone .exe!)
_DROP_PIL_SUBSTRINGS = ("_avif", "_imagingft", "_webp", "_imagingcms")
_DUP_FLUTTER_SUBSTRINGS = (
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


def _keep_binary(entry):
    dest_norm = entry[0].replace("\\", "/").lower()
    if any(sub in dest_norm for sub in _DROP_PIL_SUBSTRINGS):
        return False
    # Keep bundled Flet client files under flet_desktop/app/, drop root-level duplicates
    if not dest_norm.startswith("flet_desktop/app/") and any(
        sub in dest_norm for sub in _DUP_FLUTTER_SUBSTRINGS
    ):
        return False
    return True


a.binaries = [item for item in a.binaries if _keep_binary(item)]

splash = None
if sys.platform == "win32":
    if os.path.exists("assets/splash.png"):
        splash = Splash(
            "assets/splash.png",
            binaries=a.binaries,
            datas=a.datas,
            text_pos=None,
            text_size=12,
            minify_script=True,
            always_on_top=True,
        )
    elif os.path.exists("assets/splash.jpg"):
        splash = Splash(
            "assets/splash.jpg",
            binaries=a.binaries,
            datas=a.datas,
            text_pos=None,
            text_size=12,
            minify_script=True,
            always_on_top=True,
        )

pyz = PYZ(a.pure)

exe_args = [
    pyz,
    a.scripts,
]
if splash:
    exe_args.extend([splash, splash.binaries])

exe_args.extend([
    a.binaries,
    a.datas,
    [],
])

icon_file = "assets/icon.ico" if os.path.exists("assets/icon.ico") else None

exe = EXE(
    *exe_args,
    name="SpyQBank",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file,
)
