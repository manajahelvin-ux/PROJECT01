"""Phases 2-9-12-13 - tests de l'interface PySide6.

Les tests s'executent en mode « offscreen » : aucune fenetre reelle, aucun
appel reseau, aucun modele de transcription charge.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from transcribe_ai.config.settings import AIMode, Settings, Theme
from transcribe_ai.core.ai.processor import OpenRouterProcessor
from transcribe_ai.core.engines.whisper_engine import MockTranscriptionEngine
from transcribe_ai.core.models import (
    AIResult,
    AIUsage,
    MediaInfo,
    PipelineStage,
    ProgressEvent,
    SourceType,
)
from transcribe_ai.core.pipeline.orchestrator import TranscriptionPipeline
from transcribe_ai.io.database import Database, HistoryRepository, TranscriptionRecord
from transcribe_ai.ui.pages.settings_page import write_env
from transcribe_ai.ui.theme.styles import build_stylesheet, palette_for
from transcribe_ai.ui.widgets.components import (
    Badge,
    Card,
    PipelineProgress,
    StatCard,
)
from transcribe_ai.ui.widgets.editor import TranscriptEditor
from transcribe_ai.ui.widgets.workers import TaskRunner, Worker


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance() or QApplication([])
    return app


@pytest.fixture
def repository(tmp_path: Path) -> HistoryRepository:
    return HistoryRepository(Database(f"sqlite:///{tmp_path / 'ui.sqlite3'}"))


class FakeProcessor(OpenRouterProcessor):
    """Processeur IA double, sans reseau."""

    def __init__(self, configured: bool = True) -> None:
        self._configured = configured

    def is_configured(self) -> bool:
        return self._configured

    def clean(self, text, language="auto", progress=None, cancel=None):
        return AIResult(cleaned_text=text.upper(), usage=AIUsage(calls=1))

    def summarize(self, text, language="auto"):
        return AIResult(
            short_summary="Court.", detailed_summary="Detaille.", usage=AIUsage(calls=2)
        )

    def translate(self, text, target_language):
        return AIResult(cleaned_text=f"[{target_language}] {text}", usage=AIUsage(calls=1))


@pytest.fixture
def pipeline(tmp_path: Path) -> TranscriptionPipeline:
    settings = Settings(_env_file=None, data_dir=str(tmp_path / "data"))
    return TranscriptionPipeline(
        engine=MockTranscriptionEngine(), processor=FakeProcessor(), settings=settings
    )


# --------------------------------------------------------------------------- #
# Theme
# --------------------------------------------------------------------------- #
class TestTheme:
    @pytest.mark.parametrize("theme", [Theme.DARK, Theme.LIGHT, "dark", "light"])
    def test_feuille_de_style_generee(self, theme) -> None:
        css = build_stylesheet(theme)
        assert "QPushButton" in css and "#Sidebar" in css and "QProgressBar" in css

    def test_les_deux_themes_different(self) -> None:
        assert palette_for("dark").bg != palette_for("light").bg

    def test_theme_systeme_a_un_repli(self) -> None:
        assert palette_for("system").bg == palette_for("dark").bg


# --------------------------------------------------------------------------- #
# Composants
# --------------------------------------------------------------------------- #
class TestComponents:
    def test_card_avec_titre(self, qapp) -> None:
        card = Card("Titre", "Sous-titre")
        assert card.body().count() == 2

    def test_badge_change_de_variante(self, qapp) -> None:
        badge = Badge("Pret", "neutral")
        badge.set_status("Termine", "success")
        assert badge.text() == "Termine"
        assert badge.objectName() == "BadgeSuccess"

    def test_stat_card(self, qapp) -> None:
        card = StatCard("0", "Transcriptions")
        card.set_value("42")
        assert card.value_label.text() == "42"

    def test_progression_couvre_les_six_etapes(self, qapp) -> None:
        progress = PipelineProgress()
        assert len(progress.rows) == 6

    def test_progression_marque_les_etapes_precedentes(self, qapp) -> None:
        progress = PipelineProgress()
        progress.apply(ProgressEvent(stage=PipelineStage.TRANSCRIBE, percent=50.0, message="…"))
        assert progress.rows[PipelineStage.ANALYZE].bar.value() == 100
        assert progress.rows[PipelineStage.DOWNLOAD].bar.value() == 100
        assert progress.rows[PipelineStage.TRANSCRIBE].bar.value() == 50
        assert progress.rows[PipelineStage.AI_PROCESS].bar.value() == 0

    def test_progression_reinitialisable(self, qapp) -> None:
        progress = PipelineProgress()
        progress.apply(ProgressEvent(stage=PipelineStage.FINALIZE, percent=100.0, done=True))
        progress.reset()
        assert all(row.bar.value() == 0 for row in progress.rows.values())


# --------------------------------------------------------------------------- #
# Threads
# --------------------------------------------------------------------------- #
class TestWorkers:
    def test_resultat_transmis(self, qapp) -> None:
        runner = TaskRunner()
        results = []
        worker = runner.submit(lambda: 6 * 7)
        worker.signals.finished.connect(results.append)
        runner.wait(5000)
        qapp.processEvents()
        assert results == [42]

    def test_erreur_convertie_en_message(self, qapp) -> None:
        from transcribe_ai.core.exceptions import DownloadError

        runner = TaskRunner()
        errors = []

        def boom():
            raise DownloadError("technique")

        worker = runner.submit(boom)
        worker.signals.failed.connect(errors.append)
        runner.wait(5000)
        qapp.processEvents()
        assert errors and "telechargement" in errors[0].lower()

    def test_progression_relayee(self, qapp) -> None:
        events = []

        def task(progress=None):
            progress(ProgressEvent(stage=PipelineStage.ANALYZE, percent=100.0))
            return "fini"

        runner = TaskRunner()
        worker = runner.submit(task)
        worker.signals.progress.connect(events.append)
        runner.wait(5000)
        qapp.processEvents()
        assert len(events) == 1

    def test_annulation_transmise(self, qapp) -> None:
        seen = {}

        def task(cancel=None):
            seen["cancelled"] = cancel.is_cancelled()
            return None

        worker = Worker(task)
        worker.cancel()
        worker.run()
        assert seen["cancelled"] is True


# --------------------------------------------------------------------------- #
# Editeur (Phase 9)
# --------------------------------------------------------------------------- #
class TestEditor:
    def test_texte_et_compteur_de_mots(self, qapp) -> None:
        editor = TranscriptEditor()
        editor.set_text("bonjour tout le monde", keep_undo=False)
        assert editor.text() == "bonjour tout le monde"
        assert "4 mots" in editor.word_badge.text()

    def test_annuler_refaire(self, qapp) -> None:
        editor = TranscriptEditor()
        editor.set_text("version 1", keep_undo=False)
        editor.set_text("version 2", keep_undo=True)
        editor.editor.undo()
        assert editor.text() == "version 1"
        editor.editor.redo()
        assert editor.text() == "version 2"

    def test_recherche(self, qapp) -> None:
        editor = TranscriptEditor()
        editor.set_text("Python est un langage. Python est simple.", keep_undo=False)
        editor.search_input.setText("langage")
        assert editor.find_next() is True
        editor.search_input.setText("absent")
        assert editor.find_next() is False

    def test_tout_remplacer(self, qapp) -> None:
        editor = TranscriptEditor()
        editor.set_text("chat chien chat chat", keep_undo=False)
        editor.search_input.setText("chat")
        editor.replace_input.setText("chaton")
        assert editor.replace_all() == 3
        assert editor.text() == "chaton chien chaton chaton"

    def test_remplacement_annulable(self, qapp) -> None:
        editor = TranscriptEditor()
        editor.set_text("un deux trois", keep_undo=False)
        editor.search_input.setText("deux")
        editor.replace_input.setText("2")
        editor.replace_all()
        editor.editor.undo()
        assert "deux" in editor.text()

    def test_signaux_ia(self, qapp) -> None:
        editor = TranscriptEditor()
        received = []
        editor.ai_requested.connect(lambda a, b: received.append((a, b)))
        editor.btn_clean.click()
        editor.btn_summary.click()
        editor.btn_translate.click()
        assert [r[0] for r in received] == ["clean", "summary", "translate"]
        assert received[2][1]  # une langue cible est transmise


# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #
class TestPages:
    def test_accueil_affiche_les_statistiques(self, qapp, repository) -> None:
        from transcribe_ai.ui.pages.home import HomePage

        repository.add(TranscriptionRecord(title="A", word_count=120, duration=60, ai_calls=3))
        page = HomePage(repository)
        page.refresh()
        assert page.stat_count.value_label.text() == "1"
        assert page.stat_words.value_label.text() == "120"
        assert page.stat_duration.value_label.text() == "00:01:00"

    def test_page_transcription_expose_les_quatre_exports(self, qapp, pipeline, repository) -> None:
        from transcribe_ai.ui.pages.transcribe import TranscribePage

        page = TranscribePage(pipeline, repository, TaskRunner())
        formats = []
        page.export_bar.export_requested.connect(formats.append)
        for button in page.export_bar.findChildren(type(page.btn_import)):
            button.click()
        assert formats == ["txt", "docx", "srt", "vtt"]

    def test_modes_ia_disponibles(self, qapp, pipeline, repository) -> None:
        from transcribe_ai.ui.pages.transcribe import TranscribePage

        page = TranscribePage(pipeline, repository, TaskRunner())
        modes = {page.ai_mode_box.itemData(i) for i in range(page.ai_mode_box.count())}
        assert modes == {m.value for m in AIMode}

    def test_toutes_les_langues_proposees(self, qapp, pipeline, repository) -> None:
        from transcribe_ai.ui.pages.transcribe import TranscribePage

        page = TranscribePage(pipeline, repository, TaskRunner())
        codes = {page.language_box.itemData(i) for i in range(page.language_box.count())}
        assert {"auto", "fr", "en", "mg", "es", "pt", "de", "it"} <= codes

    def test_analyse_alimente_les_informations(self, qapp, pipeline, repository) -> None:
        from transcribe_ai.ui.pages.transcribe import TranscribePage

        page = TranscribePage(pipeline, repository, TaskRunner())
        page._on_analyzed(
            MediaInfo(
                title="Ma video", source="https://x", source_type=SourceType.URL,
                duration=3661, author="Chaine",
            )
        )
        assert page.info_title.text() == "Ma video"
        assert page.info_duration.text() == "01:01:01"
        assert page.btn_transcribe.isEnabled()

    def test_action_ia_sans_cle_avertit(self, qapp, repository, tmp_path) -> None:
        from transcribe_ai.ui.pages.transcribe import TranscribePage

        settings = Settings(_env_file=None, data_dir=str(tmp_path / "d"))
        pipeline = TranscriptionPipeline(
            engine=MockTranscriptionEngine(),
            processor=FakeProcessor(configured=False),
            settings=settings,
        )
        page = TranscribePage(pipeline, repository, TaskRunner())
        page.editor.set_text("du texte", keep_undo=False)
        messages = []
        page.notify.connect(lambda m, v: messages.append((m, v)))
        page.run_ai_action("clean", "")
        assert messages and messages[-1][1] == "warning"

    def test_historique_liste_et_selectionne(self, qapp, repository) -> None:
        from transcribe_ai.ui.pages.history import HistoryPage

        repository.add(TranscriptionRecord(title="Video A", word_count=10))
        repository.add(TranscriptionRecord(title="Video B", word_count=20))
        page = HistoryPage(repository)
        page.refresh()
        assert page.table.rowCount() == 2
        page.table.selectRow(0)
        assert page.selected_record() is not None

    def test_historique_recherche(self, qapp, repository) -> None:
        from transcribe_ai.ui.pages.history import HistoryPage

        repository.add(TranscriptionRecord(title="Cours Python"))
        repository.add(TranscriptionRecord(title="Recette"))
        page = HistoryPage(repository)
        page.search_input.setText("python")
        assert page.table.rowCount() == 1

    def test_lot_ajoute_des_sources_sans_doublon(self, qapp, pipeline, repository) -> None:
        from transcribe_ai.ui.pages.batch import BatchPage

        page = BatchPage(pipeline, repository, TaskRunner())
        page.input.setText("https://a/1\nhttps://a/2\nhttps://a/1")
        page.add_url()
        assert page.sources == ["https://a/1", "https://a/2"]
        assert page.table.rowCount() == 2

    def test_lot_progression_globale(self, qapp, pipeline, repository) -> None:
        from transcribe_ai.ui.pages.batch import BatchPage

        page = BatchPage(pipeline, repository, TaskRunner())
        page.add_source("https://a/1")
        page._on_progress(
            0, ProgressEvent(stage=PipelineStage.TRANSCRIBE, percent=100.0, message="ok")
        )
        # 4 etapes sur 6 achevees ≈ 66 %
        assert 60 <= page.table.cellWidget(0, 1).value() <= 70

    def test_a_propos_ne_revele_pas_la_cle(self, qapp, fake_api_key, monkeypatch) -> None:
        from PySide6.QtWidgets import QLabel

        from transcribe_ai.config.settings import get_settings
        from transcribe_ai.ui.pages.about import AboutPage

        monkeypatch.setenv("OPENROUTER_API_KEY", fake_api_key)
        get_settings.cache_clear()
        page = AboutPage()
        texts = " ".join(label.text() for label in page.findChildren(QLabel))
        assert fake_api_key not in texts
        assert "***" in texts or "sk-or-" in texts  # la cle apparait masquee


# --------------------------------------------------------------------------- #
# Parametres (Phase 13)
# --------------------------------------------------------------------------- #
class TestSettingsPage:
    def test_ecriture_du_env_preserve_les_autres_cles(self, tmp_path, monkeypatch) -> None:
        env = tmp_path / ".env"
        env.write_text("# commentaire\nAUTRE=valeur\nOPENROUTER_MODEL=ancien\n", encoding="utf-8")
        monkeypatch.setattr(
            "transcribe_ai.ui.pages.settings_page.env_path", lambda: env
        )
        write_env({"OPENROUTER_MODEL": "nouveau", "AI_TEMPERATURE": "0.5"})
        content = env.read_text(encoding="utf-8")
        assert "# commentaire" in content
        assert "AUTRE=valeur" in content
        assert "OPENROUTER_MODEL=nouveau" in content
        assert "AI_TEMPERATURE=0.5" in content
        assert "ancien" not in content

    def test_formulaire_charge_les_parametres(self, qapp, monkeypatch, fake_api_key) -> None:
        from transcribe_ai.ui.pages.settings_page import SettingsPage

        monkeypatch.setenv("OPENROUTER_MODEL", "vendor/modele-test")
        monkeypatch.setenv("AI_TEMPERATURE", "0.42")
        page = SettingsPage(TaskRunner())
        assert page.model_box.currentText() == "vendor/modele-test"
        assert page.temperature_spin.value() == pytest.approx(0.42)

    def test_cle_api_masquee_par_defaut(self, qapp) -> None:
        from PySide6.QtWidgets import QLineEdit

        from transcribe_ai.ui.pages.settings_page import SettingsPage

        page = SettingsPage(TaskRunner())
        assert page.api_key_input.echoMode() == QLineEdit.EchoMode.Password
        page.btn_reveal.setChecked(True)
        assert page.api_key_input.echoMode() == QLineEdit.EchoMode.Normal

    def test_test_de_connexion_sans_cle(self, qapp) -> None:
        from transcribe_ai.ui.pages.settings_page import SettingsPage

        page = SettingsPage(TaskRunner())
        page.api_key_input.setText("")
        page.test_connection()
        assert "manquante" in page.test_badge.text().lower()

    def test_modele_librement_editable(self, qapp) -> None:
        """Aucun modele n'est impose : le champ accepte n'importe quelle valeur."""
        from transcribe_ai.ui.pages.settings_page import SettingsPage

        page = SettingsPage(TaskRunner())
        assert page.model_box.isEditable()
        page.model_box.setCurrentText("vendor/modele-exotique")
        assert page.collect()["OPENROUTER_MODEL"] == "vendor/modele-exotique"


# --------------------------------------------------------------------------- #
# Fenetre principale
# --------------------------------------------------------------------------- #
class TestMainWindow:
    @pytest.fixture
    def window(self, qapp, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path / "app"))
        from transcribe_ai.config.settings import get_settings

        get_settings.cache_clear()
        from transcribe_ai.ui.main_window import MainWindow

        return MainWindow()

    def test_six_pages_enregistrees(self, window) -> None:
        assert set(window.pages) == {
            "home", "transcribe", "batch", "history", "settings", "about"
        }

    def test_navigation(self, window) -> None:
        for key, page in window.pages.items():
            window.navigate(key)
            assert window.stack.currentWidget() is page
            assert window.sidebar.buttons[key].isChecked()

    def test_changement_de_theme(self, window) -> None:
        window.apply_theme("light")
        light = window.styleSheet()
        window.apply_theme("dark")
        assert window.styleSheet() != light

    def test_notification(self, window) -> None:
        window.notify("Message de test", "success")
        assert window.toasts._toasts

    def test_ouverture_dune_entree_dhistorique(self, window) -> None:
        record = window.repository.add(
            TranscriptionRecord(title="Ancienne", text="contenu enregistre", url="https://x")
        )
        window._open_record(record)
        assert window.stack.currentWidget() is window.transcribe_page
        assert window.transcribe_page.editor.text() == "contenu enregistre"
