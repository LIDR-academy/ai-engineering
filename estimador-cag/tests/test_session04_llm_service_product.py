from app.schemas.estimation import (
    DetailLevel,
    EstimationRequest,
    EstimationResult,
    OutputFormat,
    ProjectType,
)
from app.services import llm_service

VALID_DESCRIPTION = (
    "Build a customer onboarding SaaS with authentication, admin approval, "
    "email notifications, and a reporting dashboard for operations managers."
)


def structured_payload() -> dict:
    """
    Valid structured estimate used by the fake provider.

    Why this matters:
    The product service should now consume structured provider output and return
    fields for the UI.
    """

    return {
        "summary": "A structured product estimate.",
        "project_type": "web_saas",
        "detail_level": "medium",
        "output_format": "phases_table",
        "total_duration_weeks": 4,
        "total_cost_eur": 9000,
        "confidence_pct": 76,
        "phases": [
            {
                "name": "Discovery",
                "summary": "Clarify requirements and delivery risks.",
                "duration_weeks": 2,
                "cost_eur": 4000,
                "confidence_pct": 80,
                "tasks": ["Interview stakeholders", "Define roles"],
                "risks": ["Reporting scope may expand"],
            },
            {
                "name": "Build",
                "summary": "Build backend, UI, notifications, and reporting.",
                "duration_weeks": 2,
                "cost_eur": 5000,
                "confidence_pct": 74,
                "tasks": ["Build API", "Build UI", "Add emails", "Add reports"],
                "risks": ["Email template details may change"],
            },
        ],
        "assumptions": ["Email and password authentication only"],
        "risks": ["Reporting scope may grow"],
        "recommendations": ["Confirm approval workflow before build"],
    }


class FakeCache:
    backend_name = "redis"

    def __init__(self):
        self.stored = {}

    def make_key(self, *, tier, model, system_prompt, transcription):
        self.last_key_input = {
            "tier": tier,
            "model": model,
            "system_prompt": system_prompt,
            "transcription": transcription,
        }
        return "typed-cache-key"

    def get(self, key):
        return None

    def set(self, key, value):
        self.stored[key] = value


class FakeLiteLLMProvider:
    def __init__(self):
        self.calls = []

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
        max_tokens=2000,
    ):
        self.calls.append(
            {
                "messages": messages,
                "starting_tier": starting_tier,
                "tier_ladder": tier_ladder,
                "response_model": response_model,
                "max_tokens": max_tokens,
            }
        )
        return {
            "result": structured_payload(),
            "model": "deepseek-v4-flash",
            "tier": starting_tier,
            "provider": "deepseek",
            "input_tokens": 10,
            "output_tokens": 20,
            "cost_usd": 0.0001,
            "cost_source": "static_estimate",
            "pricing_model": "deepseek-v4-flash",
            "finish_reason": "stop",
            "fallback_used": False,
            "timestamp": "2026-05-12T00:00:00+00:00",
        }


def test_estimate_product_renders_prompt_and_sends_separate_system_user_messages(monkeypatch):
    fake_cache = FakeCache()
    fake_provider = FakeLiteLLMProvider()
    render_calls = []

    request = EstimationRequest(
        description=VALID_DESCRIPTION,
        project_type=ProjectType.WEB_SAAS,
        detail_level=DetailLevel.MEDIUM,
        output_format=OutputFormat.PHASES_TABLE,
    )

    def fake_render_estimation_prompt(received_request, version="v1"):
        render_calls.append((received_request, version))
        return "rendered system prompt", "rendered user prompt"

    monkeypatch.setattr(llm_service, "build_redis_cache", lambda: fake_cache)
    monkeypatch.setattr(llm_service, "LiteLLMProvider", lambda: fake_provider)
    monkeypatch.setattr(
        llm_service,
        "render_estimation_prompt",
        fake_render_estimation_prompt,
    )

    result = llm_service.estimate_product(request)

    assert result["prompt_version"] == "v1"
    assert isinstance(result["result"], EstimationResult)
    assert result["result"].summary == "A structured product estimate."
    assert result["text"].startswith("## Product estimate")
    assert result["cached"] is False
    assert result["cache_backend"] == "redis"
    assert result["model"] == "deepseek-v4-flash"
    assert result["provider"] == "deepseek"
    assert result["tier"] == "flash"

    assert render_calls == [(request, "v1")]
    sent_messages = fake_provider.calls[0]["messages"]
    sent_system_prompt = sent_messages[0]["content"].lower()

    assert sent_messages[0]["role"] == "system"
    assert sent_messages[1] == {"role": "user", "content": "rendered user prompt"}
    assert "return only valid json" in sent_system_prompt
    assert "single json object" in sent_system_prompt
    assert "rendered system prompt" not in sent_system_prompt
    assert fake_provider.calls[0]["starting_tier"] == "flash"
    assert fake_provider.calls[0]["response_model"] is EstimationResult
    assert fake_cache.last_key_input["transcription"] == request.model_dump_json()
    assert "prompt_version=v1" in fake_cache.last_key_input["system_prompt"]
    assert "rendered system prompt" in fake_cache.last_key_input["system_prompt"]
    assert "rendered user prompt" in fake_cache.last_key_input["system_prompt"]
    assert fake_cache.stored


def test_estimate_product_structured_path_does_not_send_markdown_output_contract(monkeypatch):
    """
    The structured product path must not send Markdown output instructions.

    Why this matters:
    Session 04 moved the product UI to field-based rendering. If the LLM receives
    both "return Markdown" and "return JSON", real providers can ignore JSON mode
    or produce prose. The structured path should ask for one JSON object only.
    """

    from app.schemas.estimation import EstimationResult
    from app.services import llm_service

    calls = {}

    class FakeProvider:
        def resolve_model(self, tier):
            class Resolved:
                model = "fake-model"
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
            calls["messages"] = messages
            calls["starting_tier"] = starting_tier
            calls["tier_ladder"] = tier_ladder
            calls["response_model"] = response_model
            calls["max_tokens"] = max_tokens

            return {
                "result": EstimationResult(
                    summary="A structured estimate.",
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
                            "tasks": ["Build backend", "Build frontend"],
                            "risks": [],
                        }
                    ],
                    assumptions=[],
                    risks=[],
                    recommendations=[],
                ),
                "model": "fake-model",
                "provider": "fake",
                "tier": "flash",
            }

    class NoopCache:
        backend_name = "noop"

        def make_key(self, **kwargs):
            return "key"

        def get(self, key):
            return None

        def set(self, key, value):
            calls["cached_value"] = value

    monkeypatch.setattr(llm_service, "LiteLLMProvider", FakeProvider)
    monkeypatch.setattr(llm_service, "build_redis_cache", lambda: NoopCache())

    request = EstimationRequest(
        description="Build a B2B onboarding SaaS with approval workflow and reports.",
        project_type="web_saas",
        detail_level="medium",
        output_format="phases_table",
    )

    response = llm_service.estimate_product(request, tier="flash", prompt_version="v2")

    system_message = calls["messages"][0]["content"].lower()

    assert response["result"].summary == "A structured estimate."
    assert calls["response_model"] is EstimationResult
    assert "return only valid json" in system_message
    assert "single json object" in system_message
    assert "markdown" not in system_message
    assert "return a markdown table" not in system_message
    assert "markdown table" not in system_message


def test_estimate_product_keeps_deepseek_and_kimi_structured_fallback_ladder(monkeypatch):
    """
    Structured product estimates must keep all configured production fallbacks.

    Why this matters:
    DeepSeek can fail under provider load. Even if Kimi is less reliable for
    structured JSON, backup and backup_pro must remain wired so the app has a
    second provider family available instead of failing immediately.
    """

    from app.schemas.estimation import EstimationResult
    from app.services import llm_service

    calls = {}

    class FakeProvider:
        def resolve_model(self, tier):
            class Resolved:
                model = "fake-model"
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
            calls["starting_tier"] = starting_tier
            calls["tier_ladder"] = tier_ladder
            calls["response_model"] = response_model

            return {
                "result": EstimationResult(
                    summary="A structured estimate.",
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
                            "tasks": ["Build backend", "Build frontend"],
                            "risks": [],
                        }
                    ],
                    assumptions=[],
                    risks=[],
                    recommendations=[],
                ),
                "model": "fake-model",
                "provider": "fake",
                "tier": "backup_pro",
                "fallback_used": True,
            }

    class NoopCache:
        backend_name = "noop"

        def make_key(self, **kwargs):
            return "key"

        def get(self, key):
            return None

        def set(self, key, value):
            calls["cached_value"] = value

    monkeypatch.setattr(llm_service, "LiteLLMProvider", FakeProvider)
    monkeypatch.setattr(llm_service, "build_redis_cache", lambda: NoopCache())

    request = EstimationRequest(
        description="Build a B2B onboarding SaaS with approval workflow and reports.",
        project_type="web_saas",
        detail_level="medium",
        output_format="phases_table",
    )

    response = llm_service.estimate_product(request, tier="flash", prompt_version="v2")

    assert calls["starting_tier"] == "flash"
    assert calls["tier_ladder"] == ["flash", "pro", "backup", "backup_pro"]
    assert calls["response_model"] is EstimationResult
    assert response["tier"] == "backup_pro"
    assert response["provider"] == "fake"


def test_estimate_product_response_exposes_fallback_observability_metadata(monkeypatch):
    """
    Product responses should expose requested and served tier metadata.

    Why this matters:
    DeepSeek can fail under provider load. When the request is eventually served
    by Kimi backup or backup_pro, the UI and logs need to reveal that fallback
    happened instead of hiding it behind a normal-looking estimate.
    """

    from app.schemas.estimation import EstimationResult
    from app.services import llm_service

    calls = {}

    class FakeProvider:
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
            calls["starting_tier"] = starting_tier
            calls["tier_ladder"] = tier_ladder

            return {
                "result": EstimationResult(
                    summary="A structured estimate served after fallback.",
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
                            "tasks": ["Build backend", "Build frontend"],
                            "risks": [],
                        }
                    ],
                    assumptions=[],
                    risks=[],
                    recommendations=[],
                ),
                "model": "moonshot/kimi-k2.6",
                "provider": "kimi",
                "tier": "backup_pro",
                "fallback_used": True,
            }

    class NoopCache:
        backend_name = "noop"

        def make_key(self, **kwargs):
            return "key"

        def get(self, key):
            return None

        def set(self, key, value):
            calls["cached_value"] = value

    monkeypatch.setattr(llm_service, "LiteLLMProvider", FakeProvider)
    monkeypatch.setattr(llm_service, "build_redis_cache", lambda: NoopCache())

    request = EstimationRequest(
        description="Build a B2B onboarding SaaS with approval workflow and reports.",
        project_type="web_saas",
        detail_level="medium",
        output_format="phases_table",
    )

    response = llm_service.estimate_product(request, tier="flash", prompt_version="v2")

    assert response["requested_tier"] == "flash"
    assert response["served_tier"] == "backup_pro"
    assert response["fallback_used"] is True
    assert response["provider"] == "kimi"
    assert response["model"] == "moonshot/kimi-k2.6"
    assert response["tier"] == "backup_pro"

    cached = calls["cached_value"]
    assert cached["requested_tier"] == "flash"
    assert cached["served_tier"] == "backup_pro"
    assert cached["fallback_used"] is True


def test_estimate_product_cache_hit_preserves_fallback_observability_metadata(monkeypatch):
    """
    Cache hits must preserve fallback metadata from the original valid response.

    Why this matters:
    If a Kimi fallback result was cached, later users should still see that the
    estimate was served by fallback instead of assuming it came from the primary
    DeepSeek tier.
    """

    from app.schemas.estimation import EstimationResult
    from app.services import llm_service

    class FakeProvider:
        def resolve_model(self, tier):
            class Resolved:
                model = "deepseek-v4-flash"
            return Resolved()

        def complete_structured_messages_with_fallback(self, **kwargs):
            raise AssertionError("provider should not be called on cache hit")

    class HitCache:
        backend_name = "noop"

        def make_key(self, **kwargs):
            return "key"

        def get(self, key):
            return {
                "result": EstimationResult(
                    summary="Cached fallback estimate.",
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
                ).model_dump(mode="json"),
                "text": "cached text",
                "prompt_version": "v2",
                "model": "moonshot/kimi-k2.6",
                "provider": "kimi",
                "tier": "backup_pro",
                "requested_tier": "flash",
                "served_tier": "backup_pro",
                "fallback_used": True,
            }

        def set(self, key, value):
            raise AssertionError("cache set should not run on hit")

    monkeypatch.setattr(llm_service, "LiteLLMProvider", FakeProvider)
    monkeypatch.setattr(llm_service, "build_redis_cache", lambda: HitCache())

    request = EstimationRequest(
        description="Build a B2B onboarding SaaS with approval workflow and reports.",
        project_type="web_saas",
        detail_level="medium",
        output_format="phases_table",
    )

    response = llm_service.estimate_product(request, tier="flash", prompt_version="v2")

    assert response["cached"] is True
    assert response["cache_backend"] == "noop"
    assert response["requested_tier"] == "flash"
    assert response["served_tier"] == "backup_pro"
    assert response["fallback_used"] is True
    assert response["provider"] == "kimi"


def test_estimate_product_uses_typed_request_tier_when_present(monkeypatch):
    """
    The typed product request can explicitly choose the starting model tier.

    Why this matters:
    Streamlit exposes a model selector. The backend should honor that selector
    while still keeping the full fallback ladder available.
    """

    from app.schemas.estimation import EstimationResult
    from app.services import llm_service

    calls = {}

    class FakeProvider:
        def resolve_model(self, tier):
            calls["resolved_tier"] = tier

            class Resolved:
                model = "moonshot/kimi-k2.6"

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
            calls["starting_tier"] = starting_tier
            calls["tier_ladder"] = tier_ladder

            return {
                "result": EstimationResult(
                    summary="A structured estimate.",
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
                ),
                "model": "moonshot/kimi-k2.6",
                "provider": "kimi",
                "tier": "backup_pro",
                "fallback_used": False,
            }

    class NoopCache:
        backend_name = "noop"

        def make_key(self, **kwargs):
            return "key"

        def get(self, key):
            return None

        def set(self, key, value):
            calls["cached_value"] = value

    class NoopSemanticCache:
        def lookup(self, *, bucket, text):
            return {
                "candidate_found": False,
                "candidate_key": None,
                "similarity": None,
                "bucket": bucket,
                "mode": "shadow",
            }

        def store(self, *, bucket, text, payload):
            return "semantic-key"

    monkeypatch.setattr(llm_service, "LiteLLMProvider", FakeProvider)
    monkeypatch.setattr(llm_service, "build_redis_cache", lambda: NoopCache())
    monkeypatch.setattr(llm_service, "build_semantic_shadow_cache", lambda: NoopSemanticCache())

    request = EstimationRequest(
        description="Build a B2B onboarding SaaS with approval workflow and reports.",
        project_type="web_saas",
        detail_level="medium",
        output_format="phases_table",
        tier="backup_pro",
    )

    response = llm_service.estimate_product(request, prompt_version="v2")

    assert calls["resolved_tier"] == "backup_pro"
    assert calls["starting_tier"] == "backup_pro"
    assert calls["tier_ladder"] == ["flash", "pro", "backup", "backup_pro"]
    assert response["requested_tier"] == "backup_pro"
    assert response["served_tier"] == "backup_pro"
