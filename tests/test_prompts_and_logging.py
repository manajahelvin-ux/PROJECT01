"""Phase 1 - tests des prompts, de la redaction des logs et du diagnostic."""

from __future__ import annotations

import logging

import pytest

from transcribe_ai.core.ai.prompts import PROMPTS, get_prompt, translation_prompt
from transcribe_ai.utils.diagnostics import run_diagnostics
from transcribe_ai.utils.logging_config import RedactingFilter, redact, setup_logging


class TestPrompts:
    def test_prompts_requis_presents(self) -> None:
        assert {"clean", "structure", "summary_short", "summary_detailed",
                "key_points", "extraction", "translation"} <= set(PROMPTS)

    @pytest.mark.parametrize("name", sorted(PROMPTS))
    def test_regle_anti_hallucination_partout(self, name: str) -> None:
        assert "Ne jamais inventer d'information." in PROMPTS[name]

    def test_marqueur_inaudible_dans_le_nettoyage(self) -> None:
        assert "[inaudible]" in PROMPTS["clean"]

    def test_consigne_de_langue_ajoutee(self) -> None:
        assert "Francais" in get_prompt("clean", "fr")
        assert "langue du texte source" in get_prompt("clean", "auto")

    def test_prompt_inconnu_echoue_vite(self) -> None:
        with pytest.raises(KeyError):
            get_prompt("inexistant")

    def test_prompt_de_traduction_cible(self) -> None:
        assert "Malagasy" in translation_prompt("mg")

    def test_extraction_impose_du_json(self) -> None:
        prompt = PROMPTS["extraction"]
        assert "JSON" in prompt
        for key in ("topics", "keywords", "actions", "entities"):
            assert key in prompt


class TestRedaction:
    @pytest.mark.parametrize(
        "secret",
        [
            "sk-or-v1-abcdef0123456789abcdef0123456789",
            "Bearer abcdef0123456789abcdef",
            'api_key: "abcdef0123456789"',
        ],
    )
    def test_les_secrets_sont_masques(self, secret: str) -> None:
        cleaned = redact(f"requete avec {secret} envoyee")
        assert "abcdef0123456789" not in cleaned
        assert "REDACTED" in cleaned

    def test_texte_normal_intact(self) -> None:
        assert redact("transcription terminee en 42s") == "transcription terminee en 42s"

    def test_filtre_applique_au_record(self) -> None:
        record = logging.LogRecord(
            "t", logging.INFO, "f", 1,
            "cle=%s", ("sk-or-v1-abcdef0123456789abcdef0123456789",), None,
        )
        RedactingFilter().filter(record)
        assert "abcdef0123456789" not in record.getMessage()

    def test_la_cle_ne_finit_pas_dans_le_fichier_de_log(self, tmp_path, fake_api_key) -> None:
        logger = setup_logging("DEBUG", tmp_path / "logs", force=True)
        logger.info("Authorization: Bearer %s", fake_api_key)
        for handler in logger.handlers:
            handler.flush()
        content = (tmp_path / "logs" / "transcribe_ai.log").read_text(encoding="utf-8")
        assert fake_api_key not in content
        assert "REDACTED" in content


class TestDiagnostics:
    def test_rapport_couvre_les_dependances_cles(self, settings) -> None:
        report = run_diagnostics(settings)
        names = {c.name for c in report.checks}
        assert {"Python 3.11+", "FFmpeg", "yt-dlp", "PySide6 (UI)", "Cle OpenRouter"} <= names

    def test_cle_manquante_non_bloquante(self, settings) -> None:
        report = run_diagnostics(settings)
        key_check = next(c for c in report.checks if c.name == "Cle OpenRouter")
        assert key_check.optional is True

    def test_la_cle_reelle_nest_jamais_affichee(self, fake_api_key) -> None:
        from transcribe_ai.config.settings import Settings

        report = run_diagnostics(Settings(_env_file=None, openrouter_api_key=fake_api_key))
        assert all(fake_api_key not in c.detail for c in report.checks)
