"""Orchestrateur : enchaine les 6 etapes du pipeline de bout en bout.

C'est le seul composant qui connait l'ordre des operations. L'interface
ne parle qu'a lui, via un callback de progression et un jeton d'annulation.
"""

from __future__ import annotations

from pathlib import Path

from transcribe_ai.config.settings import AIMode, Settings, get_settings
from transcribe_ai.core.ai.processor import OpenRouterProcessor
from transcribe_ai.core.engines.whisper_engine import create_engine
from transcribe_ai.core.exceptions import TranscribeAIError
from transcribe_ai.core.interfaces import (
    AIProcessor,
    AudioExtractor,
    CancellationToken,
    ProgressCallback,
    TranscriptionEngine,
)
from transcribe_ai.core.models import (
    JobStatus,
    MediaInfo,
    PipelineStage,
    ProgressEvent,
    SourceType,
    TranscriptionJob,
)
from transcribe_ai.core.pipeline.audio import FFmpegAudioExtractor
from transcribe_ai.core.pipeline.media import MediaResolver
from transcribe_ai.utils.logging_config import get_logger
from transcribe_ai.utils.text import is_url, slugify

logger = get_logger(__name__)


class TranscriptionPipeline:
    """Assemble acquisition, extraction, transcription et traitement IA."""

    def __init__(
        self,
        resolver: MediaResolver | None = None,
        extractor: AudioExtractor | None = None,
        engine: TranscriptionEngine | None = None,
        processor: AIProcessor | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.resolver = resolver or MediaResolver()
        self.extractor = extractor or FFmpegAudioExtractor()
        self._engine = engine
        self._processor = processor

    @property
    def engine(self) -> TranscriptionEngine:
        """Chargement paresseux : le modele n'est pris en memoire qu'au besoin."""
        if self._engine is None:
            self._engine = create_engine(self.settings.transcription_engine)
        return self._engine

    @property
    def processor(self) -> AIProcessor:
        if self._processor is None:
            self._processor = OpenRouterProcessor(settings=self.settings)
        return self._processor

    # ------------------------------------------------------------------ #
    @staticmethod
    def _emit(progress: ProgressCallback | None, stage: PipelineStage, pct: float, msg: str,
              done: bool = False) -> None:
        if progress is not None:
            progress(ProgressEvent(stage=stage, percent=pct, message=msg, done=done))

    def analyze(self, source: str) -> MediaInfo:
        """Etape 1 : metadonnees, sans telechargement."""
        return self.resolver.analyze(source)

    def create_job(self, source: str, language: str | None = None,
                   ai_mode: AIMode | str | None = None) -> TranscriptionJob:
        """Fabrique un job coherent a partir d'une source brute."""
        source = source.strip()
        source_type = SourceType.URL if is_url(source) else SourceType.LOCAL_FILE
        mode = ai_mode if ai_mode is not None else self.settings.ai_mode
        return TranscriptionJob(
            source=source,
            source_type=source_type,
            language=language or self.settings.default_language,
            ai_mode=AIMode(mode).value if not isinstance(mode, str) else str(AIMode(mode).value),
        )

    # ------------------------------------------------------------------ #
    def run(
        self,
        job: TranscriptionJob,
        progress: ProgressCallback | None = None,
        cancel: CancellationToken | None = None,
    ) -> TranscriptionJob:
        """Execute le pipeline complet et renseigne le job au fil de l'eau."""
        paths = self.settings.paths
        try:
            # 1. Analyse ---------------------------------------------------
            job.status = JobStatus.ANALYZING
            self._emit(progress, PipelineStage.ANALYZE, 10.0, "Analyse de la source…")
            if job.media_info is None:
                job.media_info = self.analyze(job.source)
            self._emit(progress, PipelineStage.ANALYZE, 100.0,
                       f"« {job.media_info.title} »", done=True)
            self._check(cancel)

            # 2. Telechargement / acces au fichier -------------------------
            job.status = JobStatus.DOWNLOADING
            provider = self.resolver.resolve(job.source)
            job.media_path = provider.fetch(job.source, paths.downloads, progress, cancel)
            self._emit(progress, PipelineStage.DOWNLOAD, 100.0, "Media disponible", done=True)
            self._check(cancel)

            # 3. Extraction audio ------------------------------------------
            job.status = JobStatus.EXTRACTING
            audio_name = f"{slugify(job.media_info.title)}-{abs(hash(job.source)) % 10**6}.wav"
            job.audio_path = self.extractor.extract(
                job.media_path, paths.audio / audio_name, progress, cancel
            )
            self._check(cancel)

            # 4. Transcription ---------------------------------------------
            job.status = JobStatus.TRANSCRIBING
            job.transcription = self.engine.transcribe(
                job.audio_path, job.language, progress, cancel
            )
            self._check(cancel)

            # 5. Traitement IA ---------------------------------------------
            job.status = JobStatus.AI_PROCESSING
            mode = AIMode(job.ai_mode)
            if mode is AIMode.NONE or not self.processor.is_configured():
                if mode is not AIMode.NONE:
                    logger.info("Traitement IA ignore : aucune cle API configuree")
                self._emit(progress, PipelineStage.AI_PROCESS, 100.0,
                           "Traitement IA desactive", done=True)
            else:
                job.ai_result = self.processor.process(  # type: ignore[attr-defined]
                    job.transcription.text,
                    mode=mode,
                    language=job.transcription.language,
                    progress=progress,
                    cancel=cancel,
                )
                usage = job.ai_result.usage
                self._emit(
                    progress, PipelineStage.AI_PROCESS, 100.0,
                    f"Appels IA : {usage.calls} — blocs caches : {usage.cached_chunks}",
                    done=True,
                )

            # 6. Finalisation ----------------------------------------------
            job.status = JobStatus.FINALIZING
            self._emit(progress, PipelineStage.FINALIZE, 50.0, "Enregistrement…")
            self._persist_text(job, paths.transcriptions)
            job.status = JobStatus.COMPLETED
            self._emit(progress, PipelineStage.FINALIZE, 100.0, "Termine", done=True)
            logger.info("Job termine : %s", job.title)

        except TranscribeAIError as exc:
            job.status = JobStatus.FAILED
            job.error = exc.user_message
            logger.error("Job en echec (%s) : %s", job.title, exc)
            raise
        except Exception as exc:
            job.status = JobStatus.FAILED
            job.error = str(exc)
            logger.exception("Erreur inattendue dans le pipeline")
            raise TranscribeAIError(str(exc)) from exc
        return job

    @staticmethod
    def _check(cancel: CancellationToken | None) -> None:
        if cancel is not None and cancel.is_cancelled():
            raise TranscribeAIError(
                "Annule", user_message="Traitement annule par l'utilisateur."
            )

    @staticmethod
    def _persist_text(job: TranscriptionJob, directory: Path) -> Path | None:
        """Sauvegarde le texte sur disque : filet de securite hors base."""
        text = (
            job.ai_result.cleaned_text
            if job.ai_result and job.ai_result.cleaned_text
            else (job.transcription.text if job.transcription else "")
        )
        if not text:
            return None
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{slugify(job.title)}-{abs(hash(job.source)) % 10**6}.txt"
        try:
            path.write_text(text, encoding="utf-8")
        except OSError as exc:
            logger.warning("Sauvegarde disque impossible : %s", exc)
            return None
        return path
