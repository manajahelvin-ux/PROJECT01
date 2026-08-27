"""Fenetre principale : sidebar de navigation et pile de pages."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from transcribe_ai import __app_name__, __version__
from transcribe_ai.config.settings import get_settings
from transcribe_ai.core.pipeline.orchestrator import TranscriptionPipeline
from transcribe_ai.io.database import Database, HistoryRepository
from transcribe_ai.ui.pages.about import AboutPage
from transcribe_ai.ui.pages.batch import BatchPage
from transcribe_ai.ui.pages.history import HistoryPage
from transcribe_ai.ui.pages.home import HomePage
from transcribe_ai.ui.pages.settings_page import SettingsPage
from transcribe_ai.ui.pages.transcribe import TranscribePage
from transcribe_ai.ui.theme.styles import build_stylesheet
from transcribe_ai.ui.widgets.components import ToastManager
from transcribe_ai.ui.widgets.workers import TaskRunner
from transcribe_ai.utils.logging_config import get_logger

logger = get_logger(__name__)

#: Symboles volontairement issus du plan multilingue de base : ils sont
#: presents dans les polices systeme de Windows, macOS et Linux, la ou les
#: emojis colores ne le sont pas toujours.
NAV_ITEMS: list[tuple[str, str]] = [
    ("home", "\u2302    Accueil"),
    ("transcribe", "\u270E    Transcrire"),
    ("batch", "\u25A4    Traitement par lot"),
    ("history", "\u2261    Historique"),
    ("settings", "\u2699    Parametres"),
    ("about", "i     A propos"),
]


class Sidebar(QWidget):
    """Barre laterale de navigation."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(230)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        logo = QLabel("TRANSCRIBE AI")
        logo.setObjectName("SidebarLogo")
        version = QLabel(f"v{__version__}")
        version.setObjectName("SidebarVersion")
        layout.addWidget(logo)
        layout.addWidget(version)

        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons: dict[str, QPushButton] = {}
        for index, (key, label) in enumerate(NAV_ITEMS):
            button = QPushButton(label)
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.group.addButton(button, index)
            self.buttons[key] = button
            layout.addWidget(button)

        layout.addStretch(1)


class MainWindow(QMainWindow):
    """Assemble les services applicatifs et les pages."""

    def __init__(self) -> None:
        super().__init__()
        self.settings = get_settings()
        self.setWindowTitle(f"{__app_name__} — transcription assistee par IA")
        self.resize(1180, 800)
        self.setMinimumSize(960, 640)

        # -- services partages ---------------------------------------------
        self.runner = TaskRunner()
        self.repository = HistoryRepository(Database(self.settings.resolved_database_url))
        self.pipeline = TranscriptionPipeline(settings=self.settings)
        self.toasts = ToastManager(self)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sidebar = Sidebar()
        layout.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)

        # -- pages -----------------------------------------------------------
        self.home_page = HomePage(self.repository)
        self.transcribe_page = TranscribePage(self.pipeline, self.repository, self.runner)
        self.batch_page = BatchPage(self.pipeline, self.repository, self.runner)
        self.history_page = HistoryPage(self.repository)
        self.settings_page = SettingsPage(self.runner)
        self.about_page = AboutPage()

        self.pages: dict[str, QWidget] = {
            "home": self.home_page,
            "transcribe": self.transcribe_page,
            "batch": self.batch_page,
            "history": self.history_page,
            "settings": self.settings_page,
            "about": self.about_page,
        }
        for page in self.pages.values():
            self.stack.addWidget(page)

        self._connect()
        self.apply_theme(self.settings.ui_theme.value)
        self.navigate("home")

    # ------------------------------------------------------------------ #
    def _connect(self) -> None:
        for key, button in self.sidebar.buttons.items():
            button.clicked.connect(lambda _=False, k=key: self.navigate(k))

        self.home_page.navigate.connect(self.navigate)
        for page in (self.transcribe_page, self.batch_page, self.history_page,
                     self.settings_page):
            page.notify.connect(self.notify)

        self.transcribe_page.job_completed.connect(lambda _: self._refresh_data())
        self.history_page.open_requested.connect(self._open_record)
        self.settings_page.settings_saved.connect(self._on_settings_saved)
        self.settings_page.theme_changed.connect(self.apply_theme)

    def navigate(self, key: str) -> None:
        page = self.pages.get(key)
        if page is None:
            return
        self.stack.setCurrentWidget(page)
        button = self.sidebar.buttons.get(key)
        if button is not None:
            button.setChecked(True)
        if key == "home":
            self.home_page.refresh()
        elif key == "history":
            self.history_page.refresh()

    def notify(self, message: str, variant: str = "info") -> None:
        self.toasts.show(message, variant)

    def apply_theme(self, theme: str) -> None:
        self.setStyleSheet(build_stylesheet(theme))

    # ------------------------------------------------------------------ #
    def _refresh_data(self) -> None:
        self.home_page.refresh()
        self.history_page.refresh()

    def _open_record(self, record) -> None:
        self.transcribe_page.load_record(record)
        self.navigate("transcribe")
        self.notify(f"Transcription « {record.title} » ouverte.", "info")

    def _on_settings_saved(self) -> None:
        self.settings = get_settings()
        self.pipeline = TranscriptionPipeline(settings=self.settings)
        self.transcribe_page.pipeline = self.pipeline
        self.batch_page.pipeline = self.pipeline
        self.transcribe_page.refresh_settings()
        self.apply_theme(self.settings.ui_theme.value)

    def resizeEvent(self, event) -> None:  # noqa: N802 - signature Qt
        super().resizeEvent(event)
        self.toasts._reposition()

    def closeEvent(self, event) -> None:  # noqa: N802 - signature Qt
        logger.info("Fermeture de l'application")
        self.runner.pool.clear()
        event.accept()
