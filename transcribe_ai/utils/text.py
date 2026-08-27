"""Utilitaires de texte : validation de source, empreintes, noms de fichiers."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

from transcribe_ai.config.settings import AUDIO_EXTENSIONS, MEDIA_EXTENSIONS, VIDEO_EXTENSIONS

_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def is_url(source: str) -> bool:
    """Vrai si la chaine est une URL http(s) exploitable."""
    if not source or not _URL_RE.match(source.strip()):
        return False
    parsed = urlparse(source.strip())
    return bool(parsed.netloc)


def is_media_file(source: str) -> bool:
    """Vrai si le chemin pointe vers un media dont l'extension est supportee."""
    path = Path(source.strip().strip('"'))
    return path.suffix.lower() in MEDIA_EXTENSIONS


def is_audio_file(source: str) -> bool:
    return Path(source).suffix.lower() in AUDIO_EXTENSIONS


def is_video_file(source: str) -> bool:
    return Path(source).suffix.lower() in VIDEO_EXTENSIONS


def fingerprint(text: str) -> str:
    """Empreinte stable d'un texte : cle de cache des chunks deja traites."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:32]


def slugify(value: str, max_length: int = 60) -> str:
    """Nom de fichier sur, sans accent ni caractere interdit sous Windows."""
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^\w\s-]", "", ascii_text).strip()
    cleaned = re.sub(r"[\s_-]+", "-", cleaned).strip("-")
    return (cleaned[:max_length].rstrip("-") or "transcription").lower()


def word_count(text: str) -> int:
    return len(text.split())


def normalize_whitespace(text: str) -> str:
    """Nettoyage typographique minimal, applique meme sans IA."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_sentences(text: str) -> list[str]:
    """Decoupe en phrases, en conservant la ponctuation finale.

    Volontairement sans dependance externe : suffisant pour du chunking,
    et deterministe quelle que soit la langue.
    """
    if not text.strip():
        return []
    parts = re.split(r"(?<=[.!?…])\s+(?=[^\s])", text.strip())
    return [p.strip() for p in parts if p.strip()]
