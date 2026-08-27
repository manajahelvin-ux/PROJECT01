"""Page d'accueil : point de depart et statistiques d'usage."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from transcribe_ai import __version__
from transcribe_ai.io.database import HistoryRepository
from transcribe_ai.ui.widgets.components import Card, StatCard, primary_button
from transcribe_ai.utils.timecode import format_duration


class HomePage(QWidget):
    """Accueil : raccourcis vers les actions principales et chiffres cles."""

    navigate = Signal(str)

    def __init__(self, repository: HistoryRepository, parent: QWidget | None = None):
        super().__init__(parent)
        self.repository = repository

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)

        title = QLabel("TRANSCRIBE AI")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Transcrivez vos videos et fichiers audio, puis laissez l'IA nettoyer, "
            "structurer et resumer le resultat."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        # -- statistiques -------------------------------------------------
        stats_row = QGridLayout()
        stats_row.setSpacing(14)
        self.stat_count = StatCard("0", "Transcriptions")
        self.stat_words = StatCard("0", "Mots transcrits")
        self.stat_duration = StatCard("00:00:00", "Duree traitee")
        self.stat_ai = StatCard("0", "Appels IA")
        for column, card in enumerate(
            (self.stat_count, self.stat_words, self.stat_duration, self.stat_ai)
        ):
            stats_row.addWidget(card, 0, column)
        layout.addLayout(stats_row)

        # -- actions --------------------------------------------------------
        actions = Card(
            "Demarrer",
            "Choisissez une source : lien video, fichier local ou traitement par lot.",
        )
        buttons = QHBoxLayout()
        buttons.setSpacing(12)

        new_button = primary_button("Nouvelle transcription")
        new_button.clicked.connect(lambda: self.navigate.emit("transcribe"))
        batch_button = primary_button("Traitement par lot")
        batch_button.setObjectName("")  # bouton secondaire
        batch_button.clicked.connect(lambda: self.navigate.emit("batch"))
        history_button = primary_button("Ouvrir l'historique")
        history_button.setObjectName("")
        history_button.clicked.connect(lambda: self.navigate.emit("history"))

        for button in (new_button, batch_button, history_button):
            buttons.addWidget(button)
        buttons.addStretch(1)
        actions.add_layout(buttons)
        layout.addWidget(actions)

        # -- rappel du fonctionnement ---------------------------------------
        pipeline = Card("Comment ca marche")
        steps = QLabel(
            "1. Coller une URL ou importer un fichier\n"
            "2. Analyser la source\n"
            "3. Extraire l'audio (WAV 16 kHz)\n"
            "4. Transcrire avec le moteur local\n"
            "5. Nettoyer et resumer avec OpenRouter\n"
            "6. Editer puis exporter en TXT, DOCX, SRT ou VTT"
        )
        steps.setObjectName("Muted")
        pipeline.add(steps)
        layout.addWidget(pipeline)

        layout.addStretch(1)
        footer = QLabel(f"Version {__version__}")
        footer.setObjectName("Muted")
        footer.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(footer)

    def refresh(self) -> None:
        """Recharge les compteurs depuis la base."""
        try:
            stats = self.repository.stats()
        except Exception:
            return
        self.stat_count.set_value(str(stats["count"]))
        self.stat_words.set_value(f"{int(stats['words']):,}".replace(",", " "))
        self.stat_duration.set_value(format_duration(float(stats["duration"])))
        self.stat_ai.set_value(str(stats["ai_calls"]))
