"""Diagnostic de l'environnement d'execution.

Utilise par `python -m transcribe_ai.main --doctor` et, en Phase 13,
par la page Parametres pour signaler visuellement les dependances
manquantes (FFmpeg, yt-dlp, moteur Whisper, cle API...).
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

from transcribe_ai.config.settings import Settings


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str
    optional: bool = False


@dataclass
class DiagnosticReport:
    checks: list[Check] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Vrai si toutes les verifications obligatoires sont satisfaites."""
        return all(c.ok for c in self.checks if not c.optional)

    def add(self, check: Check) -> None:
        self.checks.append(check)


def _module_available(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def find_ffmpeg(configured: str = "") -> str | None:
    """Localise FFmpeg : chemin configure, PATH, puis binaire imageio-ffmpeg."""
    if configured and Path(configured).exists():
        return configured
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:  # repli : binaire fourni par imageio-ffmpeg
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def run_diagnostics(settings: Settings) -> DiagnosticReport:
    report = DiagnosticReport()

    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    report.add(
        Check(
            "Python 3.11+",
            sys.version_info >= (3, 11),
            f"version detectee {version}",
        )
    )

    for module, label, optional in (
        ("PySide6", "PySide6 (UI)", False),
        ("yt_dlp", "yt-dlp", False),
        ("httpx", "httpx", False),
        ("docx", "python-docx", False),
        ("sqlalchemy", "SQLAlchemy", False),
        ("dotenv", "python-dotenv", False),
        ("faster_whisper", "faster-whisper", True),
    ):
        available = _module_available(module)
        report.add(
            Check(
                label,
                available,
                "installe" if available else "manquant (pip install -r requirements.txt)",
                optional=optional,
            )
        )

    ffmpeg = find_ffmpeg(settings.ffmpeg_path)
    report.add(
        Check("FFmpeg", ffmpeg is not None, ffmpeg or "introuvable dans le PATH")
    )

    report.add(
        Check(
            "Cle OpenRouter",
            settings.has_api_key,
            settings.masked_api_key if settings.has_api_key else "absente du fichier .env",
            optional=True,
        )
    )

    root = settings.paths.root
    writable = root.exists() and root.is_dir()
    report.add(Check("Dossier de donnees", writable, str(root)))

    return report
