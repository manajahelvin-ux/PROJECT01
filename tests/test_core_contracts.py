"""Phase 1 - tests des contrats de domaine (modeles, interfaces, exceptions)."""

from __future__ import annotations

import inspect

import pytest

from transcribe_ai.core import exceptions as exc
from transcribe_ai.core.interfaces import (
    AIProcessor,
    AudioExtractor,
    Exporter,
    MediaProvider,
    OpenRouterProcessor,
    TextChunker,
    TranscriptionEngine,
    WhisperTranscriptionEngine,
)
from transcribe_ai.core.models import (
    AIUsage,
    JobStatus,
    MediaInfo,
    PipelineStage,
    ProgressEvent,
    SourceType,
    TranscriptionJob,
    TranscriptionResult,
    TranscriptSegment,
)


class TestModels:
    def test_duree_formatee(self) -> None:
        info = MediaInfo(
            title="Demo", source="https://x", source_type=SourceType.URL, duration=3725
        )
        assert info.duration_hms == "01:02:05"

    def test_comptage_de_mots(self) -> None:
        result = TranscriptionResult(text="bonjour tout le monde")
        assert result.word_count == 4

    def test_duree_de_segment(self) -> None:
        seg = TranscriptSegment(index=0, start=1.5, end=4.0, text="salut")
        assert seg.duration == pytest.approx(2.5)

    def test_fusion_des_compteurs_ia(self) -> None:
        total = AIUsage(calls=2, prompt_tokens=100).merge(
            AIUsage(calls=3, cached_chunks=1, completion_tokens=50)
        )
        assert (total.calls, total.cached_chunks, total.total_tokens) == (5, 1, 150)

    def test_titre_de_job_depuis_le_fichier_local(self) -> None:
        job = TranscriptionJob(source="/videos/reunion.mp4", source_type=SourceType.LOCAL_FILE)
        assert job.title == "reunion.mp4"

    def test_statut_terminal(self) -> None:
        job = TranscriptionJob(source="https://x", source_type=SourceType.URL)
        assert not job.is_terminal
        job.status = JobStatus.COMPLETED
        assert job.is_terminal

    def test_six_etapes_de_pipeline_etiquetees(self) -> None:
        assert len(list(PipelineStage)) == 6
        for stage in PipelineStage:
            assert ProgressEvent(stage=stage).label


class TestInterfaces:
    @pytest.mark.parametrize(
        "cls",
        [MediaProvider, AudioExtractor, TranscriptionEngine, AIProcessor, TextChunker, Exporter],
    )
    def test_les_interfaces_sont_abstraites(self, cls: type) -> None:
        assert inspect.isabstract(cls)
        with pytest.raises(TypeError):
            cls()  # type: ignore[abstract]

    def test_separation_transcription_intelligence(self) -> None:
        """Whisper et OpenRouter appartiennent a deux hierarchies distinctes."""
        assert issubclass(WhisperTranscriptionEngine, TranscriptionEngine)
        assert issubclass(OpenRouterProcessor, AIProcessor)
        assert not issubclass(OpenRouterProcessor, TranscriptionEngine)

    def test_un_moteur_personnalise_satisfait_le_contrat(self) -> None:
        from pathlib import Path

        class DummyEngine(TranscriptionEngine):
            name = "dummy"

            def is_available(self) -> bool:
                return True

            def transcribe(self, audio_path, language="auto", progress=None, cancel=None):
                return TranscriptionResult(text="ok", engine=self.name)

        engine = DummyEngine()
        assert engine.is_available()
        assert engine.transcribe(Path("a.wav")).text == "ok"


class TestExceptions:
    def test_toutes_derivent_de_la_base(self) -> None:
        for name, obj in vars(exc).items():
            if inspect.isclass(obj) and issubclass(obj, Exception) and not name.startswith("_"):
                assert issubclass(obj, exc.TranscribeAIError), name

    def test_message_utilisateur_par_defaut(self) -> None:
        assert "OpenRouter" in exc.MissingAPIKeyError().user_message

    def test_code_http_conserve(self) -> None:
        err = exc.RateLimitError("429 rate limited", status_code=429)
        assert err.status_code == 429
        assert "429" in err.user_message
