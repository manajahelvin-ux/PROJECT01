"""Phase 13 - page Parametres : IA, transcription, interface.

Les modifications sont ecrites dans le fichier `.env` du projet, ce qui
permet de changer de modele, de cle ou de moteur sans toucher au code.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from transcribe_ai.config.settings import (
    SUPPORTED_LANGUAGES,
    AIMode,
    Theme,
    get_settings,
    reload_settings,
)
from transcribe_ai.core.ai.chunking import ChunkCache
from transcribe_ai.core.ai.openrouter_service import OpenRouterService
from transcribe_ai.core.engines.whisper_engine import ENGINES
from transcribe_ai.ui.widgets.components import Badge, Card, primary_button
from transcribe_ai.ui.widgets.workers import TaskRunner
from transcribe_ai.utils.diagnostics import run_diagnostics
from transcribe_ai.utils.logging_config import get_logger

logger = get_logger(__name__)

WHISPER_MODELS = ["tiny", "base", "small", "medium", "large-v3"]

#: Suggestions courantes ; le champ reste libre, aucun modele n'est impose.
MODEL_SUGGESTIONS = [
    "openai/gpt-4o-mini",
    "openai/gpt-4o",
    "anthropic/claude-3.5-sonnet",
    "google/gemini-flash-1.5",
    "meta-llama/llama-3.1-70b-instruct",
    "mistralai/mistral-large",
    "deepseek/deepseek-chat",
]


def env_path() -> Path:
    return Path(__file__).resolve().parents[3] / ".env"


def write_env(values: dict[str, str]) -> Path:
    """Met a jour le fichier `.env` en preservant les lignes existantes."""
    path = env_path()
    lines: list[str] = []
    seen: set[str] = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                lines.append(line)
                continue
            key = stripped.split("=", 1)[0].strip()
            if key in values:
                lines.append(f"{key}={values[key]}")
                seen.add(key)
            else:
                lines.append(line)
    for key, value in values.items():
        if key not in seen:
            lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


class SettingsPage(QWidget):
    """Formulaire de configuration complet."""

    notify = Signal(str, str)
    settings_saved = Signal()
    theme_changed = Signal(str)

    def __init__(self, runner: TaskRunner, parent: QWidget | None = None):
        super().__init__(parent)
        self.runner = runner

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        container = QWidget()
        scroll.setWidget(container)
        outer.addWidget(scroll)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        title = QLabel("Parametres")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        layout.addWidget(self._build_ai_card())
        layout.addWidget(self._build_transcription_card())
        layout.addWidget(self._build_ui_card())
        layout.addWidget(self._build_diagnostic_card())

        actions = QHBoxLayout()
        self.btn_save = primary_button("Enregistrer les parametres")
        self.btn_save.clicked.connect(self.save)
        self.btn_reload = QPushButton("Recharger")
        self.btn_reload.clicked.connect(self.load)
        actions.addWidget(self.btn_save)
        actions.addWidget(self.btn_reload)
        actions.addStretch(1)
        layout.addLayout(actions)
        layout.addStretch(1)

        self.load()

    # ------------------------------------------------------------------ #
    def _build_ai_card(self) -> Card:
        card = Card(
            "Intelligence artificielle",
            "La cle API n'est jamais affichee en clair ni ecrite dans les journaux.",
        )
        form = QFormLayout()
        form.setSpacing(10)

        self.provider_box = QComboBox()
        self.provider_box.addItem("OpenRouter", "openrouter")

        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("sk-or-v1-…")
        self.btn_reveal = QPushButton("Afficher")
        self.btn_reveal.setCheckable(True)
        self.btn_reveal.toggled.connect(self._toggle_key_visibility)
        key_row = QHBoxLayout()
        key_row.addWidget(self.api_key_input, 1)
        key_row.addWidget(self.btn_reveal)
        key_widget = QWidget()
        key_widget.setLayout(key_row)

        self.model_box = QComboBox()
        self.model_box.setEditable(True)   # aucun modele code en dur
        self.model_box.addItems(MODEL_SUGGESTIONS)

        self.temperature_spin = QDoubleSpinBox()
        self.temperature_spin.setRange(0.0, 2.0)
        self.temperature_spin.setSingleStep(0.1)
        self.temperature_spin.setDecimals(2)

        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(256, 200_000)
        self.max_tokens_spin.setSingleStep(256)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(5, 1800)
        self.timeout_spin.setSuffix(" s")

        self.retries_spin = QSpinBox()
        self.retries_spin.setRange(0, 10)

        self.chunk_spin = QSpinBox()
        self.chunk_spin.setRange(500, 100_000)
        self.chunk_spin.setSingleStep(500)
        self.chunk_spin.setSuffix(" caracteres")

        self.ai_mode_box = QComboBox()
        for mode, label in (
            (AIMode.NONE, "Aucun"),
            (AIMode.CLEAN, "Nettoyage"),
            (AIMode.CLEAN_SUMMARY, "Nettoyage + resume"),
            (AIMode.FULL, "Analyse complete"),
        ):
            self.ai_mode_box.addItem(label, mode.value)

        form.addRow("Fournisseur :", self.provider_box)
        form.addRow("Cle API :", key_widget)
        form.addRow("Modele :", self.model_box)
        form.addRow("Temperature :", self.temperature_spin)
        form.addRow("Max tokens :", self.max_tokens_spin)
        form.addRow("Timeout :", self.timeout_spin)
        form.addRow("Tentatives :", self.retries_spin)
        form.addRow("Taille des blocs :", self.chunk_spin)
        form.addRow("Traitement par defaut :", self.ai_mode_box)
        card.add_layout(form)

        test_row = QHBoxLayout()
        self.btn_test = primary_button("Tester la connexion")
        self.btn_test.clicked.connect(self.test_connection)
        self.test_badge = Badge("Non teste", "neutral")
        self.btn_clear_cache = QPushButton("Vider le cache IA")
        self.btn_clear_cache.clicked.connect(self.clear_cache)
        test_row.addWidget(self.btn_test)
        test_row.addWidget(self.test_badge)
        test_row.addWidget(self.btn_clear_cache)
        test_row.addStretch(1)
        card.add_layout(test_row)

        self.test_result = QLabel("")
        self.test_result.setObjectName("Muted")
        self.test_result.setWordWrap(True)
        card.add(self.test_result)
        return card

    def _build_transcription_card(self) -> Card:
        card = Card("Transcription")
        form = QFormLayout()
        form.setSpacing(10)
        self.engine_box = QComboBox()
        for name in ENGINES:
            self.engine_box.addItem(name, name)
        self.whisper_model_box = QComboBox()
        self.whisper_model_box.addItems(WHISPER_MODELS)
        self.language_box = QComboBox()
        for code, label in SUPPORTED_LANGUAGES.items():
            self.language_box.addItem(label, code)
        self.ffmpeg_input = QLineEdit()
        self.ffmpeg_input.setPlaceholderText("Laisser vide pour la detection automatique")
        form.addRow("Moteur :", self.engine_box)
        form.addRow("Modele Whisper :", self.whisper_model_box)
        form.addRow("Langue par defaut :", self.language_box)
        form.addRow("Chemin FFmpeg :", self.ffmpeg_input)
        card.add_layout(form)
        return card

    def _build_ui_card(self) -> Card:
        card = Card("Interface")
        form = QFormLayout()
        self.theme_box = QComboBox()
        for theme, label in ((Theme.DARK, "Sombre"), (Theme.LIGHT, "Clair")):
            self.theme_box.addItem(label, theme.value)
        self.theme_box.currentIndexChanged.connect(
            lambda: self.theme_changed.emit(self.theme_box.currentData())
        )
        self.log_box = QComboBox()
        self.log_box.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        form.addRow("Theme :", self.theme_box)
        form.addRow("Niveau de journalisation :", self.log_box)
        card.add_layout(form)
        return card

    def _build_diagnostic_card(self) -> Card:
        card = Card("Diagnostic de l'environnement")
        self.diagnostic_label = QLabel("")
        self.diagnostic_label.setObjectName("Muted")
        self.diagnostic_label.setWordWrap(True)
        card.add(self.diagnostic_label)
        button = QPushButton("Relancer le diagnostic")
        button.clicked.connect(self.run_diagnostic)
        card.add(button)
        return card

    # ------------------------------------------------------------------ #
    def _toggle_key_visibility(self, visible: bool) -> None:
        self.api_key_input.setEchoMode(
            QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        )
        self.btn_reveal.setText("Masquer" if visible else "Afficher")

    def load(self) -> None:
        """Charge les valeurs courantes dans le formulaire."""
        settings = reload_settings()
        self.api_key_input.setText(settings.api_key_value())
        self.model_box.setCurrentText(settings.openrouter_model)
        self.temperature_spin.setValue(settings.ai_temperature)
        self.max_tokens_spin.setValue(settings.ai_max_tokens)
        self.timeout_spin.setValue(int(settings.ai_timeout))
        self.retries_spin.setValue(settings.ai_max_retries)
        self.chunk_spin.setValue(settings.chunk_size)
        self.ai_mode_box.setCurrentIndex(max(self.ai_mode_box.findData(settings.ai_mode.value), 0))
        self.engine_box.setCurrentIndex(
            max(self.engine_box.findData(settings.transcription_engine), 0)
        )
        self.whisper_model_box.setCurrentText(settings.whisper_model)
        self.language_box.setCurrentIndex(
            max(self.language_box.findData(settings.default_language), 0)
        )
        self.ffmpeg_input.setText(settings.ffmpeg_path)
        self.theme_box.setCurrentIndex(max(self.theme_box.findData(settings.ui_theme.value), 0))
        self.log_box.setCurrentText(settings.log_level)
        self.run_diagnostic()

    def collect(self) -> dict[str, str]:
        """Valeurs du formulaire, pretes a etre ecrites dans `.env`."""
        return {
            "OPENROUTER_API_KEY": self.api_key_input.text().strip(),
            "OPENROUTER_MODEL": self.model_box.currentText().strip(),
            "AI_TEMPERATURE": str(self.temperature_spin.value()),
            "AI_MAX_TOKENS": str(self.max_tokens_spin.value()),
            "AI_TIMEOUT": str(self.timeout_spin.value()),
            "AI_MAX_RETRIES": str(self.retries_spin.value()),
            "CHUNK_SIZE": str(self.chunk_spin.value()),
            "AI_MODE": str(self.ai_mode_box.currentData()),
            "TRANSCRIPTION_ENGINE": str(self.engine_box.currentData()),
            "WHISPER_MODEL": self.whisper_model_box.currentText(),
            "DEFAULT_LANGUAGE": str(self.language_box.currentData()),
            "FFMPEG_PATH": self.ffmpeg_input.text().strip(),
            "UI_THEME": str(self.theme_box.currentData()),
            "LOG_LEVEL": self.log_box.currentText(),
        }

    def save(self) -> None:
        values = self.collect()
        try:
            path = write_env(values)
        except OSError as exc:
            self.notify.emit(f"Ecriture du fichier .env impossible : {exc}", "error")
            return
        # Les variables d'environnement priment sur le .env : on les aligne.
        import os

        for key, value in values.items():
            os.environ[key] = value
        reload_settings()
        logger.info("Parametres enregistres dans %s", path.name)  # jamais la cle
        self.notify.emit("Parametres enregistres.", "success")
        self.settings_saved.emit()
        self.run_diagnostic()

    # ------------------------------------------------------------------ #
    def test_connection(self) -> None:
        key = self.api_key_input.text().strip()
        if not key:
            self.test_badge.set_status("Cle manquante", "warning")
            self.test_result.setText("Renseignez votre cle API OpenRouter.")
            return
        from transcribe_ai.config.settings import Settings

        settings = Settings(
            _env_file=None,
            openrouter_api_key=key,
            openrouter_model=self.model_box.currentText().strip(),
            ai_timeout=float(self.timeout_spin.value()),
            ai_max_retries=self.retries_spin.value(),
        )
        self.btn_test.setEnabled(False)
        self.test_badge.set_status("Test en cours…", "info")

        def run() -> tuple[bool, str]:
            with OpenRouterService(settings) as service:
                return service.test_connection()

        worker = self.runner.submit(run)
        worker.signals.finished.connect(self._on_test_result)
        worker.signals.failed.connect(
            lambda message: self._on_test_result((False, message))
        )
        worker.signals.done.connect(lambda: self.btn_test.setEnabled(True))

    def _on_test_result(self, result: tuple[bool, str]) -> None:
        ok, message = result
        if ok:
            self.test_badge.set_status("✓ Connexion reussie", "success")
            self.test_result.setText(message)
        else:
            self.test_badge.set_status("✕ Connexion impossible", "danger")
            self.test_result.setText(
                f"{message}\nVerifiez votre cle API ou votre connexion Internet."
            )

    def clear_cache(self) -> None:
        removed = ChunkCache().clear()
        self.notify.emit(f"Cache IA vide : {removed} bloc(s) supprime(s).", "success")

    def run_diagnostic(self) -> None:
        report = run_diagnostics(get_settings())
        lines = []
        for check in report.checks:
            icon = "✓" if check.ok else ("!" if check.optional else "✕")
            lines.append(f"{icon}  {check.name} — {check.detail}")
        self.diagnostic_label.setText("\n".join(lines))
