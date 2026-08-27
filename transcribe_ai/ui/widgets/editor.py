"""Phase 9 - editeur de transcription avec actions IA."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QTextCursor, QTextDocument
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from transcribe_ai.config.settings import SUPPORTED_LANGUAGES
from transcribe_ai.ui.widgets.components import Badge, Separator, primary_button


class TranscriptEditor(QWidget):
    """Zone d'edition : outils standards + actions IA."""

    #: (action, argument) — l'action IA est executee par la page parente,
    #: qui dispose du runner de threads et du processeur.
    ai_requested = Signal(str, str)
    text_changed = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("TRANSCRIPTION")
        title.setObjectName("CardTitle")
        self.word_badge = Badge("0 mot", "neutral")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.word_badge)
        layout.addLayout(header)

        # -- barre d'outils d'edition -------------------------------------
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)
        self.btn_undo = QPushButton("Annuler")
        self.btn_redo = QPushButton("Refaire")
        self.btn_copy = QPushButton("Copier")
        self.btn_paste = QPushButton("Coller")
        for button in (self.btn_undo, self.btn_redo, self.btn_copy, self.btn_paste):
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        # -- rechercher / remplacer ---------------------------------------
        search_row = QHBoxLayout()
        search_row.setSpacing(6)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Rechercher…")
        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText("Remplacer par…")
        self.btn_find = QPushButton("Rechercher")
        self.btn_replace = QPushButton("Remplacer")
        self.btn_replace_all = QPushButton("Tout remplacer")
        search_row.addWidget(self.search_input, 2)
        search_row.addWidget(self.replace_input, 2)
        search_row.addWidget(self.btn_find)
        search_row.addWidget(self.btn_replace)
        search_row.addWidget(self.btn_replace_all)
        layout.addLayout(search_row)

        # -- zone de texte --------------------------------------------------
        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText(
            "La transcription apparaitra ici. Vous pourrez la corriger avant export."
        )
        self.editor.setUndoRedoEnabled(True)
        layout.addWidget(self.editor, 1)

        layout.addWidget(Separator())

        # -- actions IA -----------------------------------------------------
        ai_row = QHBoxLayout()
        ai_row.setSpacing(8)
        self.btn_clean = primary_button("Nettoyer avec l'IA")
        self.btn_summary = QPushButton("Resumer avec l'IA")
        self.btn_translate = QPushButton("Traduire avec l'IA")
        self.language_box = QComboBox()
        for code, label in SUPPORTED_LANGUAGES.items():
            if code != "auto":
                self.language_box.addItem(label, code)
        self.language_box.setCurrentIndex(max(self.language_box.findData("en"), 0))

        ai_row.addWidget(self.btn_clean)
        ai_row.addWidget(self.btn_summary)
        ai_row.addWidget(self.btn_translate)
        ai_row.addWidget(self.language_box)
        ai_row.addStretch(1)
        layout.addLayout(ai_row)

        self._connect()

    # ------------------------------------------------------------------ #
    def _connect(self) -> None:
        self.btn_undo.clicked.connect(self.editor.undo)
        self.btn_redo.clicked.connect(self.editor.redo)
        self.btn_copy.clicked.connect(self.editor.copy)
        self.btn_paste.clicked.connect(self.editor.paste)
        self.btn_find.clicked.connect(self.find_next)
        self.search_input.returnPressed.connect(self.find_next)
        self.btn_replace.clicked.connect(self.replace_current)
        self.btn_replace_all.clicked.connect(self.replace_all)
        self.editor.textChanged.connect(self._on_text_changed)
        self.btn_clean.clicked.connect(lambda: self.ai_requested.emit("clean", ""))
        self.btn_summary.clicked.connect(lambda: self.ai_requested.emit("summary", ""))
        self.btn_translate.clicked.connect(
            lambda: self.ai_requested.emit("translate", self.language_box.currentData())
        )

    def _on_text_changed(self) -> None:
        count = len(self.text().split())
        self.word_badge.set_status(f"{count} mot{'s' if count > 1 else ''}", "neutral")
        self.text_changed.emit()

    # -- API publique ---------------------------------------------------
    def text(self) -> str:
        return self.editor.toPlainText()

    def set_text(self, text: str, keep_undo: bool = True) -> None:
        """Remplit l'editeur ; `keep_undo` conserve l'historique d'annulation."""
        if keep_undo:
            cursor = self.editor.textCursor()
            cursor.select(QTextCursor.SelectionType.Document)
            cursor.insertText(text)  # passe par la pile d'annulation
        else:
            self.editor.setPlainText(text)

    def clear(self) -> None:
        self.editor.clear()

    def set_read_only(self, value: bool) -> None:
        self.editor.setReadOnly(value)

    # -- recherche / remplacement ---------------------------------------
    def find_next(self) -> bool:
        needle = self.search_input.text()
        if not needle:
            return False
        found = self.editor.find(needle)
        if not found:  # relance depuis le debut du document
            cursor = self.editor.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            self.editor.setTextCursor(cursor)
            found = self.editor.find(needle)
        return found

    def replace_current(self) -> bool:
        cursor = self.editor.textCursor()
        if cursor.hasSelection() and cursor.selectedText() == self.search_input.text():
            cursor.insertText(self.replace_input.text())
            return True
        return self.find_next()

    def replace_all(self) -> int:
        needle = self.search_input.text()
        if not needle:
            return 0
        replacement = self.replace_input.text()
        document: QTextDocument = self.editor.document()
        count = 0
        cursor = QTextCursor(document)
        cursor.beginEditBlock()
        finder = QTextCursor(document)
        while True:
            finder = document.find(needle, finder)
            if finder.isNull():
                break
            finder.insertText(replacement)
            count += 1
        cursor.endEditBlock()
        return count


class ExportBar(QWidget):
    """Boutons d'export des quatre formats."""

    export_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(QLabel("Exporter :"))
        for fmt, label in (
            ("txt", "TXT"), ("docx", "WORD"), ("srt", "SRT"), ("vtt", "VTT")
        ):
            button = QPushButton(label)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _=False, f=fmt: self.export_requested.emit(f))
            layout.addWidget(button)
        layout.addStretch(1)
