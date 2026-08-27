"""Phase 1 - tests du socle de configuration."""

from __future__ import annotations

import pytest

from transcribe_ai.config.paths import app_paths
from transcribe_ai.config.settings import AIMode, Settings, Theme, get_settings


class TestDefaults:
    def test_valeurs_par_defaut_raisonnables(self, settings: Settings) -> None:
        assert settings.openrouter_base_url == "https://openrouter.ai/api/v1"
        assert 0.0 <= settings.ai_temperature <= 1.0
        assert settings.ai_max_retries >= 1
        assert settings.chunk_overlap < settings.chunk_size
        assert settings.ai_mode is AIMode.CLEAN
        assert settings.ui_theme is Theme.DARK

    def test_aucune_cle_api_codee_en_dur(self, settings: Settings) -> None:
        assert settings.api_key_value() == ""
        assert settings.has_api_key is False

    def test_base_url_sans_slash_final(self) -> None:
        s = Settings(_env_file=None, openrouter_base_url="https://openrouter.ai/api/v1/")
        assert s.openrouter_base_url == "https://openrouter.ai/api/v1"


class TestSecretHandling:
    def test_cle_masquee(self, fake_api_key: str) -> None:
        s = Settings(_env_file=None, openrouter_api_key=fake_api_key)
        masked = s.masked_api_key
        assert fake_api_key not in masked
        assert masked.startswith("sk-or-")
        assert "*" in masked

    def test_cle_absente_du_dump(self, fake_api_key: str) -> None:
        s = Settings(_env_file=None, openrouter_api_key=fake_api_key)
        dumped = s.safe_dump()
        assert fake_api_key not in str(dumped)

    def test_repr_ne_fuit_pas_la_cle(self, fake_api_key: str) -> None:
        s = Settings(_env_file=None, openrouter_api_key=fake_api_key)
        assert fake_api_key not in repr(s)


class TestValidation:
    def test_langue_inconnue_rejetee(self) -> None:
        with pytest.raises(ValueError, match="non supportee"):
            Settings(_env_file=None, default_language="klingon")

    @pytest.mark.parametrize("code", ["fr", "en", "mg", "es", "pt", "de", "it", "auto"])
    def test_langues_supportees(self, code: str) -> None:
        assert Settings(_env_file=None, default_language=code).default_language == code

    def test_overlap_superieur_au_chunk_rejete(self) -> None:
        with pytest.raises(ValueError, match="chunk_overlap"):
            Settings(_env_file=None, chunk_size=1000, chunk_overlap=1000)

    def test_temperature_hors_bornes_rejetee(self) -> None:
        with pytest.raises(ValueError):
            Settings(_env_file=None, ai_temperature=5.0)


class TestEnvironmentOverride:
    def test_les_variables_env_priment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet")
        monkeypatch.setenv("AI_TEMPERATURE", "0.7")
        get_settings.cache_clear()
        s = Settings(_env_file=None)
        assert s.openrouter_model == "anthropic/claude-3.5-sonnet"
        assert s.ai_temperature == 0.7

    def test_get_settings_est_memoise(self) -> None:
        assert get_settings() is get_settings()


class TestPaths:
    def test_arborescence_creee(self, settings: Settings) -> None:
        paths = settings.paths
        for directory in (
            paths.root,
            paths.logs,
            paths.downloads,
            paths.audio,
            paths.transcriptions,
            paths.exports,
            paths.cache,
        ):
            assert directory.is_dir()

    def test_url_sqlite_par_defaut(self, settings: Settings) -> None:
        url = settings.resolved_database_url
        assert url.startswith("sqlite:///")
        assert url.endswith("transcribe_ai.sqlite3")

    def test_data_dir_explicite_respecte(self, tmp_path) -> None:
        custom = tmp_path / "ailleurs"
        paths = app_paths(custom).ensure()
        assert paths.root == custom.resolve()
        assert paths.database.parent == custom.resolve()
