from app.services.costs import estimate_cost_usd, normalize_pricing_model


def test_normalize_pricing_model_removes_litellm_provider_prefix():
    assert normalize_pricing_model("moonshot/kimi-k2.6") == "kimi-k2.6"
    assert normalize_pricing_model("deepseek-v4-flash") == "deepseek-v4-flash"


def test_estimate_cost_usd_for_deepseek_flash():
    result = estimate_cost_usd(
        model="deepseek-v4-flash",
        input_tokens=1000,
        output_tokens=2000,
    )

    assert result["pricing_model"] == "deepseek-v4-flash"
    assert result["cost_source"] == "static_estimate"
    assert result["cost_usd"] > 0


def test_estimate_cost_usd_for_kimi_k26_with_litellm_prefix():
    result = estimate_cost_usd(
        model="moonshot/kimi-k2.6",
        input_tokens=1000,
        output_tokens=2000,
    )

    assert result["pricing_model"] == "kimi-k2.6"
    assert result["cost_source"] == "static_estimate"
    assert result["cost_usd"] > 0


def test_estimate_cost_usd_returns_unknown_for_missing_tokens():
    result = estimate_cost_usd(
        model="deepseek-v4-flash",
        input_tokens=None,
        output_tokens=2000,
    )

    assert result["pricing_model"] == "deepseek-v4-flash"
    assert result["cost_usd"] is None
    assert result["cost_source"] == "missing_token_usage"


def test_estimate_cost_usd_returns_unknown_for_unpriced_model():
    result = estimate_cost_usd(
        model="unknown-model",
        input_tokens=1000,
        output_tokens=2000,
    )

    assert result["pricing_model"] == "unknown-model"
    assert result["cost_usd"] is None
    assert result["cost_source"] == "unknown_pricing"
