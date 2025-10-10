# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['nak-flet/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('src', 'src'),
    ],
    hiddenimports=[
        'flet',
        'flet_desktop',
        'flet.auth',
        'flet.auth.providers',
        'requests',
        'urllib3',
        'certifi',
        'charset_normalizer',
        'idna',
        'vdf',
        'psutil',
        'py7zr',
        'pillow',
        'PIL',
        'PIL.Image',
        'logging',
        'logging.handlers',
        'logging.config',
        'src.core.core',
        'src.core.mo2_installer',
        'src.core.dependency_installer',
        'src.utils.steam_utils',
        'src.utils.game_utils',
        'src.utils.game_finder',
        'src.utils.steam_shortcut_manager',
        'src.utils.comprehensive_game_manager',
        'src.utils.smart_prefix_manager',
        'src.utils.prefix_locator',
        'src.utils.heroic_utils',
        'src.utils.settings_manager',
        'src.utils.logger',
        'src.utils.proton_tool_manager',
        'src.utils.dependency_cache_manager',
        'src.utils.utils',
        'src.utils.command_cache',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'libstdc++.so.6',
        'libgcc_s.so.1',
        'libssl.so.3',
        'libcrypto.so.3',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Exclude problematic system libraries that conflict with newer systems
a.binaries = [x for x in a.binaries if not any(lib in x[0] for lib in [
    'libstdc++.so.6',
    'libgcc_s.so.1',
    'libssl.so.3',
    'libcrypto.so.3',
])]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='nak-modding-helper',
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
