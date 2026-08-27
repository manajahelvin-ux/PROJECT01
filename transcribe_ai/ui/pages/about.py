"""Page « A propos »."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from transcribe_ai import __app_name__, __version__
from transcribe_ai.config.settings import get_settings
from transcribe_ai.ui.widgets.components import Card


class AboutPage(QWidget):
    """Informations sur l'application et son environnement."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        settings = get_settings()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        title = QLabel("A propos")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        presentation = Card(f"{__app_name__} v{__version__}")
        presentation.add(
            QLabel(
                "Application desktop de transcription video et audio.\n"
                "Transcription locale par moteur compatible Whisper, "
                "post-traitement intelligent via OpenRouter."
            )
        )
        layout.addWidget(presentation)

        pipeline = Card("Pipeline")
        steps = QLabel(
            "Source (URL ou fichier) → yt-dlp → FFmpeg → WAV 16 kHz → "
            "moteur de transcription → chunking → OpenRouter → editeur → "
            "export TXT / DOCX / SRT / VTT → historique SQLite"
        )
        steps.setWordWrap(True)
        steps.setObjectName("Muted")
        pipeline.add(steps)
        layout.addWidget(pipeline)

        tech = Card("Environnement")
        details = QLabel(
            f"Moteur de transcription : {settings.transcription_engine} "
            f"(modele « {settings.whisper_model} »)\n"
            f"Modele IA : {settings.openrouter_model}\n"
            f"Cle API : {settings.masked_api_key}\n"
            f"Dossier de donnees : {settings.paths.root}\n"
            f"Base de donnees : {settings.paths.database.name}"
        )
        details.setWordWrap(True)
        details.setObjectName("Muted")
        details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        tech.add(details)
        layout.addWidget(tech)

        privacy = Card("Confidentialite")
        privacy.add(
            QLabel(
                "La transcription est realisee localement : l'audio ne quitte "
                "jamais votre machine.\nSeul le texte est transmis a OpenRouter, "
                "et uniquement si le traitement IA est active.\n"
                "La cle API est stockee dans le fichier .env et n'apparait "
                "jamais dans les journaux."
            )
        )
        layout.addWidget(privacy)

        layout.addStretch(1)
