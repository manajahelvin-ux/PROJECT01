"""Phase 8 - OpenRouterProcessor : orchestration du traitement IA.

Applique les prompts specialises sur des blocs ordonnes, en s'appuyant
sur le cache pour ne jamais refacturer un bloc deja traite, et agrege la
consommation dans un `AIUsage` affichable par l'interface.
"""

from __future__ import annotations

import json
import re

from transcribe_ai.config.settings import AIMode, Settings, get_settings
from transcribe_ai.core.ai.chunking import ChunkCache, SentenceChunker
from transcribe_ai.core.ai.openrouter_service import OpenRouterService
from transcribe_ai.core.ai.prompts import get_prompt, translation_prompt
from transcribe_ai.core.exceptions import OpenRouterError
from transcribe_ai.core.interfaces import (
    CancellationToken,
    ProgressCallback,
)
from transcribe_ai.core.interfaces import (
    OpenRouterProcessor as BaseOpenRouterProcessor,
)
from transcribe_ai.core.models import AIResult, AIUsage, PipelineStage, ProgressEvent
from transcribe_ai.utils.logging_config import get_logger

logger = get_logger(__name__)

#: Au-dela, on resume les resumes intermediaires plutot que le texte entier.
SUMMARY_INPUT_LIMIT = 12_000


class OpenRouterProcessor(BaseOpenRouterProcessor):
    """Implementation OpenRouter du contrat `AIProcessor`."""

    name = "openrouter"

    def __init__(
        self,
        service: OpenRouterService | None = None,
        chunker: SentenceChunker | None = None,
        cache: ChunkCache | None = None,
        settings: Settings | None = None,
        use_cache: bool = True,
    ) -> None:
        self.settings = settings or get_settings()
        self.service = service or OpenRouterService(self.settings)
        self.chunker = chunker or SentenceChunker()
        self.cache = cache or ChunkCache()
        self.use_cache = use_cache

    # ------------------------------------------------------------------ #
    # Infrastructure
    # ------------------------------------------------------------------ #
    def is_configured(self) -> bool:
        return self.service.is_configured()

    def test_connection(self) -> tuple[bool, str]:
        return self.service.test_connection()

    @property
    def model(self) -> str:
        return self.settings.openrouter_model

    def _call(self, task: str, system_prompt: str, content: str, usage: AIUsage) -> str:
        """Appel unitaire, avec lecture/ecriture du cache et comptabilite."""
        from transcribe_ai.utils.text import fingerprint

        key = fingerprint(content)
        if self.use_cache:
            cached = self.cache.get(key, task, self.model)
            if cached is not None:
                usage.cached_chunks += 1
                logger.debug("Bloc servi depuis le cache (tache=%s)", task)
                return cached

        response = self.service.chat(system_prompt, content)
        usage.calls += 1
        usage.prompt_tokens += response.prompt_tokens
        usage.completion_tokens += response.completion_tokens
        if self.use_cache:
            self.cache.set(key, task, self.model, response.content)
        return response.content

    # ------------------------------------------------------------------ #
    # Nettoyage / structuration
    # ------------------------------------------------------------------ #
    def clean(
        self,
        text: str,
        language: str = "auto",
        progress: ProgressCallback | None = None,
        cancel: CancellationToken | None = None,
    ) -> AIResult:
        """Nettoie la transcription bloc par bloc, en preservant l'ordre."""
        usage = AIUsage()
        chunks = self.chunker.split(text)
        if not chunks:
            return AIResult(cleaned_text="", usage=usage, model=self.model)

        system_prompt = get_prompt("clean", language)
        pieces: list[str] = []
        total = len(chunks)
        for chunk in chunks:  # l'ordre de la liste garantit l'ordre du resultat
            if cancel is not None and cancel.is_cancelled():
                raise OpenRouterError(
                    "Traitement IA annule", user_message="Traitement IA annule."
                )
            try:
                pieces.append(self._call("clean", system_prompt, chunk.text, usage))
            except OpenRouterError as exc:
                # Degradation maitrisee : on conserve le texte brut du bloc.
                logger.warning("Bloc %s non traite (%s) — texte brut conserve", chunk.index, exc)
                pieces.append(chunk.text)
            if progress is not None:
                progress(
                    ProgressEvent(
                        stage=PipelineStage.AI_PROCESS,
                        percent=(chunk.index + 1) / total * 100.0,
                        message=(
                            f"Blocs traites : {chunk.index + 1}/{total} — "
                            f"Appels IA : {usage.calls}"
                        ),
                    )
                )
        return AIResult(
            cleaned_text=self.chunker.merge(pieces), usage=usage, model=self.model
        )

    def structure(self, text: str, language: str = "auto") -> AIResult:
        usage = AIUsage()
        prompt = get_prompt("structure", language)
        pieces = [
            self._call("structure", prompt, chunk.text, usage)
            for chunk in self.chunker.split(text)
        ]
        return AIResult(cleaned_text=self.chunker.merge(pieces), usage=usage, model=self.model)

    # ------------------------------------------------------------------ #
    # Resume
    # ------------------------------------------------------------------ #
    def _condense(self, text: str, usage: AIUsage, language: str) -> str:
        """Reduit un texte trop long par resume hierarchique (map-reduce)."""
        if len(text) <= SUMMARY_INPUT_LIMIT:
            return text
        prompt = get_prompt("summary_detailed", language)
        partials = [
            self._call("summary_partial", prompt, chunk.text, usage)
            for chunk in self.chunker.split(text)
        ]
        condensed = "\n\n".join(partials)
        # Un seul niveau de recursion supplementaire suffit en pratique.
        if len(condensed) > SUMMARY_INPUT_LIMIT:
            return condensed[:SUMMARY_INPUT_LIMIT]
        return condensed

    def summarize(self, text: str, language: str = "auto") -> AIResult:
        usage = AIUsage()
        source = self._condense(text, usage, language)
        short = self._call("summary_short", get_prompt("summary_short", language), source, usage)
        detailed = self._call(
            "summary_detailed", get_prompt("summary_detailed", language), source, usage
        )
        return AIResult(
            short_summary=short, detailed_summary=detailed, usage=usage, model=self.model
        )

    def key_points(self, text: str, language: str = "auto") -> AIResult:
        usage = AIUsage()
        source = self._condense(text, usage, language)
        raw = self._call("key_points", get_prompt("key_points", language), source, usage)
        points = [
            re.sub(r"^[-*•\d.\s]+", "", line).strip()
            for line in raw.splitlines()
            if line.strip()
        ]
        return AIResult(key_points=[p for p in points if p], usage=usage, model=self.model)

    # ------------------------------------------------------------------ #
    # Extraction structuree
    # ------------------------------------------------------------------ #
    @staticmethod
    def _parse_json_block(raw: str) -> dict:
        """Extrait un objet JSON meme entoure de texte ou d'un bloc Markdown."""
        candidate = raw.strip()
        fence = re.search(r"```(?:json)?\s*(.+?)```", candidate, re.DOTALL)
        if fence:
            candidate = fence.group(1).strip()
        else:
            start, end = candidate.find("{"), candidate.rfind("}")
            if start != -1 and end > start:
                candidate = candidate[start : end + 1]
        try:
            data = json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            logger.warning("Extraction JSON illisible — resultat ignore")
            return {}
        return data if isinstance(data, dict) else {}

    def extract(self, text: str, language: str = "auto") -> AIResult:
        usage = AIUsage()
        source = self._condense(text, usage, language)
        raw = self._call("extraction", get_prompt("extraction", language), source, usage)
        data = self._parse_json_block(raw)

        def as_list(key: str) -> list[str]:
            value = data.get(key) or []
            if isinstance(value, str):
                return [v.strip() for v in value.split(",") if v.strip()]
            return [str(v).strip() for v in value if str(v).strip()]

        return AIResult(
            topics=as_list("topics"),
            keywords=as_list("keywords"),
            actions=as_list("actions"),
            entities=as_list("entities") + as_list("concepts"),
            usage=usage,
            model=self.model,
        )

    def translate(self, text: str, target_language: str) -> AIResult:
        usage = AIUsage()
        prompt = translation_prompt(target_language)
        pieces = [
            self._call(f"translate:{target_language}", prompt, chunk.text, usage)
            for chunk in self.chunker.split(text)
        ]
        return AIResult(cleaned_text=self.chunker.merge(pieces), usage=usage, model=self.model)

    # ------------------------------------------------------------------ #
    # Orchestration selon le mode choisi (maitrise des couts)
    # ------------------------------------------------------------------ #
    def process(
        self,
        text: str,
        mode: AIMode | str = AIMode.CLEAN,
        language: str = "auto",
        progress: ProgressCallback | None = None,
        cancel: CancellationToken | None = None,
    ) -> AIResult:
        """Applique le niveau de traitement demande — `none` n'appelle rien."""
        mode = AIMode(mode) if not isinstance(mode, AIMode) else mode
        if mode is AIMode.NONE:
            return AIResult(cleaned_text=text, usage=AIUsage(), model="")

        result = self.clean(text, language, progress, cancel)
        usage = result.usage

        if mode in (AIMode.CLEAN_SUMMARY, AIMode.FULL):
            summary = self.summarize(result.cleaned_text or text, language)
            result.short_summary = summary.short_summary
            result.detailed_summary = summary.detailed_summary
            usage = usage.merge(summary.usage)

        if mode is AIMode.FULL:
            points = self.key_points(result.cleaned_text or text, language)
            result.key_points = points.key_points
            usage = usage.merge(points.usage)

            extraction = self.extract(result.cleaned_text or text, language)
            result.topics = extraction.topics
            result.keywords = extraction.keywords
            result.actions = extraction.actions
            result.entities = extraction.entities
            usage = usage.merge(extraction.usage)

        result.usage = usage
        logger.info(
            "Traitement IA termine (%s) : %s appels, %s blocs caches, %s tokens",
            mode.value, usage.calls, usage.cached_chunks, usage.total_tokens,
        )
        return result
