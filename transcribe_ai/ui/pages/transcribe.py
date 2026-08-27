"""Page « Transcrire » : source, analyse, progression, editeur et exports."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from transcribe_ai.config.settings import (
    AUDIO_EXTENSIONS,
    SUPPORTED_LANGUAGES,
    VIDEO_EXTENSIONS,
    AIMode,
    get_settings,
)
from transcribe_ai.core.models import MediaInfo, TranscriptionJob
from transcribe_ai.core.pipeline.orchestrator import TranscriptionPipeline
from transcribe_ai.io.database import HistoryRepository
from transcribe_ai.io.exporters import EXPORTERS, ExportPayload, export_transcription
from transcribe_ai.ui.widgets.components import Badge, Card, PipelineProgress, primary_button
from transcribe_ai.ui.widgets.editor import ExportBar, TranscriptEditor
from transcribe_ai.ui.widgets.workers import TaskRunner
from transcribe_ai.utils.logging_config import get_logger
from transcribe_ai.utils.timecode import format_duration

logger = get_logger(__name__)

AI_MODE_LABELS: list[tuple[str, AIMode]] = [
    ("Aucun traitement IA (gratuit)", AIMode.NONE),
    ("Nettoyage", AIMode.CLEAN),
    ("Nettoyage + resume", AIMode.CLEAN_SUMMARY),
    ("Analyse complete", AIMode.FULL),
]


class TranscribePage(QWidget):
    """Ecran principal de travail."""

    notify = Signal(str, str)     # (message, variante)
    job_completed = Signal(object)

    def __init__(
        self,
        pipeline: TranscriptionPipeline,
        repository: HistoryRepository,
        runner: TaskRunner,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.pipeline = pipeline
        self.repository = repository
        self.runner = runner
        self.job: TranscriptionJob | None = None
        self.media_info: MediaInfo | None = None
        self._worker = None

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

        title = QLabel("Nouvelle transcription")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        layout.addWidget(self._build_source_card())
        layout.addWidget(self._build_options_card())
        layout.addWidget(self._build_info_card())
        self.progress = PipelineProgress()
        layout.addWidget(self.progress)
        layout.addWidget(self._build_editor_card(), 1)

    # ------------------------------------------------------------------ #
    # Construction de l'interface
    # ------------------------------------------------------------------ #
    def _build_source_card(self) -> Card:
        card = Card("Source", "URL YouTube (ou compatible), ou fichier video/audio local.")
        row = QHBoxLayout()
        row.setSpacing(8)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://www.youtube.com/watch?v=…")
        self.url_input.returnPressed.connect(self.analyze)
        self.btn_import = QPushButton("Importer un fichier")
        self.btn_import.clicked.connect(self.import_file)
        self.btn_analyze = primary_button("Analyser")
        self.btn_analyze.clicked.connect(self.analyze)
        row.addWidget(self.url_input, 1)
        row.addWidget(self.btn_import)
        row.addWidget(self.btn_analyze)
        card.add_layout(row)
        return card

    def _build_options_card(self) -> Card:
        settings = get_settings()
        card = Card("Options")
        form = QFormLayout()
        form.setSpacing(10)

        self.language_box = QComboBox()
        for code, label in SUPPORTED_LANGUAGES.items():
            self.language_box.addItem(label, code)
        self.language_box.setCurrentIndex(
            max(self.language_box.findData(settings.default_language), 0)
        )

        self.engine_label = QLabel(
            f"{settings.transcription_engine} · modele « {settings.whisper_model} »"
        )
        self.engine_label.setObjectName("Muted")

        self.ai_mode_box = QComboBox()
        for label, mode in AI_MODE_LABELS:
            self.ai_mode_box.addItem(label, mode.value)
        self.ai_mode_box.setCurrentIndex(
            max(self.ai_mode_box.findData(settings.ai_mode.value), 0)
        )

        self.ai_status = Badge("IA configuree", "success") if settings.has_api_key else Badge(
            "Cle API absente", "warning"
        )

        form.addRow("Langue :", self.language_box)
        form.addRow("Moteur :", self.engine_label)
        form.addRow("Traitement IA :", self.ai_mode_box)
        form.addRow("OpenRouter :", self.ai_status)
        card.add_layout(form)
        return card

    def _build_info_card(self) -> Card:
        card = Card("Informations sur la source")
        self.info_title = QLabel("—")
        self.info_duration = QLabel("—")
        self.info_author = QLabel("—")
        self.info_language = QLabel("—")
        form = QFormLayout()
        form.setSpacing(8)
        form.addRow("Titre :", self.info_title)
        form.addRow("Duree :", self.info_duration)
        form.addRow("Auteur :", self.info_author)
        form.addRow("Langue :", self.info_language)
        card.add_layout(form)

        actions = QHBoxLayout()
        self.btn_transcribe = primary_button("Telecharger et transcrire")
        self.btn_transcribe.setEnabled(False)
        self.btn_transcribe.clicked.connect(self.start_transcription)
        self.btn_cancel = QPushButton("Annuler")
        self.btn_cancel.setObjectName("Danger")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.cancel_transcription)
        actions.addWidget(self.btn_transcribe)
        actions.addWidget(self.btn_cancel)
        actions.addStretch(1)
        card.add_layout(actions)
        self.info_card = card
        return card

    def _build_editor_card(self) -> Card:
        card = Card()
        self.editor = TranscriptEditor()
        self.editor.ai_requested.connect(self.run_ai_action)
        self.editor.editor.setMinimumHeight(260)
        card.add(self.editor)
        self.export_bar = ExportBar()
        self.export_bar.export_requested.connect(self.export)
        card.add(self.export_bar)
        return card

    # ------------------------------------------------------------------ #
    # Actions
    # ------------------------------------------------------------------ #
    def import_file(self) -> None:
        patterns = " ".join(f"*{e}" for e in VIDEO_EXTENSIONS + AUDIO_EXTENSIONS)
        path, _ = QFileDialog.getOpenFileName(
            self, "Importer un fichier video ou audio", "",
            f"Medias ({patterns});;Tous les fichiers (*)",
        )
        if path:
            self.url_input.setText(path)
            self.analyze()

    def analyze(self) -> None:
        source = self.url_input.text().strip()
        if not source:
            self.notify.emit("Indiquez une URL ou importez un fichier.", "warning")
            return
        self.btn_analyze.setEnabled(False)
        self.btn_analyze.setText("Analyse…")
        worker = self.runner.submit(self.pipeline.analyze, source)
        worker.signals.finished.connect(self._on_analyzed)
        worker.signals.failed.connect(self._on_analyze_failed)
        worker.signals.done.connect(
            lambda: (self.btn_analyze.setEnabled(True), self.btn_analyze.setText("Analyser"))
        )

    def _on_analyzed(self, info: MediaInfo) -> None:
        self.media_info = info
        self.info_title.setText(info.title or "—")
        self.info_duration.setText(format_duration(info.duration))
        self.info_author.setText(info.author or "—")
        self.info_language.setText(info.language or "a detecter")
        self.btn_transcribe.setEnabled(True)
        self.notify.emit(f"Source analysee : {info.title}", "success")

    def _on_analyze_failed(self, message: str) -> None:
        self.media_info = None
        self.btn_transcribe.setEnabled(False)
        self.notify.emit(message, "error")

    # ------------------------------------------------------------------ #
    def start_transcription(self) -> None:
        source = self.url_input.text().strip()
        if not source:
            return
        self.progress.reset()
        self.editor.clear()
        job = self.pipeline.create_job(
            source,
            language=self.language_box.currentData(),
            ai_mode=self.ai_mode_box.currentData(),
        )
        job.media_info = self.media_info
        self.job = job

        self.btn_transcribe.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        worker = self.runner.submit(self.pipeline.run, job)
        self._worker = worker
        worker.signals.progress.connect(self.progress.apply)
        worker.signals.finished.connect(self._on_job_finished)
        worker.signals.failed.connect(self._on_job_failed)
        worker.signals.done.connect(self._on_job_done)

    def cancel_transcription(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self.notify.emit("Annulation demandee…", "warning")

    def _on_job_finished(self, job: TranscriptionJob) -> None:
        text = (
            job.ai_result.cleaned_text
            if job.ai_result and job.ai_result.cleaned_text
            else (job.transcription.text if job.transcription else "")
        )
        self.editor.set_text(text, keep_undo=False)
        try:
            self.repository.save_job(job, text)
        except Exception as exc:
            logger.warning("Enregistrement en historique impossible : %s", exc)
        usage = job.ai_result.usage if job.ai_result else None
        message = "Transcription terminee."
        if usage:
            message += f" Appels IA : {usage.calls}, blocs caches : {usage.cached_chunks}."
        self.notify.emit(message, "success")
        self.job_completed.emit(job)

    def _on_job_failed(self, message: str) -> None:
        self.notify.emit(message, "error")

    def _on_job_done(self) -> None:
        self.btn_transcribe.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self._worker = None

    # ------------------------------------------------------------------ #
    def run_ai_action(self, action: str, argument: str) -> None:
        """Actions IA declenchees depuis l'editeur."""
        text = self.editor.text().strip()
        if not text:
            self.notify.emit("Aucun texte a traiter.", "warning")
            return
        processor = self.pipeline.processor
        if not processor.is_configured():
            self.notify.emit(
                "Aucune cle API OpenRouter. Renseignez-la dans Parametres.", "warning"
            )
            return

        language = self.language_box.currentData()
        if action == "clean":
            fn, args = processor.clean, (text, language)
        elif action == "summary":
            fn, args = processor.summarize, (text, language)
        elif action == "translate":
            fn, args = processor.translate, (text, argument or "en")
        else:
            return

        self.editor.set_read_only(True)
        self.notify.emit("Traitement IA en cours…", "info")
        worker = self.runner.submit(fn, *args)
        worker.signals.finished.connect(lambda result: self._apply_ai_result(action, result))
        worker.signals.failed.connect(lambda message: self.notify.emit(message, "error"))
        worker.signals.done.connect(lambda: self.editor.set_read_only(False))

    def _apply_ai_result(self, action: str, result) -> None:
        if action == "summary":
            summary = (result.short_summary or "").strip()
            detailed = (result.detailed_summary or "").strip()
            body = self.editor.text()
            self.editor.set_text(
                f"RESUME\n\n{summary}\n\nRESUME DETAILLE\n\n{detailed}\n\n"
                f"----------\n\nTRANSCRIPTION\n\n{body}"
            )
        elif result.cleaned_text:
            self.editor.set_text(result.cleaned_text)
        if self.job is not None:
            self.job.ai_result = result
        self.notify.emit(f"Traitement IA termine ({result.usage.calls} appel(s)).", "success")

    # ------------------------------------------------------------------ #
    def export(self, fmt: str) -> None:
        text = self.editor.text().strip()
        if not text:
            self.notify.emit("Aucun texte a exporter.", "warning")
            return
        payload = (
            ExportPayload.from_job(self.job)
            if self.job is not None
            else ExportPayload(text=text, title="Transcription")
        )
        payload.text = text  # l'utilisateur peut avoir corrige le texte

        exporter = EXPORTERS[fmt]
        default_dir = get_settings().paths.exports / payload.default_filename(fmt)
        path, _ = QFileDialog.getSaveFileName(
            self, f"Exporter en {fmt.upper()}", str(default_dir), f"{exporter.label} (*.{fmt})"
        )
        if not path:
            return
        try:
            export_transcription(payload, Path(path), fmt)
        except Exception as exc:
            user_message = getattr(exc, "user_message", str(exc))
            QMessageBox.critical(self, "Export impossible", user_message)
            return
        self.notify.emit(f"Export {fmt.upper()} : {Path(path).name}", "success")

    # ------------------------------------------------------------------ #
    def load_record(self, record) -> None:
        """Ouvre une transcription de l'historique dans l'editeur."""
        self.url_input.setText(record.url or "")
        self.info_title.setText(record.title or "—")
        self.info_duration.setText(format_duration(record.duration))
        self.info_author.setText(record.author or "—")
        self.info_language.setText(record.language or "—")
        self.editor.set_text(record.text or "", keep_undo=False)
        self.job = None
        self.media_info = None

    def refresh_settings(self) -> None:
        """Reprend en compte les parametres modifies dans l'onglet dedie."""
        settings = get_settings()
        self.engine_label.setText(
            f"{settings.transcription_engine} · modele « {settings.whisper_model} »"
        )
        if settings.has_api_key:
            self.ai_status.set_status("IA configuree", "success")
        else:
            self.ai_status.set_status("Cle API absente", "warning")
