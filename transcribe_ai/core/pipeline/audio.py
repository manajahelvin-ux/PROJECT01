"""Phase 4 - extraction audio FFmpeg : WAV 16 kHz mono, contrat du pipeline."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from transcribe_ai.config.settings import (
    AUDIO_CHANNELS,
    AUDIO_CODEC,
    AUDIO_SAMPLE_RATE,
    get_settings,
)
from transcribe_ai.core.exceptions import FFmpegError, MissingDependencyError
from transcribe_ai.core.interfaces import AudioExtractor, CancellationToken, ProgressCallback
from transcribe_ai.core.models import PipelineStage, ProgressEvent
from transcribe_ai.utils.logging_config import get_logger
from transcribe_ai.utils.timecode import parse_timestamp

logger = get_logger(__name__)

_TIME_RE = re.compile(r"time=(\d+:\d+:\d+\.\d+)")

#: Empeche l'ouverture d'une fenetre console sous Windows (app packagee).
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0


def find_ffmpeg(configured: str = "") -> str | None:
    """Chemin FFmpeg : configure, puis PATH, puis binaire imageio-ffmpeg."""
    if configured and Path(configured).exists():
        return configured
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001 - dependance optionnelle
        return None


def find_ffprobe(configured: str = "") -> str | None:
    """Chemin ffprobe : configure, puis PATH, puis voisin du binaire ffmpeg."""
    if configured and Path(configured).exists():
        return configured
    found = shutil.which("ffprobe")
    if found:
        return found
    ffmpeg = find_ffmpeg()
    if ffmpeg:
        candidate = Path(ffmpeg).with_name("ffprobe" + Path(ffmpeg).suffix)
        if candidate.exists():
            return str(candidate)
    return None


class FFmpegAudioExtractor(AudioExtractor):
    """Convertit tout media en WAV 16 kHz mono pcm_s16le."""

    def __init__(self, ffmpeg_path: str | None = None, ffprobe_path: str | None = None) -> None:
        settings = get_settings()
        self._ffmpeg = ffmpeg_path or find_ffmpeg(settings.ffmpeg_path)
        self._ffprobe = ffprobe_path or find_ffprobe(settings.ffprobe_path)

    @property
    def ffmpeg_path(self) -> str:
        if not self._ffmpeg:
            raise MissingDependencyError(
                "FFmpeg introuvable",
                user_message=(
                    "FFmpeg est introuvable. Installez-le et ajoutez-le au PATH, "
                    "ou renseignez FFMPEG_PATH dans le fichier .env."
                ),
            )
        return self._ffmpeg

    def is_available(self) -> bool:
        return self._ffmpeg is not None

    # ------------------------------------------------------------------ #
    def probe_duration(self, media_path: Path) -> float:
        """Duree en secondes via ffprobe ; 0.0 si indisponible."""
        if not self._ffprobe:
            return self._probe_duration_with_ffmpeg(media_path)
        cmd = [
            self._ffprobe, "-v", "quiet", "-print_format", "json",
            "-show_format", str(media_path),
        ]
        try:
            out = subprocess.run(  # noqa: S603 - arguments entierement controles
                cmd, capture_output=True, text=True, timeout=60, creationflags=_NO_WINDOW
            )
            data = json.loads(out.stdout or "{}")
            return float(data.get("format", {}).get("duration", 0.0))
        except Exception as exc:  # noqa: BLE001
            logger.debug("ffprobe a echoue sur %s : %s", media_path.name, exc)
            return 0.0

    def _probe_duration_with_ffmpeg(self, media_path: Path) -> float:
        """Repli : lit la duree dans la sortie d'erreur de ffmpeg."""
        if not self._ffmpeg:
            return 0.0
        try:
            out = subprocess.run(  # noqa: S603
                [self._ffmpeg, "-i", str(media_path)],
                capture_output=True, text=True, timeout=60, creationflags=_NO_WINDOW,
            )
            match = re.search(r"Duration: (\d+:\d+:\d+\.\d+)", out.stderr)
            return parse_timestamp(match.group(1)) if match else 0.0
        except Exception:  # noqa: BLE001
            return 0.0

    # ------------------------------------------------------------------ #
    def extract(
        self,
        media_path: Path,
        destination: Path,
        progress: ProgressCallback | None = None,
        cancel: CancellationToken | None = None,
    ) -> Path:
        """Produit le WAV normalise attendu par le moteur de transcription."""
        media_path = Path(media_path)
        if not media_path.exists():
            raise FFmpegError(
                f"Media introuvable : {media_path}",
                user_message=f"Le fichier « {media_path.name} » est introuvable.",
            )
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)

        total = self.probe_duration(media_path)
        cmd = [
            self.ffmpeg_path,
            "-y", "-hide_banner", "-loglevel", "error", "-stats",
            "-i", str(media_path),
            "-vn",                              # on ignore la video
            "-ac", str(AUDIO_CHANNELS),         # mono
            "-ar", str(AUDIO_SAMPLE_RATE),      # 16 kHz
            "-acodec", AUDIO_CODEC,             # PCM 16 bits signe
            str(destination),
        ]
        logger.info("Extraction audio : %s -> %s", media_path.name, destination.name)

        process = subprocess.Popen(  # noqa: S603
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            creationflags=_NO_WINDOW,
        )
        tail: list[str] = []
        assert process.stdout is not None
        for line in process.stdout:
            tail.append(line)
            del tail[:-20]
            if cancel is not None and cancel.is_cancelled():
                process.kill()
                raise FFmpegError("Extraction annulee", user_message="Extraction audio annulee.")
            match = _TIME_RE.search(line)
            if match and total > 0 and progress is not None:
                elapsed = parse_timestamp(match.group(1))
                progress(
                    ProgressEvent(
                        stage=PipelineStage.EXTRACT_AUDIO,
                        percent=min(elapsed / total * 100.0, 99.0),
                        message="Extraction audio…",
                    )
                )
        code = process.wait()
        if code != 0 or not destination.exists():
            raise FFmpegError(
                f"FFmpeg a retourne le code {code} : {''.join(tail)[-500:]}",
                user_message="L'extraction audio a echoue. Le fichier est peut-etre corrompu.",
            )
        if progress is not None:
            progress(
                ProgressEvent(
                    stage=PipelineStage.EXTRACT_AUDIO,
                    percent=100.0,
                    message="Audio extrait",
                    done=True,
                )
            )
        return destination
