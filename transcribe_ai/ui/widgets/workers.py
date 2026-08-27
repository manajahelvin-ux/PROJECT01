"""Execution des taches longues hors du thread graphique.

L'interface ne doit jamais se figer : tout travail lourd passe par un
`Worker` (QRunnable) execute dans un `QThreadPool`, et communique avec
l'UI uniquement par signaux.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from transcribe_ai.core.exceptions import TranscribeAIError
from transcribe_ai.core.models import ProgressEvent
from transcribe_ai.utils.cancellation import CancelToken
from transcribe_ai.utils.logging_config import get_logger

logger = get_logger(__name__)


class WorkerSignals(QObject):
    """Signaux emis par un `Worker` (un QRunnable ne peut pas en porter)."""

    started = Signal()
    progress = Signal(object)     # ProgressEvent
    finished = Signal(object)     # resultat de la fonction
    failed = Signal(str)          # message utilisateur
    done = Signal()               # toujours emis, succes ou echec


class Worker(QRunnable):
    """Execute `fn` dans le pool de threads et relaie son avancement.

    La fonction recoit `progress=` et `cancel=` si elle les accepte, ce
    qui permet de reutiliser directement les fonctions du pipeline.
    """

    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self.cancel_token = CancelToken()
        self.setAutoDelete(True)

    def cancel(self) -> None:
        self.cancel_token.cancel()

    def _emit_progress(self, event: ProgressEvent) -> None:
        # Emission depuis le thread de travail : Qt met le signal en file
        # d'attente vers le thread graphique, c'est donc sur.
        self.signals.progress.emit(event)

    @Slot()
    def run(self) -> None:
        self.signals.started.emit()
        try:
            import inspect

            parameters = inspect.signature(self.fn).parameters
            if "progress" in parameters:
                self.kwargs.setdefault("progress", self._emit_progress)
            if "cancel" in parameters:
                self.kwargs.setdefault("cancel", self.cancel_token)
            result = self.fn(*self.args, **self.kwargs)
        except TranscribeAIError as exc:
            logger.warning("Tache en echec : %s", exc)
            self.signals.failed.emit(exc.user_message)
        except Exception as exc:
            logger.exception("Erreur inattendue dans une tache de fond")
            self.signals.failed.emit(f"Erreur inattendue : {exc}")
        else:
            self.signals.finished.emit(result)
        finally:
            self.signals.done.emit()


class TaskRunner:
    """Petite facade au-dessus de `QThreadPool`."""

    def __init__(self, max_threads: int | None = None) -> None:
        self.pool = QThreadPool.globalInstance()
        if max_threads:
            self.pool.setMaxThreadCount(max_threads)

    def submit(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Worker:
        worker = Worker(fn, *args, **kwargs)
        self.pool.start(worker)
        return worker

    def wait(self, timeout_ms: int = 30_000) -> bool:
        return self.pool.waitForDone(timeout_ms)

    @property
    def active(self) -> int:
        return self.pool.activeThreadCount()
