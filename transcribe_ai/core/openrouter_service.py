"""Alias de compatibilite : le service reel vit dans `core/ai/openrouter_service.py`.

Ce module conserve le chemin d'import `transcribe_ai.core.openrouter_service`
prevu par la specification initiale.
"""

from transcribe_ai.core.ai.openrouter_service import (
    MAX_PROMPT_CHARS,
    RETRYABLE_STATUS,
    ChatResponse,
    OpenRouterService,
)

__all__ = ["MAX_PROMPT_CHARS", "RETRYABLE_STATUS", "ChatResponse", "OpenRouterService"]
