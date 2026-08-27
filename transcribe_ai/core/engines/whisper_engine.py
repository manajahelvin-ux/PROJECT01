"""Phase 5 - moteurs de transcription.

`FasterWhisperEngine` est l'implementation par defaut. `MockEngine` sert
aux tests et aux demonstrations sans modele installe. Le registre permet
d'ajouter un moteur sans toucher au pipeline.
"""

from __future__ import annotations

import wave
from pathlib import Path

from transcribe_ai.config.settings import get_settings
from transcribe_ai.core.exceptions import EngineNotAvailableError, TranscriptionError
from transcribe_ai.core.interfaces import (
    CancellationToken,
    ProgressCallback,
    TranscriptionEngine,
    WhisperTranscriptionEngine,
)
from transcribe_ai.core.models import (
    PipelineStage,
    ProgressEvent,
    TranscriptionResult,
    TranscriptSegment,
)
from transcribe_ai.utils.logging_config import get_logger
from transcribe_ai.utils.text import normalize_whitespace

logger = get_logger(__name__)


def wav_duration(path: Path) -> float:
    """Duree d'un WAV sans dependance externe (le pipeline garantit ce format)."""
    try:
        with wave.open(str(path), "rb") as handle:
            return handle.getnframes() / float(handle.getframerate() or 1)
    except Exception:
        return 0.0


class FasterWhisperEngine(WhisperTranscriptionEngine):
    """Moteur base sur faster-whisper (CTranslate2) : rapide sur CPU."""

    name = "faster-whisper"

    def __init__(
        self,
        model_size: str | None = None,
        device: str | None = None,
        compute_type: str | None = None,
    ) -> None:
        settings = get_settings()
        self.model_size = model_size or settings.whisper_model
        self.device = device or settings.whisper_device
        self.compute_type = compute_type or settings.whisper_compute_type
        self._model = None  # chargement paresseux : demarrage instantane de l'app

    def is_available(self) -> bool:
        try:
            import faster_whisper  # noqa: F401
        except ImportError:
            return False
        return True

    def _load_model(self):
        if self._model is not None:
            return self._model
        if not self.is_available():
            raise EngineNotAvailableError(
                "faster-whisper non installe",
                user_message=(
                    "Le moteur de transcription n'est pas installe. "
                    "Executez : pip install faster-whisper"
                ),
            )
        from faster_whisper import WhisperModel

        device = self.device
        if device == "auto":
            device = "cpu"
            try:  # bascule GPU seulement si CUDA est reellement disponible
                import ctranslate2

                if ctranslate2.get_cuda_device_count() > 0:
                    device = "cuda"
            except Exception:
                pass
        compute = self.compute_type if device == "cpu" else "float16"
        logger.info(
            "Chargement du modele Whisper « %s » (%s / %s)", self.model_size, device, compute
        )
        self._model = WhisperModel(
            self.model_size,
            device=device,
            compute_type=compute,
            download_root=str(get_settings().paths.models),
        )
        return self._model

    def transcribe(
        self,
        audio_path: Path,
        language: str = "auto",
        progress: ProgressCallback | None = None,
        cancel: CancellationToken | None = None,
    ) -> TranscriptionResult:
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise TranscriptionError(
                f"Audio introuvable : {audio_path}",
                user_message="Le fichier audio a transcrire est introuvable.",
            )
        model = self._load_model()
        lang = None if (language or "auto").lower() == "auto" else language

        if progress is not None:
            progress(
                ProgressEvent(
                    stage=PipelineStage.TRANSCRIBE, percent=1.0, message="Analyse de l'audio…"
                )
            )
        try:
            segments_iter, info = model.transcribe(
                str(audio_path),
                language=lang,
                vad_filter=True,               # ignore les silences : plus rapide, moins d'erreurs
                beam_size=5,
                condition_on_previous_text=False,  # limite la propagation d'hallucinations
            )
        except Exception as exc:
            raise TranscriptionError(
                str(exc), user_message="La transcription a echoue."
            ) from exc

        total = float(getattr(info, "duration", 0.0)) or wav_duration(audio_path)
        segments: list[TranscriptSegment] = []
        pieces: list[str] = []
        for index, seg in enumerate(segments_iter):
            if cancel is not None and cancel.is_cancelled():
                raise TranscriptionError(
                    "Transcription annulee", user_message="Transcription annulee."
                )
            text = (seg.text or "").strip()
            if not text:
                continue
            segments.append(
                TranscriptSegment(
                    index=len(segments),
                    start=float(seg.start or 0.0),
                    end=float(seg.end or 0.0),
                    text=text,
                    confidence=getattr(seg, "avg_logprob", None),
                )
            )
            pieces.append(text)
            if progress is not None and total > 0:
                progress(
                    ProgressEvent(
                        stage=PipelineStage.TRANSCRIBE,
                        percent=min(float(seg.end or 0) / total * 100.0, 99.0),
                        message=f"Transcription… {len(segments)} segments",
                    )
                )
            del index

        result = TranscriptionResult(
            text=normalize_whitespace(" ".join(pieces)),
            segments=segments,
            language=getattr(info, "language", None) or language,
            duration=total,
            engine=self.name,
            model=self.model_size,
        )
        if progress is not None:
            progress(
                ProgressEvent(
                    stage=PipelineStage.TRANSCRIBE,
                    percent=100.0,
                    message=f"{result.word_count} mots transcrits",
                    done=True,
                )
            )
        return result


class MockTranscriptionEngine(TranscriptionEngine):
    """Moteur factice : tests et demonstration sans modele telecharge."""

    name = "mock"

    def __init__(self, text: str | None = None) -> None:
        self.text = text or (
            "bonjour et bienvenue dans cette demonstration alors aujourd'hui "
            "on va parler de python et de transcription automatique"
        )

    def is_available(self) -> bool:
        return True

    def transcribe(
        self,
        audio_path: Path,
        language: str = "auto",
        progress: ProgressCallback | None = None,
        cancel: CancellationToken | None = None,
    ) -> TranscriptionResult:
        words = self.text.split()
        per_segment = max(len(words) // 4, 1)
        segments: list[TranscriptSegment] = []
        for i in range(0, len(words), per_segment):
            chunk = " ".join(words[i : i + per_segment])
            idx = len(segments)
            segments.append(
                TranscriptSegment(index=idx, start=idx * 5.0, end=(idx + 1) * 5.0, text=chunk)
            )
        if progress is not None:
            progress(
                ProgressEvent(
                    stage=PipelineStage.TRANSCRIBE, percent=100.0, message="Simulation", done=True
                )
            )
        return TranscriptionResult(
            text=self.text,
            segments=segments,
            language="fr" if language == "auto" else language,
            duration=len(segments) * 5.0,
            engine=self.name,
            model="mock",
        )


#: Registre des moteurs : ajouter une entree suffit a exposer un nouveau moteur.
ENGINES: dict[str, type[TranscriptionEngine]] = {
    FasterWhisperEngine.name: FasterWhisperEngine,
    MockTranscriptionEngine.name: MockTranscriptionEngine,
}


def create_engine(name: str | None = None) -> TranscriptionEngine:
    """Instancie le moteur demande, avec repli sur le moteur factice."""
    key = (name or get_settings().transcription_engine or "faster-whisper").lower()
    engine_cls = ENGINES.get(key)
    if engine_cls is None:
        raise EngineNotAvailableError(
            f"Moteur inconnu : {key}",
            user_message=f"Moteur « {key} » inconnu. Disponibles : {', '.join(ENGINES)}",
        )
    return engine_cls()


def available_engines() -> list[str]:
    """Noms des moteurs reellement utilisables sur cette machine."""
    return [name for name, cls in ENGINES.items() if cls().is_available()]
