"""Phase 7 - chunking intelligent et cache anti-refacturation.

Le decoupage respecte les frontieres de phrases, conserve l'ordre des
blocs et attribue a chacun une empreinte. Un bloc deja traite (meme
texte, meme tache, meme modele) est relu depuis le cache disque plutot
que renvoye — et donc refacture — a OpenRouter.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from transcribe_ai.config.settings import get_settings
from transcribe_ai.core.interfaces import TextChunker
from transcribe_ai.core.models import Chunk
from transcribe_ai.utils.logging_config import get_logger
from transcribe_ai.utils.text import fingerprint, split_sentences

logger = get_logger(__name__)

#: Approximation usuelle : ~4 caracteres par token en moyenne multilingue.
CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    return max(len(text) // CHARS_PER_TOKEN, 1)


class SentenceChunker(TextChunker):
    """Decoupe par phrases, avec recouvrement optionnel entre blocs."""

    def __init__(self, chunk_size: int | None = None, overlap: int | None = None) -> None:
        settings = get_settings()
        self.chunk_size = chunk_size or settings.chunk_size
        self.overlap = settings.chunk_overlap if overlap is None else overlap
        if self.overlap >= self.chunk_size:
            raise ValueError("overlap doit etre inferieur a chunk_size")

    # ------------------------------------------------------------------ #
    def split(self, text: str) -> list[Chunk]:
        """Retourne des blocs ordonnes couvrant l'integralite du texte."""
        content = (text or "").strip()
        if not content:
            return []
        if len(content) <= self.chunk_size:
            return [
                Chunk(
                    index=0,
                    text=content,
                    start_char=0,
                    end_char=len(content),
                    token_estimate=estimate_tokens(content),
                    fingerprint=fingerprint(content),
                )
            ]

        sentences = split_sentences(content) or [content]
        chunks: list[Chunk] = []
        buffer: list[str] = []
        cursor = 0

        def flush() -> None:
            nonlocal buffer, cursor
            if not buffer:
                return
            body = " ".join(buffer).strip()
            chunks.append(
                Chunk(
                    index=len(chunks),
                    text=body,
                    start_char=cursor,
                    end_char=cursor + len(body),
                    token_estimate=estimate_tokens(body),
                    fingerprint=fingerprint(body),
                )
            )
            cursor += len(body) + 1
            # Recouvrement : on reprend la fin du bloc pour garder le contexte.
            if self.overlap > 0:
                tail: list[str] = []
                length = 0
                for sentence in reversed(buffer):
                    if length + len(sentence) > self.overlap:
                        break
                    tail.insert(0, sentence)
                    length += len(sentence) + 1
                buffer = tail
            else:
                buffer = []

        for sentence in sentences:
            # Une phrase demesuree est coupee durement pour ne jamais depasser la limite.
            if len(sentence) > self.chunk_size:
                flush()
                for start in range(0, len(sentence), self.chunk_size):
                    piece = sentence[start : start + self.chunk_size]
                    chunks.append(
                        Chunk(
                            index=len(chunks),
                            text=piece,
                            start_char=cursor,
                            end_char=cursor + len(piece),
                            token_estimate=estimate_tokens(piece),
                            fingerprint=fingerprint(piece),
                        )
                    )
                    cursor += len(piece)
                buffer = []
                continue

            projected = sum(len(s) + 1 for s in buffer) + len(sentence)
            if buffer and projected > self.chunk_size:
                flush()
            buffer.append(sentence)

        if buffer:
            body = " ".join(buffer).strip()
            if not chunks or chunks[-1].text != body:
                chunks.append(
                    Chunk(
                        index=len(chunks),
                        text=body,
                        start_char=cursor,
                        end_char=cursor + len(body),
                        token_estimate=estimate_tokens(body),
                        fingerprint=fingerprint(body),
                    )
                )

        logger.debug("Texte de %s caracteres decoupe en %s blocs", len(content), len(chunks))
        return chunks

    def merge(self, pieces: Iterable[str]) -> str:
        """Recompose le texte final en supprimant les doublons de recouvrement."""
        cleaned = [p.strip() for p in pieces if p and p.strip()]
        if not cleaned:
            return ""
        merged = [cleaned[0]]
        for piece in cleaned[1:]:
            previous = merged[-1]
            # Le recouvrement peut faire reapparaitre la fin du bloc precedent.
            overlap_len = 0
            # Seuil bas volontairement prudent : en deca de 15 caracteres,
            # une coincidence fortuite est plus probable qu'un vrai recouvrement.
            limit = min(len(previous), len(piece), 400)
            for size in range(limit, 14, -1):
                if previous[-size:].strip() == piece[:size].strip():
                    overlap_len = size
                    break
            merged.append(piece[overlap_len:].strip())
        return "\n\n".join(p for p in merged if p)


class ChunkCache:
    """Cache disque des blocs deja traites : evite de repayer un appel IA."""

    def __init__(self, directory: Path | None = None) -> None:
        self.directory = Path(directory or get_settings().paths.cache)
        self.directory.mkdir(parents=True, exist_ok=True)

    def _key(self, chunk_fingerprint: str, task: str, model: str) -> str:
        return fingerprint(f"{chunk_fingerprint}|{task}|{model}")

    def _path(self, chunk_fingerprint: str, task: str, model: str) -> Path:
        return self.directory / f"{self._key(chunk_fingerprint, task, model)}.json"

    def get(self, chunk_fingerprint: str, task: str, model: str) -> str | None:
        path = self._path(chunk_fingerprint, task, model)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8")).get("content")
        except (json.JSONDecodeError, OSError):
            return None

    def set(self, chunk_fingerprint: str, task: str, model: str, content: str) -> None:
        path = self._path(chunk_fingerprint, task, model)
        try:
            path.write_text(
                json.dumps({"task": task, "model": model, "content": content}, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as exc:  # le cache est un confort, jamais un point de rupture
            logger.debug("Ecriture du cache impossible : %s", exc)

    def clear(self) -> int:
        removed = 0
        for path in self.directory.glob("*.json"):
            try:
                path.unlink()
                removed += 1
            except OSError:
                pass
        return removed

    def size(self) -> int:
        return len(list(self.directory.glob("*.json")))
