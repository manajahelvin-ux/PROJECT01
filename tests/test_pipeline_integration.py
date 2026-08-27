"""Test d'integration du pipeline complet, sans reseau ni modele lourd.

Le chemin URL → audio → transcription → IA → texte est exerce de bout en
bout avec un moteur factice et un processeur IA double.
"""

from __future__ import annotations

import wave
from pathlib import Path

import pytest

from transcribe_ai.config.settings import AIMode, Settings
from transcribe_ai.core.ai.processor import OpenRouterProcessor
from transcribe_ai.core.engines.whisper_engine import (
    MockTranscriptionEngine,
    available_engines,
    create_engine,
)
from transcribe_ai.core.exceptions import EngineNotAvailableError, TranscribeAIError
from transcribe_ai.core.models import AIResult, AIUsage, JobStatus, PipelineStage, SourceType
from transcribe_ai.core.pipeline.audio import find_ffmpeg
from transcribe_ai.core.pipeline.orchestrator import TranscriptionPipeline
from transcribe_ai.io.database import Database, HistoryRepository
from transcribe_ai.io.exporters import ExportPayload, export_transcription
from transcribe_ai.utils.cancellation import CancelToken

ffmpeg_required = pytest.mark.skipif(find_ffmpeg() is None, reason="FFmpeg absent")


@pytest.fixture
def local_media(tmp_path: Path) -> Path:
    path = tmp_path / "reunion.wav"
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(22050)
        handle.writeframes(b"\x00\x00" * 22050 * 2)
    return path


class FakeProcessor(OpenRouterProcessor):
    """Processeur IA double : aucune requete HTTP, comportement deterministe."""

    def __init__(self) -> None:
        self.calls = 0

    def is_configured(self) -> bool:
        return True

    def process(self, text, mode=AIMode.CLEAN, language="auto", progress=None, cancel=None):
        self.calls += 1
        return AIResult(
            cleaned_text=text.capitalize() + ".",
            short_summary="Un resume.",
            usage=AIUsage(calls=1),
            model="fake/model",
        )


@pytest.fixture
def pipeline(tmp_path: Path) -> TranscriptionPipeline:
    settings = Settings(_env_file=None, data_dir=str(tmp_path / "data"))
    return TranscriptionPipeline(
        engine=MockTranscriptionEngine(), processor=FakeProcessor(), settings=settings
    )


class TestEngineRegistry:
    def test_moteur_factice_disponible(self) -> None:
        assert "mock" in available_engines()

    def test_creation_par_nom(self) -> None:
        assert create_engine("mock").name == "mock"

    def test_moteur_inconnu(self) -> None:
        with pytest.raises(EngineNotAvailableError):
            create_engine("moteur-imaginaire")

    def test_transcription_factice_segmentee(self, tmp_path: Path) -> None:
        result = MockTranscriptionEngine("bonjour tout le monde ici").transcribe(tmp_path / "a.wav")
        assert result.segments and result.word_count == 5
        assert result.segments[0].end > result.segments[0].start


class TestPipelineIntegration:
    def test_creation_de_job_depuis_une_url(self, pipeline: TranscriptionPipeline) -> None:
        job = pipeline.create_job("https://www.youtube.com/watch?v=abc")
        assert job.source_type is SourceType.URL

    def test_creation_de_job_depuis_un_fichier(self, pipeline, local_media: Path) -> None:
        assert pipeline.create_job(str(local_media)).source_type is SourceType.LOCAL_FILE

    @ffmpeg_required
    def test_parcours_complet_fichier_local(self, pipeline, local_media: Path) -> None:
        job = pipeline.create_job(str(local_media), language="fr", ai_mode=AIMode.CLEAN)
        events = []
        pipeline.run(job, progress=events.append)

        assert job.status is JobStatus.COMPLETED
        assert job.audio_path.exists()
        assert job.transcription.word_count > 0
        assert job.ai_result.cleaned_text.endswith(".")
        # Les 6 etapes ont bien ete parcourues.
        assert {e.stage for e in events} == set(PipelineStage)

    @ffmpeg_required
    def test_audio_intermediaire_au_format_impose(self, pipeline, local_media: Path) -> None:
        job = pipeline.create_job(str(local_media))
        pipeline.run(job)
        with wave.open(str(job.audio_path), "rb") as handle:
            assert handle.getframerate() == 16000 and handle.getnchannels() == 1

    @ffmpeg_required
    def test_mode_sans_ia_najoute_aucun_appel(self, pipeline, local_media: Path) -> None:
        job = pipeline.create_job(str(local_media), ai_mode=AIMode.NONE)
        pipeline.run(job)
        assert job.status is JobStatus.COMPLETED
        assert job.ai_result is None
        assert pipeline.processor.calls == 0

    def test_source_invalide_echoue_proprement(self, pipeline: TranscriptionPipeline) -> None:
        job = pipeline.create_job("source-inexistante")
        with pytest.raises(TranscribeAIError):
            pipeline.run(job)
        assert job.status is JobStatus.FAILED and job.error

    @ffmpeg_required
    def test_annulation_interrompt_le_pipeline(self, pipeline, local_media: Path) -> None:
        token = CancelToken()
        token.cancel()
        job = pipeline.create_job(str(local_media))
        with pytest.raises(TranscribeAIError):
            pipeline.run(job, cancel=token)
        assert job.status is JobStatus.FAILED

    @ffmpeg_required
    def test_chaine_complete_jusqua_lexport_et_lhistorique(
        self, pipeline, local_media: Path, tmp_path: Path
    ) -> None:
        job = pipeline.create_job(str(local_media))
        pipeline.run(job)

        repo = HistoryRepository(Database(f"sqlite:///{tmp_path / 'h.sqlite3'}"))
        record = repo.save_job(job)
        assert record.id and record.word_count > 0

        payload = ExportPayload.from_job(job)
        for fmt in ("txt", "docx", "srt", "vtt"):
            assert export_transcription(payload, tmp_path / f"out.{fmt}").exists()
