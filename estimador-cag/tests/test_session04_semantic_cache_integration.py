"""
Session 04 semantic cache shadow-mode integration tests.

Semantic cache is intentionally observational here. It can report a candidate,
but the application must still call the model and return fresh validated output.
"""

from app.schemas.estimation import EstimationRequest, EstimationResult
from app.services import llm_service


def _request() -> EstimationRequest:
    return EstimationRequest(
        description="Build a B2B onboarding SaaS with approval workflow and reports.",
        project_type="web_saas",
        detail_level="medium",
        output_format="phases_table",
    )


def _result(summary: str = "Fresh structured estimate.") -> EstimationResult:
    return EstimationResult(
        summary=summary,
        project_type="web_saas",
        detail_level="medium",
        output_format="phases_table",
        total_duration_weeks=2,
        total_cost_eur=3000,
        confidence_pct=80,
        phases=[
            {
                "name": "Implementation",
                "summary": "Build the first version.",
                "duration_weeks": 2,
                "cost_eur": 3000,
                "confidence_pct": 80,
                "tasks": ["Build backend"],
                "risks": [],
            }
        ],
        assumptions=[],
        risks=[],
        recommendations=[],
    )


class FakeProvider:
    def __init__(self):
        self.calls = 0

    def resolve_model(self, tier):
        class Resolved:
            model = "deepseek-v4-flash"

        return Resolved()

    def complete_structured_messages_with_fallback(
        self,
        *,
        messages,
        starting_tier,
        tier_ladder,
        response_model,
        max_tokens,
    ):
        self.calls += 1
        return {
            "result": _result(),
            "model": "deepseek-v4-flash",
            "provider": "deepseek",
            "tier": "flash",
            "fallback_used": False,
        }


class MissExactCache:
    backend_name = "noop"

    def __init__(self):
        self.stored = None

    def make_key(self, **kwargs):
        return "exact-key"

    def get(self, key):
        return None

    def set(self, key, value):
        self.stored = value


class HitExactCache:
    backend_name = "noop"

    def make_key(self, **kwargs):
        return "exact-key"

    def get(self, key):
        return {
            "result": _result("Exact cached estimate.").model_dump(mode="json"),
            "text": "cached text",
            "prompt_version": "v2",
            "model": "deepseek-v4-flash",
            "provider": "deepseek",
            "tier": "flash",
        }

    def set(self, key, value):
        raise AssertionError("exact cache set should not run on hit")


class RecordingSemanticCache:
    def __init__(self, *, candidate_found: bool):
        self.candidate_found = candidate_found
        self.lookup_calls = 0
        self.store_calls = 0

    def lookup(self, *, bucket, text):
        self.lookup_calls += 1
        if not self.candidate_found:
            return {
                "candidate_found": False,
                "candidate_key": None,
                "similarity": None,
                "bucket": bucket,
                "mode": "shadow",
            }

        return {
            "candidate_found": True,
            "candidate_key": "semantic-candidate-1",
            "similarity": 0.91,
            "bucket": bucket,
            "mode": "shadow",
        }

    def store(self, *, bucket, text, payload):
        self.store_calls += 1
        return "semantic-store-key"


def test_exact_cache_hit_skips_semantic_lookup(monkeypatch):
    """
    Exact cache must remain the first cache layer.

    Why this matters:
    Exact cache is deterministic and safe. Semantic cache is approximate and must
    not run when exact cache already has the answer.
    """

    provider = FakeProvider()
    semantic_cache = RecordingSemanticCache(candidate_found=True)

    monkeypatch.setattr(llm_service, "LiteLLMProvider", lambda: provider)
    monkeypatch.setattr(llm_service, "build_redis_cache", lambda: HitExactCache())
    monkeypatch.setattr(llm_service, "build_semantic_shadow_cache", lambda: semantic_cache)
    monkeypatch.setattr(llm_service.settings, "semantic_cache_mode", "shadow", raising=False)

    response = llm_service.estimate_product(_request(), tier="flash", prompt_version="v2")

    assert response["cached"] is True
    assert provider.calls == 0
    assert semantic_cache.lookup_calls == 0
    assert semantic_cache.store_calls == 0
    assert response["semantic_cache_mode"] == "shadow"
    assert response["semantic_candidate_found"] is False


def test_shadow_semantic_hit_does_not_serve_cached_response(monkeypatch):
    """
    A semantic candidate in shadow mode must not serve the cached payload.

    Why this matters:
    We want observability before approximate cache serving. The model must still
    run and produce the actual response.
    """

    provider = FakeProvider()
    exact_cache = MissExactCache()
    semantic_cache = RecordingSemanticCache(candidate_found=True)

    monkeypatch.setattr(llm_service, "LiteLLMProvider", lambda: provider)
    monkeypatch.setattr(llm_service, "build_redis_cache", lambda: exact_cache)
    monkeypatch.setattr(llm_service, "build_semantic_shadow_cache", lambda: semantic_cache)
    monkeypatch.setattr(llm_service.settings, "semantic_cache_mode", "shadow", raising=False)
    monkeypatch.setattr(llm_service.settings, "semantic_cache_threshold", 0.85, raising=False)

    response = llm_service.estimate_product(_request(), tier="flash", prompt_version="v2")

    assert provider.calls == 1
    assert response["result"].summary == "Fresh structured estimate."
    assert response["semantic_cache_mode"] == "shadow"
    assert response["semantic_candidate_found"] is True
    assert response["semantic_candidate_key"] == "semantic-candidate-1"
    assert response["semantic_similarity"] == 0.91
    assert semantic_cache.lookup_calls == 1
    assert semantic_cache.store_calls == 1
    assert exact_cache.stored["semantic_candidate_found"] is True


def test_semantic_shadow_off_records_disabled_metadata(monkeypatch):
    """
    Off mode should avoid semantic lookup and store.

    Why this matters:
    Production can disable semantic cache without changing product behavior.
    """

    provider = FakeProvider()
    semantic_cache = RecordingSemanticCache(candidate_found=True)

    monkeypatch.setattr(llm_service, "LiteLLMProvider", lambda: provider)
    monkeypatch.setattr(llm_service, "build_redis_cache", lambda: MissExactCache())
    monkeypatch.setattr(llm_service, "build_semantic_shadow_cache", lambda: semantic_cache)
    monkeypatch.setattr(llm_service.settings, "semantic_cache_mode", "off", raising=False)

    response = llm_service.estimate_product(_request(), tier="flash", prompt_version="v2")

    assert provider.calls == 1
    assert semantic_cache.lookup_calls == 0
    assert semantic_cache.store_calls == 0
    assert response["semantic_cache_mode"] == "off"
    assert response["semantic_candidate_found"] is False


def test_invalid_output_does_not_store_semantic_shadow(monkeypatch):
    """
    Invalid output must not be stored in semantic cache.

    Why this matters:
    Approximate retrieval of invalid estimates would amplify model failures.
    """

    class BadProvider(FakeProvider):
        def complete_structured_messages_with_fallback(self, **kwargs):
            self.calls += 1
            return {
                "result": _result("This mentions system prompt and should fail guardrails."),
                "model": "deepseek-v4-flash",
                "provider": "deepseek",
                "tier": "flash",
                "fallback_used": False,
            }

    provider = BadProvider()
    semantic_cache = RecordingSemanticCache(candidate_found=False)

    monkeypatch.setattr(llm_service, "LiteLLMProvider", lambda: provider)
    monkeypatch.setattr(llm_service, "build_redis_cache", lambda: MissExactCache())
    monkeypatch.setattr(llm_service, "build_semantic_shadow_cache", lambda: semantic_cache)
    monkeypatch.setattr(llm_service.settings, "semantic_cache_mode", "shadow", raising=False)

    try:
        llm_service.estimate_product(_request(), tier="flash", prompt_version="v2")
    except RuntimeError:
        pass
    else:
        raise AssertionError("invalid output should raise RuntimeError")

    assert provider.calls == 1
    assert semantic_cache.lookup_calls == 1
    assert semantic_cache.store_calls == 0
