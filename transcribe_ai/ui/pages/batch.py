"""Phase 12 - traitement par lot : plusieurs sources traitees independamment."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from transcribe_ai.config.settings import (
    AUDIO_EXTENSIONS,
    SUPPORTED_LANGUAGES,
    VIDEO_EXTENSIONS,
    get_settings,
)
from transcribe_ai.core.models import JobStatus, TranscriptionJob
from transcribe_ai.core.pipeline.orchestrator import TranscriptionPipeline
from transcribe_ai.io.database import HistoryRepository
from transcribe_ai.ui.pages.transcribe import AI_MODE_LABELS
from transcribe_ai.ui.widgets.components import Badge, Card, primary_button
from transcribe_ai.ui.widgets.workers import TaskRunner
from transcribe_ai.utils.logging_config import get_logger

logger = get_logger(__name__)

STATUS_VARIANT = {
    JobStatus.PENDING: ("En attente", "neutral"),
    JobStatus.COMPLETED: ("Termine", "success"),
    JobStatus.FAILED: ("Echec", "danger"),
    JobStatus.CANCELLED: ("Annule", "warning"),
}


class BatchPage(QWidget):
    """File d'attente : chaque source est traitee dans son propre worker."""

    notify = Signal(str, str)

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
        self.sources: list[str] = []
        self.workers: dict[int, object] = {}
        self._finished = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        title = QLabel("Traitement par lot")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Ajoutez plusieurs URLs ou fichiers : chacun est traite independamment.")
        subtitle.setObjectName("PageSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        # -- ajout de sources ---------------------------------------------
        card = Card("Sources")
        row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText(
            "Collez une URL puis « Ajouter » (ou plusieurs, une par ligne)"
        )
        self.input.returnPressed.connect(self.add_url)
        btn_add = QPushButton("+ Ajouter une URL")
        btn_add.clicked.connect(self.add_url)
        btn_files = QPushButton("+ Ajouter des fichiers")
        btn_files.clicked.connect(self.add_files)
        row.addWidget(self.input, 1)
        row.addWidget(btn_add)
        row.addWidget(btn_files)
        card.add_layout(row)

        options = QHBoxLayout()
        self.language_box = QComboBox()
        for code, label in SUPPORTED_LANGUAGES.items():
            self.language_box.addItem(label, code)
        self.ai_mode_box = QComboBox()
        for label, mode in AI_MODE_LABELS:
            self.ai_mode_box.addItem(label, mode.value)
        self.ai_mode_box.setCurrentIndex(
            max(self.ai_mode_box.findData(get_settings().ai_mode.value), 0)
        )
        options.addWidget(QLabel("Langue :"))
        options.addWidget(self.language_box)
        options.addWidget(QLabel("Traitement IA :"))
        options.addWidget(self.ai_mode_box)
        options.addStretch(1)
        card.add_layout(options)
        layout.addWidget(card)

        # -- file d'attente -------------------------------------------------
        queue_card = Card("File d'attente")
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Source", "Progression", "Etat", "Detail"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(1, 160)
        queue_card.add(self.table)

        actions = QHBoxLayout()
        self.btn_start = primary_button("Lancer le lot")
        self.btn_start.clicked.connect(self.start_batch)
        self.btn_cancel = QPushButton("Tout annuler")
        self.btn_cancel.setObjectName("Danger")
        self.btn_cancel.clicked.connect(self.cancel_all)
        self.btn_clear = QPushButton("Vider la liste")
        self.btn_clear.clicked.connect(self.clear_queue)
        actions.addWidget(self.btn_start)
        actions.addWidget(self.btn_cancel)
        actions.addWidget(self.btn_clear)
        actions.addStretch(1)
        self.summary = QLabel("0 source")
        self.summary.setObjectName("Muted")
        actions.addWidget(self.summary)
        queue_card.add_layout(actions)
        layout.addWidget(queue_card, 1)

    # ------------------------------------------------------------------ #
    def add_source(self, source: str) -> None:
        source = source.strip()
        if not source or source in self.sources:
            return
        self.sources.append(source)
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(source))
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(0)
        bar.setTextVisible(False)
        self.table.setCellWidget(row, 1, bar)
        badge = Badge("En attente", "neutral")
        self.table.setCellWidget(row, 2, badge)
        self.table.setItem(row, 3, QTableWidgetItem(""))
        self._update_summary()

    def add_url(self) -> None:
        raw = self.input.text()
        for line in raw.replace(",", "\n").splitlines():
            self.add_source(line)
        self.input.clear()

    def add_files(self) -> None:
        patterns = " ".join(f"*{e}" for e in VIDEO_EXTENSIONS + AUDIO_EXTENSIONS)
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Ajouter des fichiers", "", f"Medias ({patterns});;Tous les fichiers (*)"
        )
        for path in paths:
            self.add_source(path)

    def clear_queue(self) -> None:
        if self.workers:
            self.notify.emit("Un lot est en cours : annulez-le avant de vider la liste.", "warning")
            return
        self.sources.clear()
        self.table.setRowCount(0)
        self._update_summary()

    # ------------------------------------------------------------------ #
    def start_batch(self) -> None:
        if not self.sources:
            self.notify.emit("Ajoutez au moins une source.", "warning")
            return
        if self.workers:
            self.notify.emit("Un lot est deja en cours.", "warning")
            return
        self._finished = 0
        language = self.language_box.currentData()
        ai_mode = self.ai_mode_box.currentData()

        for row, source in enumerate(self.sources):
            job = self.pipeline.create_job(source, language=language, ai_mode=ai_mode)
            worker = self.runner.submit(self.pipeline.run, job)
            self.workers[row] = worker
            worker.signals.progress.connect(lambda event, r=row: self._on_progress(r, event))
            worker.signals.finished.connect(lambda j, r=row: self._on_finished(r, j))
            worker.signals.failed.connect(lambda message, r=row: self._on_failed(r, message))
            worker.signals.done.connect(lambda r=row: self._on_done(r))
            self._set_badge(row, "En cours", "info")
        self.btn_start.setEnabled(False)
        self.notify.emit(f"Lot demarre : {len(self.sources)} source(s).", "info")

    def cancel_all(self) -> None:
        for worker in self.workers.values():
            worker.cancel()  # type: ignore[attr-defined]
        self.notify.emit("Annulation du lot demandee.", "warning")

    # ------------------------------------------------------------------ #
    def _on_progress(self, row: int, event) -> None:
        stages = list(type(event.stage))
        # Progression globale : etape courante + avancement dans l'etape.
        overall = (stages.index(event.stage) + event.percent / 100.0) / len(stages) * 100.0
        bar = self.table.cellWidget(row, 1)
        if bar is not None:
            bar.setValue(int(overall))
        self._set_detail(row, event.message)

    def _on_finished(self, row: int, job: TranscriptionJob) -> None:
        try:
            self.repository.save_job(job)
        except Exception as exc:
            logger.warning("Historique non mis a jour : %s", exc)
        bar = self.table.cellWidget(row, 1)
        if bar is not None:
            bar.setValue(100)
        self._set_badge(row, "Termine", "success")
        words = job.transcription.word_count if job.transcription else 0
        self._set_detail(row, f"{words} mots")

    def _on_failed(self, row: int, message: str) -> None:
        self._set_badge(row, "Echec", "danger")
        self._set_detail(row, message)

    def _on_done(self, row: int) -> None:
        self.workers.pop(row, None)
        self._finished += 1
        self._update_summary()
        if not self.workers:
            self.btn_start.setEnabled(True)
            self.notify.emit("Traitement par lot termine.", "success")

    def _set_badge(self, row: int, text: str, variant: str) -> None:
        badge = self.table.cellWidget(row, 2)
        if badge is not None:
            badge.set_status(text, variant)

    def _set_detail(self, row: int, text: str) -> None:
        item = self.table.item(row, 3)
        if item is not None:
            item.setText(text)

    def _update_summary(self) -> None:
        self.summary.setText(
            f"{len(self.sources)} source(s) — {self._finished} traitee(s)"
        )
