"""Utilitaires de temps et de formatage des timestamps de sous-titres."""

from __future__ import annotations


def format_duration(seconds: float) -> str:
    """Duree lisible : 01:02:05."""
    total = int(max(seconds or 0, 0))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def format_srt_timestamp(seconds: float) -> str:
    """Timestamp SRT : 00:01:02,500 (virgule decimale)."""
    total_ms = int(round(max(seconds or 0, 0) * 1000))
    ms = total_ms % 1000
    total_s = total_ms // 1000
    h, rem = divmod(total_s, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def format_vtt_timestamp(seconds: float) -> str:
    """Timestamp WebVTT : 00:01:02.500 (point decimal)."""
    return format_srt_timestamp(seconds).replace(",", ".")


def parse_timestamp(value: str) -> float:
    """Analyse un timestamp SRT ou VTT et retourne des secondes."""
    cleaned = value.strip().replace(",", ".")
    parts = cleaned.split(":")
    if len(parts) == 3:
        h, m, s = parts
    elif len(parts) == 2:
        h, m, s = "0", parts[0], parts[1]
    else:
        raise ValueError(f"Timestamp invalide : {value!r}")
    return int(h) * 3600 + int(m) * 60 + float(s)
