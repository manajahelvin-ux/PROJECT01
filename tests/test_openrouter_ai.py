"""Phases 6-7-8 - service OpenRouter, chunking et processeur IA.

Aucun appel reseau reel : httpx est intercepte par respx et le service
est remplace par des doubles la ou seule l'orchestration est testee.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from transcribe_ai.config.settings import AIMode, Settings
from transcribe_ai.core.ai.chunking import ChunkCache, SentenceChunker
from transcribe_ai.core.ai.openrouter_service import OpenRouterService
from transcribe_ai.core.ai.processor import OpenRouterProcessor
from transcribe_ai.core.exceptions import (
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

BASE = "https://openrouter.ai/api/v1"
CHAT = f"{BASE}/chat/completions"


def completion(content: str = "Texte nettoye.") -> dict:
    return {
        "model": "test/model",
        "choices": [{"message": {"role": "assistant", "content": content},
                     "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }


@pytest.fixture
def api_settings(fake_api_key: str, tmp_path) -> Settings:
    """Parametres de test : cle factice, retry immediat, cache isole."""
    return Settings(
        _env_file=None,
        openrouter_api_key=fake_api_key,
        openrouter_model="test/model",
        ai_max_retries=2,
        ai_retry_backoff=1.0,
        ai_timeout=5.0,
        data_dir=str(tmp_path / "data"),
    )


@pytest.fixture
def service(api_settings: Settings) -> OpenRouterService:
    return OpenRouterService(api_settings)


# --------------------------------------------------------------------------- #
# Phase 6 : service HTTP
# --------------------------------------------------------------------------- #
class TestOpenRouterService:
    def test_cle_absente_bloque_lappel(self) -> None:
        with pytest.raises(MissingAPIKeyError):
            OpenRouterService(Settings(_env_file=None)).chat("sys", "bonjour")

    @respx.mock
    def test_completion_reussie(self, service: OpenRouterService) -> None:
        route = respx.post(CHAT).mock(return_value=httpx.Response(200, json=completion()))
        response = service.chat("prompt systeme", "bonjour")
        assert response.content == "Texte nettoye."
        assert response.total_tokens == 15
        assert route.called

    @respx.mock
    def test_entetes_dauthentification(self, service: OpenRouterService, fake_api_key) -> None:
        route = respx.post(CHAT).mock(return_value=httpx.Response(200, json=completion()))
        service.chat("sys", "bonjour")
        headers = route.calls[0].request.headers
        assert headers["authorization"] == f"Bearer {fake_api_key}"
        assert headers["x-title"] == "TranscribeAI"

    @respx.mock
    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            (401, AuthenticationError),
            (403, PermissionDeniedError),
            (500, ServerError),
            (400, OpenRouterError),
        ],
    )
    def test_mapping_des_erreurs_http(self, service, status: int, expected: type) -> None:
        respx.post(CHAT).mock(
            return_value=httpx.Response(status, json={"error": {"message": "boom"}})
        )
        with pytest.raises(expected):
            service.chat("sys", "bonjour")

    @respx.mock
    def test_429_retente_puis_reussit(self, service: OpenRouterService) -> None:
        route = respx.post(CHAT).mock(
            side_effect=[
                httpx.Response(429, json={"error": {"message": "rate"}}, headers={"Retry-After": "0"}),
                httpx.Response(200, json=completion("ok")),
            ]
        )
        assert service.chat("sys", "bonjour").content == "ok"
        assert route.call_count == 2

    @respx.mock
    def test_429_persistant_finit_en_erreur(self, service: OpenRouterService) -> None:
        respx.post(CHAT).mock(
            return_value=httpx.Response(429, json={"error": {"message": "rate"}},
                                        headers={"Retry-After": "0"})
        )
        with pytest.raises(RateLimitError):
            service.chat("sys", "bonjour")

    @respx.mock
    def test_absence_de_reseau(self, service: OpenRouterService) -> None:
        respx.post(CHAT).mock(side_effect=httpx.ConnectError("pas de reseau"))
        with pytest.raises(NetworkError):
            service.chat("sys", "bonjour")

    @respx.mock
    def test_timeout(self, service: OpenRouterService) -> None:
        from transcribe_ai.core.exceptions import AITimeoutError

        respx.post(CHAT).mock(side_effect=httpx.ReadTimeout("trop long"))
        with pytest.raises(AITimeoutError):
            service.chat("sys", "bonjour")

    @respx.mock
    def test_json_invalide(self, service: OpenRouterService) -> None:
        respx.post(CHAT).mock(return_value=httpx.Response(200, text="<html>oops</html>"))
        with pytest.raises(InvalidResponseError):
            service.chat("sys", "bonjour")

    @respx.mock
    def test_reponse_vide(self, service: OpenRouterService) -> None:
        respx.post(CHAT).mock(return_value=httpx.Response(200, json={"choices": []}))
        with pytest.raises(EmptyResponseError):
            service.chat("sys", "bonjour")

    def test_contenu_trop_volumineux_refuse(self, service: OpenRouterService) -> None:
        with pytest.raises(OpenRouterError, match="volumineux"):
            service.chat("sys", "x" * 200_000)

    @respx.mock
    def test_connexion_ok(self, service: OpenRouterService) -> None:
        respx.get(f"{BASE}/models").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "test/model"}]})
        )
        ok, message = service.test_connection()
        assert ok and "Connexion reussie" in message

    @respx.mock
    def test_connexion_refusee(self, service: OpenRouterService) -> None:
        respx.get(f"{BASE}/models").mock(return_value=httpx.Response(401, json={"error": "no"}))
        ok, message = service.test_connection()
        assert not ok and "401" in message

    def test_connexion_sans_cle(self) -> None:
        ok, message = OpenRouterService(Settings(_env_file=None)).test_connection()
        assert not ok and "cle API" in message


# --------------------------------------------------------------------------- #
# Phase 7 : chunking
# --------------------------------------------------------------------------- #
class TestChunking:
    def test_texte_court_reste_en_un_bloc(self) -> None:
        chunks = SentenceChunker(chunk_size=1000).split("Bonjour. Comment allez-vous ?")
        assert len(chunks) == 1

    def test_texte_vide(self) -> None:
        assert SentenceChunker().split("   ") == []

    def test_decoupage_multiple_et_ordonne(self) -> None:
        text = " ".join(f"Ceci est la phrase numero {i}." for i in range(300))
        chunks = SentenceChunker(chunk_size=500, overlap=0).split(text)
        assert len(chunks) > 1
        assert [c.index for c in chunks] == list(range(len(chunks)))

    def test_taille_respectee(self) -> None:
        text = " ".join(f"Phrase {i} de test." for i in range(500))
        for chunk in SentenceChunker(chunk_size=400, overlap=0).split(text):
            assert len(chunk.text) <= 400 + 100  # tolerance : on ne coupe pas une phrase

    def test_aucune_perte_de_contenu(self) -> None:
        text = " ".join(f"Phrase {i}." for i in range(200))
        chunks = SentenceChunker(chunk_size=300, overlap=0).split(text)
        reassembled = " ".join(c.text for c in chunks)
        for i in (0, 99, 199):
            assert f"Phrase {i}." in reassembled

    def test_phrase_geante_coupee(self) -> None:
        chunks = SentenceChunker(chunk_size=100, overlap=0).split("a" * 1000)
        assert len(chunks) == 10

    def test_empreintes_stables_et_distinctes(self) -> None:
        chunker = SentenceChunker(chunk_size=200, overlap=0)
        text = " ".join(f"Phrase {i} du test." for i in range(50))
        first, second = chunker.split(text), chunker.split(text)
        assert [c.fingerprint for c in first] == [c.fingerprint for c in second]
        assert len({c.fingerprint for c in first}) == len(first)

    def test_recomposition_supprime_le_recouvrement(self) -> None:
        chunker = SentenceChunker(chunk_size=1000, overlap=0)
        merged = chunker.merge(["Bonjour a tous.", "Bonjour a tous. Voici la suite."])
        assert merged.count("Bonjour a tous.") == 1


class TestChunkCache:
    def test_cycle_ecriture_lecture(self, tmp_path) -> None:
        cache = ChunkCache(tmp_path / "cache")
        assert cache.get("abc", "clean", "m") is None
        cache.set("abc", "clean", "m", "resultat")
        assert cache.get("abc", "clean", "m") == "resultat"

    def test_isolation_par_tache_et_modele(self, tmp_path) -> None:
        cache = ChunkCache(tmp_path / "cache")
        cache.set("abc", "clean", "m1", "A")
        assert cache.get("abc", "summary", "m1") is None
        assert cache.get("abc", "clean", "m2") is None

    def test_vidage(self, tmp_path) -> None:
        cache = ChunkCache(tmp_path / "cache")
        cache.set("a", "clean", "m", "x")
        cache.set("b", "clean", "m", "y")
        assert cache.size() == 2
        assert cache.clear() == 2 and cache.size() == 0


# --------------------------------------------------------------------------- #
# Phase 8 : processeur
# --------------------------------------------------------------------------- #
@pytest.fixture
def processor(api_settings: Settings, tmp_path) -> OpenRouterProcessor:
    return OpenRouterProcessor(
        service=OpenRouterService(api_settings),
        chunker=SentenceChunker(chunk_size=200, overlap=0),
        cache=ChunkCache(tmp_path / "cache"),
        settings=api_settings,
    )


class TestProcessor:
    @respx.mock
    def test_nettoyage_dun_bloc(self, processor: OpenRouterProcessor) -> None:
        respx.post(CHAT).mock(return_value=httpx.Response(200, json=completion("Bonjour.")))
        result = processor.clean("bonjour")
        assert result.cleaned_text == "Bonjour."
        assert result.usage.calls == 1

    @respx.mock
    def test_un_appel_par_bloc(self, processor: OpenRouterProcessor) -> None:
        route = respx.post(CHAT).mock(return_value=httpx.Response(200, json=completion("ok")))
        text = " ".join(f"Phrase unique numero {i}." for i in range(60))
        expected = len(processor.chunker.split(text))
        result = processor.clean(text)
        assert expected > 1
        assert route.call_count == expected == result.usage.calls

    @respx.mock
    def test_le_cache_evite_de_repayer(self, processor: OpenRouterProcessor) -> None:
        route = respx.post(CHAT).mock(return_value=httpx.Response(200, json=completion("ok")))
        processor.clean("bonjour tout le monde")
        first_calls = route.call_count
        second = processor.clean("bonjour tout le monde")
        assert route.call_count == first_calls          # aucun nouvel appel
        assert second.usage.calls == 0
        assert second.usage.cached_chunks >= 1

    @respx.mock
    def test_mode_none_najoute_aucun_appel(self, processor: OpenRouterProcessor) -> None:
        route = respx.post(CHAT).mock(return_value=httpx.Response(200, json=completion()))
        result = processor.process("texte brut", mode=AIMode.NONE)
        assert result.cleaned_text == "texte brut"
        assert not route.called and result.usage.calls == 0

    @respx.mock
    def test_erreur_sur_un_bloc_conserve_le_texte_brut(self, processor) -> None:
        respx.post(CHAT).mock(return_value=httpx.Response(500, json={"error": "boom"}))
        result = processor.clean("bonjour le monde")
        assert "bonjour le monde" in result.cleaned_text  # degradation maitrisee

    @respx.mock
    def test_progression_reportee(self, processor: OpenRouterProcessor) -> None:
        respx.post(CHAT).mock(return_value=httpx.Response(200, json=completion("ok")))
        events = []
        processor.clean("Une phrase. Deux phrases.", progress=events.append)
        assert events and "Appels IA" in events[-1].message

    @respx.mock
    def test_resume(self, processor: OpenRouterProcessor) -> None:
        respx.post(CHAT).mock(return_value=httpx.Response(200, json=completion("Un resume.")))
        result = processor.summarize("texte a resumer")
        assert result.short_summary and result.detailed_summary

    @respx.mock
    def test_points_cles_normalises(self, processor: OpenRouterProcessor) -> None:
        respx.post(CHAT).mock(
            return_value=httpx.Response(200, json=completion("- Point A\n- Point B\n* Point C"))
        )
        assert processor.key_points("texte").key_points == ["Point A", "Point B", "Point C"]

    @respx.mock
    def test_extraction_json_dans_un_bloc_markdown(self, processor) -> None:
        payload = '```json\n{"topics":["IA"],"keywords":["python"],"actions":[],' \
                  '"entities":["Guido"],"concepts":["POO"]}\n```'
        respx.post(CHAT).mock(return_value=httpx.Response(200, json=completion(payload)))
        result = processor.extract("texte")
        assert result.topics == ["IA"] and result.keywords == ["python"]
        assert "Guido" in result.entities and "POO" in result.entities

    @respx.mock
    def test_extraction_json_illisible_ne_casse_pas(self, processor) -> None:
        respx.post(CHAT).mock(return_value=httpx.Response(200, json=completion("desole")))
        assert processor.extract("texte").topics == []

    @respx.mock
    def test_traduction(self, processor: OpenRouterProcessor) -> None:
        respx.post(CHAT).mock(return_value=httpx.Response(200, json=completion("Hello.")))
        assert processor.translate("Bonjour.", "en").cleaned_text == "Hello."

    @respx.mock
    def test_mode_complet_agrege_la_consommation(self, processor) -> None:
        payload = '{"topics":["a"],"keywords":["b"],"actions":[],"entities":[],"concepts":[]}'
        respx.post(CHAT).mock(
            side_effect=lambda request: httpx.Response(
                200, json=completion(payload if b"JSON" in request.content else "Contenu.")
            )
        )
        result = processor.process("Bonjour. Voici un texte.", mode=AIMode.FULL)
        assert result.cleaned_text and result.short_summary and result.key_points
        assert result.usage.calls >= 4
