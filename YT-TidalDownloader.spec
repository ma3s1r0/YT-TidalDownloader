# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['tidal_downloader_gui.py'],
    pathex=[],
    binaries=[],
    datas=[('.env', '.'), ('C:\\Users\\lubel\\AppData\\Local\\Temp\\qtbase.qm', 'PyQt5/Qt5/translations/qtbase.qm')],
    hiddenimports=[],
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
    name='YT-TidalDownloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
