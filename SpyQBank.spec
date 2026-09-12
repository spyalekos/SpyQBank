# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('assets', 'assets'), ('data', 'data')]
binaries = []
hiddenimports = ['requests', 'pypdf', 'reportlab']

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
    pathex=[],
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
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
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
    icon=['assets/icon.ico'],
)
