"""Phase 3 - acquisition du media : URL (yt-dlp) et fichier local."""

from __future__ import annotations

from pathlib import Path

from transcribe_ai.config.settings import MEDIA_EXTENSIONS
from transcribe_ai.core.exceptions import (
    DownloadError,
    InvalidURLError,
    MediaError,
    MissingDependencyError,
    UnsupportedFormatError,
)
from transcribe_ai.core.interfaces import CancellationToken, MediaProvider, ProgressCallback
from transcribe_ai.core.models import MediaInfo, PipelineStage, ProgressEvent, SourceType
from transcribe_ai.utils.logging_config import get_logger
from transcribe_ai.utils.text import is_media_file, is_url, slugify

logger = get_logger(__name__)


def _emit(progress: ProgressCallback | None, stage: PipelineStage, pct: float, msg: str) -> None:
    if progress is not None:
        progress(ProgressEvent(stage=stage, percent=pct, message=msg))


class LocalFileProvider(MediaProvider):
    """Fichier deja present sur le disque : aucun telechargement requis."""

    name = "local"

    def supports(self, source: str) -> bool:
        return not is_url(source) and is_media_file(source)

    def analyze(self, source: str) -> MediaInfo:
        path = Path(source.strip().strip('"')).expanduser()
        if not path.exists():
            raise MediaError(
                f"Fichier introuvable : {path}",
                user_message=f"Le fichier « {path.name} » est introuvable.",
            )
        if path.suffix.lower() not in MEDIA_EXTENSIONS:
            raise UnsupportedFormatError(
                f"Extension non supportee : {path.suffix}",
                user_message=(
                    f"Le format « {path.suffix} » n'est pas pris en charge. "
                    f"Formats acceptes : {', '.join(MEDIA_EXTENSIONS)}"
                ),
            )
        duration = 0.0
        try:  # la duree exacte est fournie par ffprobe, sans bloquer si absent
            from transcribe_ai.core.pipeline.audio import FFmpegAudioExtractor

            duration = FFmpegAudioExtractor().probe_duration(path)
        except Exception as exc:
            logger.debug("ffprobe indisponible pour %s : %s", path.name, exc)

        return MediaInfo(
            title=path.stem,
            source=str(path),
            source_type=SourceType.LOCAL_FILE,
            duration=duration,
            author=None,
            extractor="local",
            filesize=path.stat().st_size,
        )

    def fetch(
        self,
        source: str,
        destination: Path,
        progress: ProgressCallback | None = None,
        cancel: CancellationToken | None = None,
    ) -> Path:
        path = Path(source.strip().strip('"')).expanduser()
        if not path.exists():
            raise MediaError(f"Fichier introuvable : {path}")
        _emit(progress, PipelineStage.DOWNLOAD, 100.0, "Fichier local pret")
        return path  # aucune copie : on lit la source telle quelle


class YtDlpProvider(MediaProvider):
    """Telechargement via yt-dlp (YouTube et ~1800 sites compatibles)."""

    name = "yt-dlp"

    def supports(self, source: str) -> bool:
        return is_url(source)

    # -- outils internes -------------------------------------------------
    @staticmethod
    def _import_ytdlp():
        try:
            import yt_dlp
        except ImportError as exc:  # pragma: no cover - depend de l'installation
            raise MissingDependencyError(
                "yt-dlp est introuvable",
                user_message=(
                    "yt-dlp n'est pas installe. "
                    "Executez : pip install -r requirements.txt"
                ),
            ) from exc
        return yt_dlp

    def analyze(self, source: str) -> MediaInfo:
        if not is_url(source):
            raise InvalidURLError(f"URL invalide : {source}")
        yt_dlp = self._import_ytdlp()
        options = {"quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True}
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(source, download=False)
        except Exception as exc:
            logger.warning("Analyse impossible pour %s : %s", source, exc)
            raise InvalidURLError(
                str(exc),
                user_message=(
                    "Impossible d'analyser cette URL. Verifiez le lien, "
                    "sa disponibilite publique et votre connexion."
                ),
            ) from exc

        if info is None:
            raise InvalidURLError("Aucune metadonnee renvoyee par yt-dlp")
        if "entries" in info:  # playlist : on retient la premiere entree
            entries = [e for e in info.get("entries") or [] if e]
            if not entries:
                raise InvalidURLError("Playlist vide")
            info = entries[0]

        return MediaInfo(
            title=info.get("title") or "Sans titre",
            source=source,
            source_type=SourceType.URL,
            duration=float(info.get("duration") or 0.0),
            author=info.get("uploader") or info.get("channel"),
            language=info.get("language"),
            thumbnail_url=info.get("thumbnail"),
            extractor=info.get("extractor_key") or info.get("extractor"),
            filesize=info.get("filesize") or info.get("filesize_approx"),
            raw={k: info.get(k) for k in ("id", "webpage_url", "upload_date", "view_count")},
        )

    def fetch(
        self,
        source: str,
        destination: Path,
        progress: ProgressCallback | None = None,
        cancel: CancellationToken | None = None,
    ) -> Path:
        if not is_url(source):
            raise InvalidURLError(f"URL invalide : {source}")
        yt_dlp = self._import_ytdlp()
        destination.mkdir(parents=True, exist_ok=True)

        def hook(status: dict) -> None:
            if cancel is not None and cancel.is_cancelled():
                raise DownloadError("Telechargement annule")
            if status.get("status") == "downloading":
                total = status.get("total_bytes") or status.get("total_bytes_estimate") or 0
                done = status.get("downloaded_bytes") or 0
                pct = (done / total * 100.0) if total else 0.0
                speed = status.get("speed") or 0
                _emit(
                    progress,
                    PipelineStage.DOWNLOAD,
                    min(pct, 99.0),
                    f"Telechargement… {pct:.0f} % ({speed / 1e6:.1f} Mo/s)"
                    if speed
                    else f"Telechargement… {pct:.0f} %",
                )
            elif status.get("status") == "finished":
                _emit(progress, PipelineStage.DOWNLOAD, 100.0, "Telechargement termine")

        # On privilegie une piste audio seule : plus rapide et suffisant pour la STT.
        options = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "format": "bestaudio/best",
            "outtmpl": str(destination / "%(id)s.%(ext)s"),
            "progress_hooks": [hook],
            "retries": 3,
            "socket_timeout": 30,
        }
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(source, download=True)
                if "entries" in info:
                    info = next(e for e in info["entries"] if e)
                path = Path(ydl.prepare_filename(info))
        except Exception as exc:
            logger.error("Telechargement echoue : %s", exc)
            raise DownloadError(
                str(exc),
                user_message="Le telechargement a echoue. Verifiez le lien et votre connexion.",
            ) from exc

        if not path.exists():  # yt-dlp a pu remuxer vers une autre extension
            candidates = sorted(destination.glob(f"{path.stem}.*"))
            if not candidates:
                raise DownloadError("Fichier telecharge introuvable")
            path = candidates[0]
        logger.info("Telecharge : %s (%.1f Mo)", path.name, path.stat().st_size / 1e6)
        return path


class MediaResolver:
    """Selectionne automatiquement le fournisseur adapte a la source."""

    def __init__(self, providers: list[MediaProvider] | None = None) -> None:
        self.providers = providers or [LocalFileProvider(), YtDlpProvider()]

    def resolve(self, source: str) -> MediaProvider:
        for provider in self.providers:
            if provider.supports(source):
                return provider
        raise InvalidURLError(
            f"Aucun fournisseur pour : {source}",
            user_message=(
                "Source non reconnue. Fournissez une URL http(s) valide "
                "ou un fichier media supporte."
            ),
        )

    def analyze(self, source: str) -> MediaInfo:
        return self.resolve(source).analyze(source)

    def suggest_filename(self, info: MediaInfo) -> str:
        return slugify(info.title)
