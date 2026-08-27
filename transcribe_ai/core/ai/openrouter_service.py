"""Phase 6 - service OpenRouter : couche HTTP unique de l'application.

Responsabilites : authentification, timeouts, retry avec backoff
exponentiel, mapping des erreurs HTTP, limitation de taille, parsing des
reponses et journalisation sans fuite de secret.
"""

from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass
from typing import Any

import httpx

from transcribe_ai.config.settings import Settings, get_settings
from transcribe_ai.core.exceptions import (
    AITimeoutError,
    AuthenticationError,
    EmptyResponseError,
    InvalidResponseError,
    MissingAPIKeyError,
    NetworkError,
    OpenRouterError,
    PermissionDeniedError,
    RateLimitError,
    ServerError,
)
from transcribe_ai.utils.logging_config import get_logger

logger = get_logger(__name__)

#: Garde-fou : au-dela, on refuse d'envoyer (le chunker doit avoir decoupe avant).
MAX_PROMPT_CHARS = 120_000

#: Codes qui justifient une nouvelle tentative.
RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}


@dataclass(slots=True)
class ChatResponse:
    """Reponse normalisee d'une completion."""

    content: str
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    finish_reason: str = ""

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class OpenRouterService:
    """Client HTTP OpenRouter, volontairement synchrone.

    Le pipeline s'execute deja dans un thread de travail : un client
    synchrone reste plus simple a tester et a raisonner qu'un client async.
    """

    def __init__(self, settings: Settings | None = None, client: httpx.Client | None = None):
        self.settings = settings or get_settings()
        self._client = client
        self._owns_client = client is None

    # ------------------------------------------------------------------ #
    # Infrastructure
    # ------------------------------------------------------------------ #
    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.settings.openrouter_base_url,
                timeout=httpx.Timeout(self.settings.ai_timeout, connect=15.0),
                follow_redirects=True,
            )
        return self._client

    def close(self) -> None:
        if self._client is not None and self._owns_client:
            self._client.close()
            self._client = None

    def __enter__(self) -> OpenRouterService:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def _headers(self) -> dict[str, str]:
        key = self.settings.api_key_value()
        if not key:
            raise MissingAPIKeyError()
        return {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            # En-tetes d'attribution recommandes par OpenRouter.
            "HTTP-Referer": self.settings.openrouter_site_url,
            "X-Title": self.settings.openrouter_app_name,
        }

    def is_configured(self) -> bool:
        return self.settings.has_api_key

    # ------------------------------------------------------------------ #
    # Mapping des erreurs
    # ------------------------------------------------------------------ #
    @staticmethod
    def _extract_error_message(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except (json.JSONDecodeError, ValueError):
            return (response.text or "")[:300]
        error = payload.get("error")
        if isinstance(error, dict):
            return str(error.get("message") or error)
        return str(error or payload)[:300]

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code < 400:
            return
        detail = self._extract_error_message(response)
        code = response.status_code
        logger.warning("OpenRouter HTTP %s : %s", code, detail)
        if code == 401:
            raise AuthenticationError(detail, status_code=code)
        if code == 403:
            raise PermissionDeniedError(detail, status_code=code)
        if code == 429:
            raise RateLimitError(detail, status_code=code)
        if code >= 500:
            raise ServerError(detail, status_code=code)
        if code == 402:
            raise OpenRouterError(
                detail,
                status_code=code,
                user_message="Credits OpenRouter insuffisants pour ce modele (402).",
            )
        raise OpenRouterError(
            detail,
            status_code=code,
            user_message=f"OpenRouter a refuse la requete (HTTP {code}) : {detail[:150]}",
        )

    def _backoff_delay(self, attempt: int, retry_after: str | None = None) -> float:
        """Delai avant nouvelle tentative : `Retry-After` sinon backoff + jitter."""
        if retry_after:
            try:
                return min(float(retry_after), 60.0)
            except ValueError:
                pass
        base = self.settings.ai_retry_backoff ** attempt
        return min(base + random.uniform(0, 0.5), 60.0)

    # ------------------------------------------------------------------ #
    # Requetes
    # ------------------------------------------------------------------ #
    def _request(self, method: str, path: str, payload: dict | None = None) -> dict[str, Any]:
        """Execute une requete avec retry ; ne journalise jamais la cle."""
        last_error: Exception | None = None
        attempts = self.settings.ai_max_retries + 1

        for attempt in range(attempts):
            try:
                response = self.client.request(
                    method, path, json=payload, headers=self._headers()
                )
                if response.status_code in RETRYABLE_STATUS and attempt < attempts - 1:
                    delay = self._backoff_delay(attempt, response.headers.get("Retry-After"))
                    logger.info(
                        "HTTP %s — tentative %s/%s, nouvel essai dans %.1f s",
                        response.status_code, attempt + 1, attempts, delay,
                    )
                    time.sleep(delay)
                    continue
                self._raise_for_status(response)
                try:
                    return response.json()
                except (json.JSONDecodeError, ValueError) as exc:
                    raise InvalidResponseError(
                        f"JSON invalide : {(response.text or '')[:200]}",
                        status_code=response.status_code,
                    ) from exc

            except httpx.TimeoutException as exc:
                last_error = AITimeoutError(str(exc))
            except httpx.ConnectError as exc:
                last_error = NetworkError(str(exc))
            except httpx.HTTPError as exc:
                last_error = OpenRouterError(str(exc))
            else:
                continue

            if attempt < attempts - 1:
                delay = self._backoff_delay(attempt)
                logger.info(
                    "Erreur reseau (%s) — tentative %s/%s, nouvel essai dans %.1f s",
                    type(last_error).__name__, attempt + 1, attempts, delay,
                )
                time.sleep(delay)

        raise last_error or OpenRouterError("Echec de la requete OpenRouter")

    # ------------------------------------------------------------------ #
    # API publique
    # ------------------------------------------------------------------ #
    def chat(
        self,
        system_prompt: str,
        user_content: str,
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ChatResponse:
        """Envoie une completion et retourne la reponse normalisee."""
        if not user_content.strip():
            raise EmptyResponseError(
                "Contenu vide", user_message="Aucun texte a envoyer a l'IA."
            )
        if len(user_content) > MAX_PROMPT_CHARS:
            raise OpenRouterError(
                f"Contenu trop volumineux : {len(user_content)} caracteres",
                user_message=(
                    "Le texte envoye est trop volumineux. "
                    "Reduisez la taille des blocs dans les parametres."
                ),
            )

        payload = {
            "model": model or self.settings.openrouter_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": (
                self.settings.ai_temperature if temperature is None else temperature
            ),
            "max_tokens": max_tokens or self.settings.ai_max_tokens,
        }
        data = self._request("POST", "/chat/completions", payload)
        return self._parse_completion(data)

    @staticmethod
    def _parse_completion(data: dict[str, Any]) -> ChatResponse:
        choices = data.get("choices") or []
        if not choices:
            raise EmptyResponseError(f"Aucun choix dans la reponse : {str(data)[:200]}")
        message = choices[0].get("message") or {}
        content = (message.get("content") or "").strip()
        if not content:
            raise EmptyResponseError("Le modele a renvoye un contenu vide")
        usage = data.get("usage") or {}
        return ChatResponse(
            content=content,
            model=data.get("model", ""),
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            finish_reason=choices[0].get("finish_reason") or "",
        )

    def list_models(self) -> list[dict[str, Any]]:
        """Catalogue des modeles disponibles (alimente la liste des parametres)."""
        data = self._request("GET", "/models")
        models = data.get("data") or []
        return [m for m in models if isinstance(m, dict)]

    def test_connection(self) -> tuple[bool, str]:
        """Verification utilisee par le bouton « Tester la connexion »."""
        if not self.is_configured():
            return False, "Aucune cle API renseignee."
        model = self.settings.openrouter_model
        try:
            models = self.list_models()
        except OpenRouterError as exc:
            return False, exc.user_message
        except Exception as exc:
            logger.error("Test de connexion echoue : %s", exc)
            return False, "Connexion impossible. Verifiez votre cle API ou votre connexion."

        ids = {m.get("id") for m in models}
        if model and ids and model not in ids:
            return True, (
                f"Connexion reussie ({len(ids)} modeles disponibles), "
                f"mais le modele « {model} » est introuvable dans le catalogue."
            )
        return True, (
            f"Connexion reussie. Modele « {model} » disponible. "
            f"API fonctionnelle ({len(ids)} modeles)."
        )
