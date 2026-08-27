# -*- mode: python ; coding: utf-8 -*-
"""Specification PyInstaller de TRANSCRIBE AI.

Squelette pose en Phase 1, finalise en Phase 15 (icone, binaire FFmpeg
embarque, exclusion des dependances de developpement).

Build : .venv\\Scripts\\python.exe -m PyInstaller TranscribeAI.spec --noconfirm --clean
Sortie : dist/TranscribeAI.exe
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

datas = [
    ("transcribe_ai/resources", "transcribe_ai/resources"),
    (".env.example", "."),
]
datas += collect_data_files("yt_dlp")

hiddenimports = [
    "transcribe_ai",
    *collect_submodules("transcribe_ai"),
]

a = Analysis(
    ["transcribe_ai/main.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["pytest", "black", "ruff", "mypy", "tkinter"],
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
    name="TranscribeAI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # application graphique : pas de console Windows
    disable_windowed_traceback=False,
    icon="transcribe_ai/resources/icons/app.ico",
)
