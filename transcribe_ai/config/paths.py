"""Resolution centralisee des chemins de l'application.

Toutes les ecritures disque (base SQLite, logs, audio temporaire, exports)
passent par ce module afin que le packaging PyInstaller reste trivial :
le code n'ecrit jamais a cote de l'executable, toujours dans un dossier
utilisateur inscriptible.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

APP_NAME = "TranscribeAI"
APP_AUTHOR = "TranscribeAI"


def is_frozen() -> bool:
    """Vrai lorsque le code s'execute depuis un bundle PyInstaller."""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def bundle_dir() -> Path:
    """Dossier des ressources embarquees (icones, QSS) selon le mode d'execution."""
    if is_frozen():
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[1]


def _default_data_dir() -> Path:
    """Dossier de donnees par defaut, dependant de la plateforme."""
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming"
        return Path(base) / APP_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    base = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(base) / APP_NAME


@dataclass(frozen=True)
class AppPaths:
    """Arborescence de travail de l'application."""

    root: Path

    @property
    def database(self) -> Path:
        return self.root / "transcribe_ai.sqlite3"

    @property
    def logs(self) -> Path:
        return self.root / "logs"

    @property
    def downloads(self) -> Path:
        return self.root / "downloads"

    @property
    def audio(self) -> Path:
        return self.root / "audio"

    @property
    def transcriptions(self) -> Path:
        return self.root / "transcriptions"

    @property
    def exports(self) -> Path:
        return self.root / "exports"

    @property
    def cache(self) -> Path:
        """Cache des chunks IA deja traites (evite de repayer un appel)."""
        return self.root / "cache"

    @property
    def models(self) -> Path:
        return self.root / "models"

    @property
    def resources(self) -> Path:
        return bundle_dir() / "resources"

    def ensure(self) -> AppPaths:
        """Cree l'arborescence si necessaire, puis se retourne."""
        for directory in (
            self.root,
            self.logs,
            self.downloads,
            self.audio,
            self.transcriptions,
            self.exports,
            self.cache,
            self.models,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        return self


def app_paths(data_dir: str | os.PathLike[str] | None = None) -> AppPaths:
    """Construit l'objet `AppPaths`.

    `data_dir` prime, sinon la variable d'environnement DATA_DIR,
    sinon le dossier utilisateur standard de la plateforme.
    """
    candidate = data_dir or os.environ.get("DATA_DIR") or ""
    root = Path(candidate).expanduser() if str(candidate).strip() else _default_data_dir()
    return AppPaths(root=root.resolve())
