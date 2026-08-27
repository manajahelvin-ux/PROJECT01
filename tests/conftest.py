"""Fixtures partagees par la suite de tests.

Regle absolue : aucun test n'utilise de vraie cle API ni de reseau.
L'environnement est isole pour que le `.env` du developpeur n'influence
jamais les resultats.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

_APP_ENV_VARS = [
    "OPENROUTER_API_KEY",
    "OPENROUTER_MODEL",
    "OPENROUTER_BASE_URL",
    "AI_TEMPERATURE",
    "AI_MAX_TOKENS",
    "AI_TIMEOUT",
    "CHUNK_SIZE",
    "CHUNK_OVERLAP",
    "DEFAULT_LANGUAGE",
    "UI_THEME",
    "UI_LANGUAGE",
    "LOG_LEVEL",
    "DATA_DIR",
    "DATABASE_URL",
]


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Neutralise l'environnement reel et redirige les donnees vers tmp_path."""
    for var in _APP_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    data_dir = tmp_path / "appdata"
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    from transcribe_ai.config.settings import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def settings(isolated_env):
    """Parametres construits sans lecture du fichier .env du developpeur."""
    from transcribe_ai.config.settings import Settings

    return Settings(_env_file=None, data_dir=os.environ["DATA_DIR"])


@pytest.fixture
def fake_api_key() -> str:
    """Cle factice, jamais valide cote OpenRouter."""
    return "sk-or-v1-000000000000000000000000000000000000000000000000fake"
