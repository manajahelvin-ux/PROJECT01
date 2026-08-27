# -*- mode: python ; coding: utf-8 -*-
"""Specification PyInstaller de TRANSCRIBE AI (Phase 15).

Build Windows :
    .venv\\Scripts\\python.exe -m PyInstaller TranscribeAI.spec --noconfirm --clean
Sortie :
    dist/TranscribeAI.exe

Le binaire ffmpeg fourni par imageio-ffmpeg est embarque lorsqu'il est
disponible : l'application reste utilisable sur un poste ou FFmpeg n'est
pas installe.
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

block_cipher = None

# --- Donnees embarquees ----------------------------------------------------
datas = [
    ("transcribe_ai/resources", "transcribe_ai/resources"),
    (".env.example", "."),
]
datas += collect_data_files("yt_dlp")

# --- Binaires --------------------------------------------------------------
binaries = []
try:  # FFmpeg embarque : evite l'erreur la plus frequente au premier lancement
    import imageio_ffmpeg

    ffmpeg_exe = Path(imageio_ffmpeg.get_ffmpeg_exe())
    if ffmpeg_exe.exists():
        binaries.append((str(ffmpeg_exe), "imageio_ffmpeg/binaries"))
except Exception:  # noqa: BLE001 - dependance optionnelle
    pass

try:  # bibliotheques natives du moteur de transcription
    binaries += collect_dynamic_libs("ctranslate2")
except Exception:  # noqa: BLE001
    pass

# --- Imports non detectables statiquement ----------------------------------
hiddenimports = [
    *collect_submodules("transcribe_ai"),
    "sqlalchemy.dialects.sqlite",
    "docx",
    "httpx",
    "yt_dlp",
]
for optional in ("faster_whisper", "ctranslate2", "tokenizers", "onnxruntime"):
    try:
        hiddenimports += collect_submodules(optional)
        datas += collect_data_files(optional)
    except Exception:  # noqa: BLE001 - moteur optionnel
        pass

a = Analysis(
    ["transcribe_ai/main.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "pytest", "respx", "black", "ruff", "mypy", "tkinter",
        "matplotlib", "PyQt5", "PyQt6", "PySide2",
    ],
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
    upx_exclude=["vcruntime140.dll", "python3*.dll", "Qt6*.dll"],
    console=False,          # application graphique : aucune console Windows
    disable_windowed_traceback=False,
    icon="transcribe_ai/resources/icons/app.ico",
)
