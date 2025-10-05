# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

block_cipher = None

# Collect all vdf module files
vdf_datas, vdf_binaries, vdf_hiddenimports = collect_all('vdf')

a = Analysis(
    ['nak_backend_simple.py'],
    pathex=[],
    binaries=vdf_binaries,
    datas=[('src', 'src')] + vdf_datas,  # Include the src directory and vdf data files
    hiddenimports=[
        'requests',
        'PIL',
        'psutil',
        'py7zr',
        'vdf',
        'json',
        'argparse',
        'pathlib',
        'src.utils.game_finder',
        'src.utils.steam_utils',
        'src.utils.steam_shortcut_manager',
        'src.utils.heroic_utils',
        'src.utils.settings_manager',
        'src.utils.logger',
        'src.utils.prefix_locator',
        'src.utils.smart_prefix_manager',
        'src.utils.comprehensive_game_manager',
        'src.utils.dependency_cache_manager',
    ] + vdf_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PySide6',
        'PyQt5',
        'PyQt6',
        'tkinter',
        'matplotlib',
        'numpy',
        'scipy',
        'pandas',
        'tensorflow',
        'torch',
        'jupyter',
        'notebook',
        'IPython'
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='nak_backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
