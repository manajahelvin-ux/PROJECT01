"""Composants d'interface reutilisables : cards, badges, progression, toasts."""

from __future__ import annotations

from typing import ClassVar

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from transcribe_ai.core.models import STAGE_LABELS, PipelineStage


class Card(QFrame):
    """Conteneur de contenu avec titre optionnel."""

    def __init__(self, title: str = "", subtitle: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Card")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(20, 18, 20, 18)
        self._layout.setSpacing(12)
        if title:
            label = QLabel(title)
            label.setObjectName("CardTitle")
            self._layout.addWidget(label)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setObjectName("CardSubtitle")
            sub.setWordWrap(True)
            self._layout.addWidget(sub)

    def add(self, widget: QWidget) -> QWidget:
        self._layout.addWidget(widget)
        return widget

    def add_layout(self, layout) -> None:
        self._layout.addLayout(layout)

    def body(self) -> QVBoxLayout:
        return self._layout


class Badge(QLabel):
    """Pastille d'etat coloree."""

    VARIANTS: ClassVar[dict[str, str]] = {
        "success": "BadgeSuccess",
        "warning": "BadgeWarning",
        "danger": "BadgeDanger",
        "neutral": "BadgeNeutral",
        "info": "BadgeInfo",
    }

    def __init__(self, text: str = "", variant: str = "neutral", parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setObjectName("Badge")
        self.set_variant(variant)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)

    def set_variant(self, variant: str) -> None:
        self.setProperty("class", self.VARIANTS.get(variant, "BadgeNeutral"))
        # Un seul objectName pilote le style : on le reaffecte pour rafraichir.
        self.setObjectName(self.VARIANTS.get(variant, "BadgeNeutral"))
        self.style().unpolish(self)
        self.style().polish(self)

    def set_status(self, text: str, variant: str) -> None:
        self.setText(text)
        self.set_variant(variant)


class StatCard(Card):
    """Chiffre cle affiche sur la page d'accueil."""

    def __init__(self, value: str, label: str, parent: QWidget | None = None):
        super().__init__(parent=parent)
        self.value_label = QLabel(value)
        self.value_label.setObjectName("StatValue")
        text_label = QLabel(label)
        text_label.setObjectName("StatLabel")
        self.add(self.value_label)
        self.add(text_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)


class StageRow(QWidget):
    """Une ligne d'etape : libelle, barre de progression, etat."""

    def __init__(self, stage: PipelineStage, number: int, parent: QWidget | None = None):
        super().__init__(parent)
        self.stage = stage
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(12)

        self.label = QLabel(f"{number}. {STAGE_LABELS[stage]}")
        self.label.setMinimumWidth(160)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        self.state = Badge("En attente", "neutral")
        self.state.setMinimumWidth(90)

        layout.addWidget(self.label)
        layout.addWidget(self.bar, 1)
        layout.addWidget(self.state)

    def set_progress(self, percent: float, running: bool = True) -> None:
        self.bar.setValue(int(max(0, min(percent, 100))))
        if running and percent < 100:
            self.state.set_status("En cours", "info")

    def set_done(self) -> None:
        self.bar.setValue(100)
        self.state.set_status("Termine", "success")

    def set_failed(self) -> None:
        self.state.set_status("Echec", "danger")

    def reset(self) -> None:
        self.bar.setValue(0)
        self.state.set_status("En attente", "neutral")


class PipelineProgress(Card):
    """Les 6 etapes du pipeline, avec leur avancement respectif."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__("Progression", parent=parent)
        self.rows: dict[PipelineStage, StageRow] = {}
        for number, stage in enumerate(PipelineStage, start=1):
            row = StageRow(stage, number)
            self.rows[stage] = row
            self.add(row)
        self.message = QLabel("")
        self.message.setObjectName("Muted")
        self.message.setWordWrap(True)
        self.add(self.message)

    def apply(self, event) -> None:
        """Applique un `ProgressEvent` recu du pipeline."""
        row = self.rows.get(event.stage)
        if row is None:
            return
        # Les etapes precedentes sont implicitement terminees.
        stages = list(PipelineStage)
        for previous in stages[: stages.index(event.stage)]:
            self.rows[previous].set_done()
        if event.done or event.percent >= 100:
            row.set_done()
        else:
            row.set_progress(event.percent)
        if event.message:
            self.message.setText(event.message)

    def reset(self) -> None:
        for row in self.rows.values():
            row.reset()
        self.message.setText("")

    def mark_failed(self, stage: PipelineStage | None = None) -> None:
        if stage and stage in self.rows:
            self.rows[stage].set_failed()


class Toast(QFrame):
    """Notification ephemere affichee en bas a droite de la fenetre."""

    ICONS: ClassVar[dict[str, str]] = {"success": "✓", "error": "✕", "warning": "!", "info": "i"}

    def __init__(self, message: str, variant: str = "info", parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Toast")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)

        icon = Badge(self.ICONS.get(variant, "i"),
                     {"success": "success", "error": "danger",
                      "warning": "warning"}.get(variant, "info"))
        label = QLabel(message)
        label.setWordWrap(True)
        label.setMaximumWidth(360)
        layout.addWidget(icon)
        layout.addWidget(label, 1)

        self._effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)
        self._animation = QPropertyAnimation(self._effect, b"opacity", self)

    def show_for(self, milliseconds: int = 4000) -> None:
        self.show()
        self.raise_()
        self._animation.setDuration(200)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.start()
        QTimer.singleShot(milliseconds, self._fade_out)

    def _fade_out(self) -> None:
        self._animation.setDuration(250)
        self._animation.setStartValue(1.0)
        self._animation.setEndValue(0.0)
        self._animation.finished.connect(self.deleteLater)
        self._animation.start()


class ToastManager:
    """Empile les notifications dans le coin inferieur droit de la fenetre."""

    def __init__(self, parent: QWidget):
        self.parent = parent
        self._toasts: list[Toast] = []

    def show(self, message: str, variant: str = "info", duration: int = 4000) -> Toast:
        toast = Toast(message, variant, self.parent)
        toast.adjustSize()
        self._toasts.append(toast)
        self._reposition()
        toast.show_for(duration)
        toast.destroyed.connect(lambda: self._forget(toast))
        return toast

    def _forget(self, toast: Toast) -> None:
        if toast in self._toasts:
            self._toasts.remove(toast)
        self._reposition()

    def _reposition(self) -> None:
        margin = 20
        try:
            height, width = self.parent.height(), self.parent.width()
        except RuntimeError:
            # La fenetre parente a ete detruite avant ses notifications
            # (fermeture de l'application) : il n'y a plus rien a placer.
            self._toasts.clear()
            return
        y = height - margin
        for toast in reversed(self._toasts):
            try:
                y -= toast.height() + 10
                toast.move(width - toast.width() - margin, y)
            except RuntimeError:  # widget deja detruit
                continue


class Separator(QFrame):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Separator")
        self.setFixedHeight(1)


def primary_button(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName("Primary")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


def ghost_button(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName("Ghost")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button
