from app.schemas.estimation import EstimateResponse


def test_estimate_response_schema_exposes_cache_metadata():
    response = EstimateResponse(
        estimation="## Estimate",
        model="deepseek-v4-flash",
        tier="flash",
        provider="deepseek",
        input_tokens=10,
        output_tokens=20,
        timestamp="2026-05-10T00:00:00+00:00",
        cached=True,
        cache_backend="redis",
    )

    dumped = response.model_dump()

    assert dumped["cached"] is True
    assert dumped["cache_backend"] == "redis"


def test_estimate_response_schema_exposes_cost_metadata():
    response = EstimateResponse(
        estimation="## Estimate",
        model="deepseek-v4-flash",
        tier="flash",
        provider="deepseek",
        input_tokens=1000,
        output_tokens=2000,
        timestamp="2026-05-10T00:00:00+00:00",
        cached=False,
        cache_backend="redis",
        cost_usd=0.00247,
        cost_source="static_estimate",
        pricing_model="deepseek-v4-flash",
    )

    dumped = response.model_dump()

    assert dumped["cost_usd"] == 0.00247
    assert dumped["cost_source"] == "static_estimate"
    assert dumped["pricing_model"] == "deepseek-v4-flash"
