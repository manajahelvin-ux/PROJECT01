"""Journalisation applicative avec redaction systematique des secrets.

Aucune cle API ne doit apparaitre dans un fichier de log, meme si un
appelant journalise imprudemment un en-tete HTTP complet.
"""

from __future__ import annotations

import logging
import re
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_CONFIGURED = False

#: Motifs de secrets connus : cles OpenRouter, Bearer tokens, champs api_key.
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-or-v1-[A-Za-z0-9\-_]{8,}"),
    re.compile(r"sk-[A-Za-z0-9\-_]{16,}"),
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9\-_\.]{8,}"),
    re.compile(r"(?i)((?:api[_-]?key|authorization)[\"'\s:=]+)[A-Za-z0-9\-_\.]{8,}"),
)

REDACTED = "***REDACTED***"


def redact(text: str) -> str:
    """Remplace tout secret reconnu par un marqueur neutre."""
    result = text
    for pattern in _SECRET_PATTERNS:
        if pattern.groups:
            result = pattern.sub(lambda m: f"{m.group(1)}{REDACTED}", result)
        else:
            result = pattern.sub(REDACTED, result)
    return result


class RedactingFilter(logging.Filter):
    """Filtre applique a tous les handlers : nettoie message et arguments."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: redact(v) if isinstance(v, str) else v for k, v in record.args.items()
                }
            else:
                record.args = tuple(
                    redact(a) if isinstance(a, str) else a for a in record.args
                )
        return True


def setup_logging(
    level: str = "INFO",
    log_dir: Path | None = None,
    *,
    force: bool = False,
) -> logging.Logger:
    """Configure le logger racine 'transcribe_ai' (console + fichier tournant)."""
    global _CONFIGURED
    logger = logging.getLogger("transcribe_ai")
    if _CONFIGURED and not force:
        return logger

    logger.setLevel(level.upper())
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    redactor = RedactingFilter()

    console = logging.StreamHandler(stream=sys.stderr)
    console.setFormatter(formatter)
    console.addFilter(redactor)
    logger.addHandler(console)

    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_dir / "transcribe_ai.log",
            maxBytes=2_000_000,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(redactor)
        logger.addHandler(file_handler)

    _CONFIGURED = True
    return logger


def get_logger(name: str) -> logging.Logger:
    """Logger enfant du logger applicatif ('transcribe_ai.<name>')."""
    suffix = name.split("transcribe_ai.")[-1]
    return logging.getLogger(f"transcribe_ai.{suffix}")
