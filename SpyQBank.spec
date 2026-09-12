import os
from PyInstaller.building.api import Splash

block_cipher = None

datas_list = []
if os.path.exists('assets'):
    datas_list.append(('assets', 'assets'))
if os.path.exists('data'):
    datas_list.append(('data', 'data'))

a = Analysis(
    ['run.py'],
    pathex=['.'],
    binaries=[],
    datas=datas_list,
    hiddenimports=[
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
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
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

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe_args = [
    pyz,
    a.scripts,
]
if splash:
    exe_args.extend([splash, splash.binaries])

exe_args.extend([
    a.binaries,
    a.zipfiles,
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
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file,
)
