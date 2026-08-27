"""Amorcage de l'application graphique."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from transcribe_ai import __app_name__, __version__
from transcribe_ai.config.paths import app_paths
from transcribe_ai.utils.logging_config import get_logger

logger = get_logger(__name__)


def create_app(argv: list[str] | None = None) -> QApplication:
    """Cree (ou reutilise) l'instance QApplication configuree."""
    existing = QApplication.instance()
    if isinstance(existing, QApplication):
        return existing
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(__app_name__)
    app.setApplicationVersion(__version__)
    app.setOrganizationName("TranscribeAI")
    app.setFont(QFont("Segoe UI", 10))
    icon = app_paths().resources / "icons" / "app.png"
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))
    return app


def run_app(argv: list[str] | None = None) -> int:
    """Lance la fenetre principale et entre dans la boucle evenementielle."""
    from transcribe_ai.ui.main_window import MainWindow

    app = create_app(argv)
    window = MainWindow()
    window.show()
    logger.info("Interface demarree")
    return app.exec()
