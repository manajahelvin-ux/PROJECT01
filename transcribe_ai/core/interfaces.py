"""Interfaces abstraites : coeur de la modularite de TRANSCRIBE AI.

La transcription (locale) et l'intelligence (OpenRouter) sont deux
responsabilites strictement separees. Remplacer Whisper par un autre
moteur, ou OpenRouter par un autre fournisseur, revient a fournir une
nouvelle implementation de ces classes et a l'enregistrer dans le
registre correspondant : aucun autre code n'est a modifier.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Protocol

from transcribe_ai.core.models import (
    AIResult,
    Chunk,
    MediaInfo,
    ProgressEvent,
    TranscriptionResult,
)

#: Callback de progression ; toute implementation doit tolerer `None`.
ProgressCallback = Callable[[ProgressEvent], None]


class CancellationToken(Protocol):
    """Permet a l'UI d'interrompre proprement une operation longue."""

    def is_cancelled(self) -> bool: ...


# --------------------------------------------------------------------------- #
# Acquisition media
# --------------------------------------------------------------------------- #
class MediaProvider(ABC):
    """Fournit metadonnees et fichier media a partir d'une source."""

    name: str = "base"

    @abstractmethod
    def supports(self, source: str) -> bool:
        """Vrai si ce fournisseur sait traiter la source (URL ou chemin)."""

    @abstractmethod
    def analyze(self, source: str) -> MediaInfo:
        """Retourne les metadonnees sans telecharger le contenu complet."""

    @abstractmethod
    def fetch(
        self,
        source: str,
        destination: Path,
        progress: ProgressCallback | None = None,
        cancel: CancellationToken | None = None,
    ) -> Path:
        """Rend disponible localement le media et retourne son chemin."""


class AudioExtractor(ABC):
    """Convertit n'importe quel media en WAV 16 kHz mono, entree du moteur STT."""

    @abstractmethod
    def extract(
        self,
        media_path: Path,
        destination: Path,
        progress: ProgressCallback | None = None,
        cancel: CancellationToken | None = None,
    ) -> Path: ...

    @abstractmethod
    def probe_duration(self, media_path: Path) -> float: ...


# --------------------------------------------------------------------------- #
# Transcription
# --------------------------------------------------------------------------- #
class TranscriptionEngine(ABC):
    """Contrat de tout moteur de transcription (Whisper ou autre)."""

    name: str = "base"

    @abstractmethod
    def is_available(self) -> bool:
        """Vrai si les dependances/modeles requis sont installes."""

    @abstractmethod
    def transcribe(
        self,
        audio_path: Path,
        language: str = "auto",
        progress: ProgressCallback | None = None,
        cancel: CancellationToken | None = None,
    ) -> TranscriptionResult: ...


class WhisperTranscriptionEngine(TranscriptionEngine):
    """Base commune aux implementations Whisper (Phase 5)."""

    name = "whisper"

    def is_available(self) -> bool:  # pragma: no cover - implemente en Phase 5
        raise NotImplementedError

    def transcribe(  # pragma: no cover - implemente en Phase 5
        self,
        audio_path: Path,
        language: str = "auto",
        progress: ProgressCallback | None = None,
        cancel: CancellationToken | None = None,
    ) -> TranscriptionResult:
        raise NotImplementedError


# --------------------------------------------------------------------------- #
# Intelligence artificielle
# --------------------------------------------------------------------------- #
class TextChunker(ABC):
    """Decoupe une transcription en blocs ordonnes envoyables a l'IA."""

    @abstractmethod
    def split(self, text: str) -> list[Chunk]: ...

    @abstractmethod
    def merge(self, pieces: Iterable[str]) -> str: ...


class AIProcessor(ABC):
    """Contrat de tout fournisseur d'intelligence (post-transcription)."""

    name: str = "base"

    @abstractmethod
    def is_configured(self) -> bool: ...

    @abstractmethod
    def test_connection(self) -> tuple[bool, str]:
        """Retourne (succes, message affichable) pour le bouton de test."""

    @abstractmethod
    def clean(
        self,
        text: str,
        language: str = "auto",
        progress: ProgressCallback | None = None,
        cancel: CancellationToken | None = None,
    ) -> AIResult: ...

    @abstractmethod
    def summarize(self, text: str, language: str = "auto") -> AIResult: ...

    @abstractmethod
    def key_points(self, text: str, language: str = "auto") -> AIResult: ...

    @abstractmethod
    def translate(self, text: str, target_language: str) -> AIResult: ...


class OpenRouterProcessor(AIProcessor):
    """Base de l'implementation OpenRouter (Phase 6)."""

    name = "openrouter"


# --------------------------------------------------------------------------- #
# Export
# --------------------------------------------------------------------------- #
class Exporter(ABC):
    """Contrat d'un format d'export (TXT, DOCX, SRT, VTT)."""

    extension: str = ""
    label: str = ""

    @abstractmethod
    def export(self, job_data: object, destination: Path) -> Path: ...
