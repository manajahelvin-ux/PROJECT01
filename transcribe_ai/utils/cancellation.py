"""Jetons d'annulation partages entre l'UI et le pipeline."""

from __future__ import annotations

import threading


class CancelToken:
    """Implementation thread-safe du protocole `CancellationToken`."""

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    def reset(self) -> None:
        self._event.clear()

    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        from transcribe_ai.core.exceptions import TranscribeAIError

        if self.is_cancelled():
            raise TranscribeAIError(
                "Operation annulee", user_message="Operation annulee par l'utilisateur."
            )


class NullToken(CancelToken):
    """Jeton qui n'est jamais annule : valeur par defaut pratique."""

    def is_cancelled(self) -> bool:
        return False
