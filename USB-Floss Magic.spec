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
    upx=False,          # UPX n'est pas installé sur macOS (et déconseillé)
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    # None = architecture de la machine. La version universelle (Intel +
    # Apple Silicon) est impossible : Pillow n'existe pas en binaire
    # universel sur PyPI (ses 26 binaires sont mono-architecture).
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
    upx=False,
    upx_exclude=[],
    name='USB-Floss Magic',
)
app = BUNDLE(
    coll,
    name='USB-Floss Magic.app',
    icon='icon.icns',
    bundle_identifier='com.ritchy-lab.usb-floss-magic',
    version='0.7',
    info_plist={
        'CFBundleShortVersionString': '0.7',
        'NSHumanReadableCopyright': '© 2026 ritchy-lab',
        'LSMinimumSystemVersion': '11.0',
    },
)
