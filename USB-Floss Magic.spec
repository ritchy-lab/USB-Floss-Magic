# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['usb-floss-magic.py'],
    pathex=[],
    binaries=[],
    datas=[('logo.png', '.'), ('background.png', '.'), ('button_idle.png', '.'), ('button_active.png', '.'), ('button_processing.png', '.'), ('popup_success.png', '.'), ('popup_warning.png', '.'), ('popup_error.png', '.')],
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
    [],
    exclude_binaries=True,
    name='USB-Floss Magic',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icon.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='USB-Floss Magic',
)
app = BUNDLE(
    coll,
    name='USB-Floss Magic.app',
    icon='icon.icns',
    bundle_identifier=None,
)
