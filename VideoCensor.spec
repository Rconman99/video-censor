# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Video Censor
Build with: pyinstaller VideoCensor.spec
"""

import sys
from pathlib import Path

block_cipher = None

# Get the project root
project_root = Path(SPECPATH)

a = Analysis(
    ['main.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        # Include the config template
        ('config.yaml.example', '.'),
        # Include UI modules
        ('ui', 'ui'),
        # Include video_censor modules
        ('video_censor', 'video_censor'),
    ],
    hiddenimports=[
        # PySide6 imports
        'PySide6.QtCore',
        'PySide6.QtGui', 
        'PySide6.QtWidgets',
        # Whisper/ML imports
        'faster_whisper',
        'ctranslate2',
        # NudeNet
        'nudenet',
        'onnxruntime',
        # Other dependencies
        'PIL',
        'PIL.Image',
        'numpy',
        'yaml',
        'tqdm',
        'requests',
        'bs4',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',  # Not needed, using PySide6
        'matplotlib',
        'scipy',
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
    [],
    exclude_binaries=True,
    name='VideoCensor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No terminal window
    disable_windowed_traceback=False,
    argv_emulation=True,  # macOS argv emulation
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='VideoCensor',
)

app = BUNDLE(
    coll,
    name='VideoCensor.app',
    icon=None,  # Add icon path here if you have one
    bundle_identifier='com.videocensor.app',
    info_plist={
        'CFBundleName': 'Video Censor',
        'CFBundleDisplayName': 'Video Censor',
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleVersion': '1.0.0',
        'NSHighResolutionCapable': True,
        'NSRequiresAquaSystemAppearance': False,  # Support dark mode
        'LSMinimumSystemVersion': '10.15',
    },
)
