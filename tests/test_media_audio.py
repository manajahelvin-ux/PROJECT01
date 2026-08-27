"""Phases 3-4 - acquisition media et extraction audio."""

from __future__ import annotations

import wave
from pathlib import Path

import pytest

from transcribe_ai.config.settings import AUDIO_CHANNELS, AUDIO_SAMPLE_RATE
from transcribe_ai.core.exceptions import (
    FFmpegError,
    InvalidURLError,
    MediaError,
    UnsupportedFormatError,
)
from transcribe_ai.core.models import SourceType
from transcribe_ai.core.pipeline.audio import FFmpegAudioExtractor, find_ffmpeg
from transcribe_ai.core.pipeline.media import LocalFileProvider, MediaResolver, YtDlpProvider
from transcribe_ai.utils.text import is_media_file, is_url, slugify

ffmpeg_required = pytest.mark.skipif(find_ffmpeg() is None, reason="FFmpeg absent")


@pytest.fixture
def sample_wav(tmp_path: Path) -> Path:
    """Genere un WAV silencieux de 1 s, sans dependre du reseau."""
    path = tmp_path / "source.wav"
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(44100)
        handle.writeframes(b"\x00\x00" * 2 * 44100)
    return path


class TestSourceDetection:
    @pytest.mark.parametrize(
        "url",
        ["https://www.youtube.com/watch?v=abc", "http://vimeo.com/1", "https://x.com/i/status/2"],
    )
    def test_urls_reconnues(self, url: str) -> None:
        assert is_url(url)

    @pytest.mark.parametrize("value", ["", "pas une url", "C:/videos/a.mp4", "ftp://x.fr/a.mp4"])
    def test_non_urls_rejetees(self, value: str) -> None:
        assert not is_url(value)

    @pytest.mark.parametrize("ext", [".mp4", ".mkv", ".avi", ".mov", ".webm"])
    def test_formats_video_supportes(self, ext: str) -> None:
        assert is_media_file(f"video{ext}")

    @pytest.mark.parametrize("ext", [".mp3", ".wav", ".m4a", ".flac", ".ogg"])
    def test_formats_audio_supportes(self, ext: str) -> None:
        assert is_media_file(f"audio{ext}")

    def test_format_non_supporte(self) -> None:
        assert not is_media_file("document.pdf")

    def test_slugify_nom_de_fichier_sur(self) -> None:
        assert slugify("Réunion du 12/03 : bilan !") == "reunion-du-1203-bilan"


class TestMediaResolver:
    def test_url_routee_vers_ytdlp(self) -> None:
        provider = MediaResolver().resolve("https://www.youtube.com/watch?v=abc")
        assert isinstance(provider, YtDlpProvider)

    def test_fichier_route_vers_le_provider_local(self, sample_wav: Path) -> None:
        assert isinstance(MediaResolver().resolve(str(sample_wav)), LocalFileProvider)

    def test_source_inconnue_rejetee(self) -> None:
        with pytest.raises(InvalidURLError):
            MediaResolver().resolve("n'importe quoi")


class TestLocalFileProvider:
    def test_analyse_dun_fichier_local(self, sample_wav: Path) -> None:
        info = LocalFileProvider().analyze(str(sample_wav))
        assert info.source_type is SourceType.LOCAL_FILE
        assert info.title == "source"
        assert info.filesize > 0

    def test_fichier_absent(self, tmp_path: Path) -> None:
        with pytest.raises(MediaError):
            LocalFileProvider().analyze(str(tmp_path / "absent.mp4"))

    def test_extension_refusee(self, tmp_path: Path) -> None:
        bad = tmp_path / "doc.pdf"
        bad.write_text("x")
        with pytest.raises(UnsupportedFormatError):
            LocalFileProvider().analyze(str(bad))

    def test_fetch_ne_copie_pas_le_fichier(self, sample_wav: Path, tmp_path: Path) -> None:
        assert LocalFileProvider().fetch(str(sample_wav), tmp_path) == sample_wav


class TestYtDlpProvider:
    def test_url_invalide_refusee_sans_reseau(self) -> None:
        with pytest.raises(InvalidURLError):
            YtDlpProvider().analyze("pas-une-url")

    def test_metadonnees_normalisees(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """yt-dlp est mocke : aucun appel reseau dans la suite de tests."""

        class FakeYDL:
            def __init__(self, opts): ...
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def extract_info(self, url, download=False):
                return {
                    "title": "Ma video", "duration": 125.0, "uploader": "Chaine",
                    "language": "fr", "extractor_key": "Youtube", "id": "abc",
                }

        import yt_dlp

        monkeypatch.setattr(yt_dlp, "YoutubeDL", FakeYDL)
        info = YtDlpProvider().analyze("https://www.youtube.com/watch?v=abc")
        assert info.title == "Ma video"
        assert info.author == "Chaine"
        assert info.duration_hms == "00:02:05"
        assert info.source_type is SourceType.URL


class TestFFmpegExtractor:
    def test_ffmpeg_detecte(self) -> None:
        assert FFmpegAudioExtractor().is_available() is True

    @ffmpeg_required
    def test_extraction_produit_un_wav_16khz_mono(self, sample_wav: Path, tmp_path: Path) -> None:
        out = FFmpegAudioExtractor().extract(sample_wav, tmp_path / "out.wav")
        assert out.exists()
        with wave.open(str(out), "rb") as handle:
            assert handle.getframerate() == AUDIO_SAMPLE_RATE
            assert handle.getnchannels() == AUDIO_CHANNELS
            assert handle.getsampwidth() == 2  # pcm_s16le

    @ffmpeg_required
    def test_duree_sondee(self, sample_wav: Path) -> None:
        assert FFmpegAudioExtractor().probe_duration(sample_wav) == pytest.approx(1.0, abs=0.2)

    def test_media_absent(self, tmp_path: Path) -> None:
        with pytest.raises(FFmpegError):
            FFmpegAudioExtractor().extract(tmp_path / "absent.mp4", tmp_path / "o.wav")

    @ffmpeg_required
    def test_progression_emise(self, sample_wav: Path, tmp_path: Path) -> None:
        events = []
        FFmpegAudioExtractor().extract(sample_wav, tmp_path / "o.wav", progress=events.append)
        assert events and events[-1].done is True
