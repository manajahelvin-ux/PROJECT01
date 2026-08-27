"""Page « Historique » : consultation, reouverture, export et suppression."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from transcribe_ai.config.settings import get_settings
from transcribe_ai.io.database import HistoryRepository, TranscriptionRecord
from transcribe_ai.io.exporters import EXPORTERS, ExportPayload, export_transcription
from transcribe_ai.ui.widgets.components import Card
from transcribe_ai.utils.timecode import format_duration

COLUMNS = ["Titre", "Date", "Duree", "Langue", "Mots", "Statut"]


class HistoryPage(QWidget):
    """Tableau de l'historique avec ses actions."""

    notify = Signal(str, str)
    open_requested = Signal(object)   # TranscriptionRecord

    def __init__(self, repository: HistoryRepository, parent: QWidget | None = None):
        super().__init__(parent)
        self.repository = repository
        self._records: list[TranscriptionRecord] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        title = QLabel("Historique")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        card = Card()
        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Rechercher un titre, une URL ou du contenu…")
        self.search_input.textChanged.connect(self.refresh)
        self.btn_refresh = QPushButton("Actualiser")
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_clear = QPushButton("Vider l'historique")
        self.btn_clear.setObjectName("Danger")
        self.btn_clear.clicked.connect(self.clear_all)
        search_row.addWidget(self.search_input, 1)
        search_row.addWidget(self.btn_refresh)
        search_row.addWidget(self.btn_clear)
        card.add_layout(search_row)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.doubleClicked.connect(self.open_selected)
        card.add(self.table)

        actions = QHBoxLayout()
        self.btn_open = QPushButton("Ouvrir")
        self.btn_open.clicked.connect(self.open_selected)
        self.btn_export = QPushButton("Exporter")
        self.btn_export.clicked.connect(self.export_selected)
        self.btn_delete = QPushButton("Supprimer")
        self.btn_delete.setObjectName("Danger")
        self.btn_delete.clicked.connect(self.delete_selected)
        for button in (self.btn_open, self.btn_export, self.btn_delete):
            actions.addWidget(button)
        actions.addStretch(1)
        self.count_label = QLabel("0 element")
        self.count_label.setObjectName("Muted")
        actions.addWidget(self.count_label)
        card.add_layout(actions)

        layout.addWidget(card, 1)

    # ------------------------------------------------------------------ #
    def refresh(self) -> None:
        try:
            self._records = self.repository.list(search=self.search_input.text())
        except Exception as exc:
            self.notify.emit(f"Lecture de l'historique impossible : {exc}", "error")
            return
        self.table.setRowCount(len(self._records))
        for row, record in enumerate(self._records):
            values = [
                record.title or "(sans titre)",
                record.created_at.strftime("%d/%m/%Y %H:%M") if record.created_at else "—",
                format_duration(record.duration),
                record.language or "—",
                str(record.word_count),
                record.status,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column > 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, column, item)
        self.count_label.setText(f"{len(self._records)} element(s)")

    def selected_record(self) -> TranscriptionRecord | None:
        row = self.table.currentRow()
        if 0 <= row < len(self._records):
            return self._records[row]
        return None

    # ------------------------------------------------------------------ #
    def open_selected(self) -> None:
        record = self.selected_record()
        if record is None:
            self.notify.emit("Selectionnez une transcription.", "warning")
            return
        self.open_requested.emit(record)

    def export_selected(self) -> None:
        record = self.selected_record()
        if record is None:
            self.notify.emit("Selectionnez une transcription.", "warning")
            return
        from PySide6.QtWidgets import QFileDialog

        payload = ExportPayload(
            text=record.text or "",
            title=record.title or "Transcription",
            source=record.url or "",
            duration=record.duration,
            language=record.language,
            created_at=record.created_at,
        )
        filters = ";;".join(f"{e.label} (*.{key})" for key, e in EXPORTERS.items())
        default = get_settings().paths.exports / payload.default_filename("txt")
        path, _selected = QFileDialog.getSaveFileName(
            self, "Exporter la transcription", str(default), filters
        )
        if not path:
            return
        fmt = Path(path).suffix.lstrip(".").lower() or "txt"
        try:
            export_transcription(payload, Path(path), fmt)
        except Exception as exc:
            self.notify.emit(getattr(exc, "user_message", str(exc)), "error")
            return
        self.notify.emit(f"Export {fmt.upper()} termine.", "success")

    def delete_selected(self) -> None:
        record = self.selected_record()
        if record is None:
            self.notify.emit("Selectionnez une transcription.", "warning")
            return
        confirm = QMessageBox.question(
            self, "Confirmer la suppression",
            f"Supprimer definitivement « {record.title} » ?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self.repository.delete(record.id)
        self.refresh()
        self.notify.emit("Transcription supprimee.", "success")

    def clear_all(self) -> None:
        if not self._records:
            return
        confirm = QMessageBox.question(
            self, "Vider l'historique", "Supprimer toutes les transcriptions enregistrees ?"
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        removed = self.repository.clear()
        self.refresh()
        self.notify.emit(f"{removed} element(s) supprime(s).", "success")
