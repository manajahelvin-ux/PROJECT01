"""Configuration centralisee de TRANSCRIBE AI.

Priorite de resolution (du plus fort au plus faible) :

1. Arguments explicites passes au constructeur `Settings(...)`
2. Variables d'environnement du processus
3. Fichier `.env` a la racine du projet
4. Valeurs par defaut definies ici

La cle API n'est jamais journalisee ni serialisee en clair : elle est
enveloppee dans un `SecretStr` et masquee par `masked_api_key`.
"""

from __future__ import annotations

import functools
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from transcribe_ai.config.paths import AppPaths, app_paths

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"


class AIMode(StrEnum):
    """Niveau de traitement IA applique apres la transcription."""

    NONE = "none"                      # aucun appel OpenRouter (cout zero)
    CLEAN = "clean"                    # nettoyage + ponctuation + paragraphes
    CLEAN_SUMMARY = "clean_summary"    # nettoyage + resume
    FULL = "full"                      # nettoyage + resume + points cles + mots-cles


class Theme(StrEnum):
    DARK = "dark"
    LIGHT = "light"
    SYSTEM = "system"


SUPPORTED_LANGUAGES: dict[str, str] = {
    "auto": "Detection automatique",
    "fr": "Francais",
    "en": "Anglais",
    "mg": "Malagasy",
    "es": "Espagnol",
    "pt": "Portugais",
    "de": "Allemand",
    "it": "Italien",
}

VIDEO_EXTENSIONS: tuple[str, ...] = (".mp4", ".mkv", ".avi", ".mov", ".webm")
AUDIO_EXTENSIONS: tuple[str, ...] = (".mp3", ".wav", ".m4a", ".flac", ".ogg")
MEDIA_EXTENSIONS: tuple[str, ...] = VIDEO_EXTENSIONS + AUDIO_EXTENSIONS

#: Format audio impose au moteur de transcription (contrat du pipeline FFmpeg).
AUDIO_SAMPLE_RATE = 16_000
AUDIO_CHANNELS = 1
AUDIO_CODEC = "pcm_s16le"


class Settings(BaseSettings):
    """Parametres applicatifs, alimentes par l'environnement et `.env`."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- OpenRouter --------------------------------------------------------
    openrouter_api_key: SecretStr = Field(default=SecretStr(""))
    openrouter_model: str = Field(default="openai/gpt-4o-mini")
    openrouter_base_url: str = Field(default="https://openrouter.ai/api/v1")
    openrouter_app_name: str = Field(default="TranscribeAI")
    openrouter_site_url: str = Field(default="https://github.com/manajahelvin-ux/PROJECT01")

    # --- Inference ---------------------------------------------------------
    ai_temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    ai_max_tokens: int = Field(default=4096, ge=256, le=200_000)
    ai_timeout: float = Field(default=120.0, ge=5.0, le=1800.0)
    ai_max_retries: int = Field(default=3, ge=0, le=10)
    ai_retry_backoff: float = Field(default=2.0, ge=1.0, le=10.0)
    ai_mode: AIMode = Field(default=AIMode.CLEAN)

    # --- Chunking ----------------------------------------------------------
    chunk_size: int = Field(default=6000, ge=500, le=100_000)
    chunk_overlap: int = Field(default=200, ge=0, le=5_000)

    # --- Transcription -----------------------------------------------------
    transcription_engine: str = Field(default="faster-whisper")
    whisper_model: str = Field(default="base")
    whisper_device: Literal["auto", "cpu", "cuda"] = Field(default="auto")
    whisper_compute_type: str = Field(default="int8")
    default_language: str = Field(default="auto")

    # --- Binaires externes -------------------------------------------------
    ffmpeg_path: str = Field(default="")
    ffprobe_path: str = Field(default="")

    # --- Stockage ----------------------------------------------------------
    data_dir: str = Field(default="")
    database_url: str = Field(default="")

    # --- Interface ---------------------------------------------------------
    ui_theme: Theme = Field(default=Theme.DARK)
    ui_language: str = Field(default="fr")

    # --- Logs --------------------------------------------------------------
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(default="INFO")

    # ------------------------------------------------------------------ #
    # Validateurs
    # ------------------------------------------------------------------ #
    @field_validator("openrouter_base_url")
    @classmethod
    def _strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @field_validator("default_language", "ui_language")
    @classmethod
    def _known_language(cls, value: str) -> str:
        code = (value or "auto").strip().lower()
        if code not in SUPPORTED_LANGUAGES:
            raise ValueError(
                f"Langue '{value}' non supportee. Valeurs possibles : "
                f"{', '.join(SUPPORTED_LANGUAGES)}"
            )
        return code

    @field_validator("chunk_overlap")
    @classmethod
    def _overlap_smaller_than_chunk(cls, value: int, info: Any) -> int:
        chunk_size = info.data.get("chunk_size", 6000)
        if value >= chunk_size:
            raise ValueError("chunk_overlap doit etre strictement inferieur a chunk_size")
        return value

    # ------------------------------------------------------------------ #
    # Proprietes derivees
    # ------------------------------------------------------------------ #
    @property
    def paths(self) -> AppPaths:
        """Arborescence de travail, creee a la demande."""
        return app_paths(self.data_dir or None).ensure()

    @property
    def resolved_database_url(self) -> str:
        """URL SQLAlchemy effective (SQLite dans le dossier de donnees par defaut)."""
        if self.database_url:
            return self.database_url
        return f"sqlite:///{self.paths.database.as_posix()}"

    @property
    def has_api_key(self) -> bool:
        return bool(self.openrouter_api_key.get_secret_value().strip())

    @property
    def masked_api_key(self) -> str:
        """Representation sure de la cle, utilisable dans l'UI et les logs."""
        key = self.openrouter_api_key.get_secret_value().strip()
        if not key:
            return "(non definie)"
        if len(key) <= 10:
            return "*" * len(key)
        return f"{key[:6]}{'*' * 12}{key[-4:]}"

    def api_key_value(self) -> str:
        """Acces explicite au secret : rend l'usage reperable en revue de code."""
        return self.openrouter_api_key.get_secret_value().strip()

    def safe_dump(self) -> dict[str, Any]:
        """Vue serialisable sans secret, destinee aux logs et au diagnostic."""
        data = self.model_dump(mode="json", exclude={"openrouter_api_key"})
        data["openrouter_api_key"] = self.masked_api_key
        return data


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Instance unique et memoisee des parametres."""
    return Settings()


def reload_settings(**overrides: Any) -> Settings:
    """Vide le cache et reconstruit les parametres (apres edition dans l'UI)."""
    get_settings.cache_clear()
    if overrides:
        return Settings(**overrides)
    return get_settings()
