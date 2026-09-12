# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_all
from PyInstaller.building.api import Splash

datas = []
if os.path.exists('assets'):
    datas.append(('assets', 'assets'))
if os.path.exists('data'):
    datas.append(('data', 'data'))

binaries = []
hiddenimports = [
    'src',
    'src.version',
    'src.models',
    'src.iep_api',
    'src.storage',
    'src.pdf_builder',
    'src.config',
    'src.ui',
    'src.ui.theme',
    'src.ui.log_console',
    'src.ui.question_card',
    'src.ui.settings_dialog',
    'src.main',
    'flet',
    'flet_desktop',
    'requests',
    'pypdf',
    'reportlab',
]

flet_datas, flet_binaries, flet_hiddenimports = collect_all('flet')
datas += flet_datas
binaries += flet_binaries
hiddenimports += flet_hiddenimports

flet_desktop_datas, flet_desktop_binaries, flet_desktop_hiddenimports = collect_all('flet_desktop')
datas += flet_desktop_datas
binaries += flet_desktop_binaries
hiddenimports += flet_desktop_hiddenimports

a = Analysis(
    ['run.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

splash = None
if os.path.exists('assets/splash.png'):
    splash = Splash(
        'assets/splash.png',
        binaries=a.binaries,
        datas=a.datas,
        text_pos=None,
        text_size=12,
        minify_script=True,
        always_on_top=True,
    )
elif os.path.exists('assets/splash.jpg'):
    splash = Splash(
        'assets/splash.jpg',
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

icon_file = 'assets/icon.ico' if os.path.exists('assets/icon.ico') else None

exe = EXE(
    *exe_args,
    name='SpyQBank',
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
