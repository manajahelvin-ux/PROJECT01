"""Modeles de domaine partages par toutes les couches.

Ces dataclasses constituent le contrat stable entre les phases :
telechargement -> audio -> transcription -> IA -> export -> historique.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any


class SourceType(StrEnum):
    URL = "url"
    LOCAL_FILE = "local_file"


class JobStatus(StrEnum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    DOWNLOADING = "downloading"
    EXTRACTING = "extracting"
    TRANSCRIBING = "transcribing"
    AI_PROCESSING = "ai_processing"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PipelineStage(StrEnum):
    """Les 6 etapes affichees dans la barre de progression de l'UI."""

    ANALYZE = "analyze"
    DOWNLOAD = "download"
    EXTRACT_AUDIO = "extract_audio"
    TRANSCRIBE = "transcribe"
    AI_PROCESS = "ai_process"
    FINALIZE = "finalize"


STAGE_LABELS: dict[PipelineStage, str] = {
    PipelineStage.ANALYZE: "Analyse URL",
    PipelineStage.DOWNLOAD: "Telechargement",
    PipelineStage.EXTRACT_AUDIO: "Extraction audio",
    PipelineStage.TRANSCRIBE: "Transcription",
    PipelineStage.AI_PROCESS: "Traitement IA",
    PipelineStage.FINALIZE: "Finalisation",
}


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class MediaInfo:
    """Metadonnees d'une source, produites par l'analyse (yt-dlp ou ffprobe)."""

    title: str
    source: str
    source_type: SourceType
    duration: float = 0.0            # secondes
    author: str | None = None
    language: str | None = None
    thumbnail_url: str | None = None
    extractor: str | None = None
    filesize: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_hms(self) -> str:
        total = int(max(self.duration, 0))
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"


@dataclass(slots=True)
class TranscriptSegment:
    """Segment horodate : brique de base des exports SRT et VTT."""

    index: int
    start: float
    end: float
    text: str
    speaker: str | None = None
    confidence: float | None = None

    @property
    def duration(self) -> float:
        return max(self.end - self.start, 0.0)


@dataclass(slots=True)
class TranscriptionResult:
    """Sortie normalisee de tout `TranscriptionEngine`."""

    text: str
    segments: list[TranscriptSegment] = field(default_factory=list)
    language: str = "auto"
    duration: float = 0.0
    engine: str = ""
    model: str = ""
    created_at: datetime = field(default_factory=_utcnow)

    @property
    def word_count(self) -> int:
        return len(self.text.split())


@dataclass(slots=True)
class Chunk:
    """Bloc de texte envoye a l'IA. `index` garantit l'ordre a la recomposition."""

    index: int
    text: str
    start_char: int = 0
    end_char: int = 0
    token_estimate: int = 0
    fingerprint: str = ""   # hash du contenu : cle du cache anti-retraitement


@dataclass(slots=True)
class AIUsage:
    """Comptabilite des appels IA, affichee dans l'UI (couts et volumetrie)."""

    calls: int = 0
    cached_chunks: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def merge(self, other: AIUsage) -> AIUsage:
        return AIUsage(
            calls=self.calls + other.calls,
            cached_chunks=self.cached_chunks + other.cached_chunks,
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
        )


@dataclass(slots=True)
class AIResult:
    """Resultat consolide du traitement IA d'une transcription."""

    cleaned_text: str = ""
    short_summary: str = ""
    detailed_summary: str = ""
    key_points: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    usage: AIUsage = field(default_factory=AIUsage)
    model: str = ""


@dataclass(slots=True)
class ProgressEvent:
    """Evenement de progression emis par le pipeline vers l'UI (thread-safe)."""

    stage: PipelineStage
    percent: float = 0.0            # 0..100 pour l'etape courante
    message: str = ""
    done: bool = False

    @property
    def label(self) -> str:
        return STAGE_LABELS[self.stage]


@dataclass(slots=True)
class TranscriptionJob:
    """Unite de travail du pipeline, egalement utilisee par le mode lot."""

    source: str
    source_type: SourceType
    language: str = "auto"
    ai_mode: str = "clean"
    status: JobStatus = JobStatus.PENDING
    media_info: MediaInfo | None = None
    media_path: Path | None = None
    audio_path: Path | None = None
    transcription: TranscriptionResult | None = None
    ai_result: AIResult | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=_utcnow)
    record_id: int | None = None

    @property
    def title(self) -> str:
        if self.media_info and self.media_info.title:
            return self.media_info.title
        return Path(self.source).name if self.source_type is SourceType.LOCAL_FILE else self.source

    @property
    def is_terminal(self) -> bool:
        return self.status in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}
