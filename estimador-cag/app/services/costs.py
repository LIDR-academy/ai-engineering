"""
LAYER: services (cost tracking)
RESPONSIBILITY: Estimate LLM call cost from model and token usage.
WHY IT EXISTS: Session 03 canonical observability needs cost visibility in
               responses and metrics without leaking provider secrets.
DEPENDS_ON: decimal

ARCHITECTURE NOTE:
Prices are static estimates for development observability, not billing truth.
Provider invoices remain the source of truth.
"""

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

TOKENS_PER_MILLION = Decimal("1000000")

# Static USD per 1M tokens. Keep this table conservative and explicit.
# Update when provider pricing changes.
MODEL_PRICING_USD_PER_1M: dict[str, dict[str, Decimal]] = {
    "deepseek-v4-flash": {
        "input": Decimal("0.27"),
        "output": Decimal("1.10"),
    },
    "deepseek-v4-pro": {
        "input": Decimal("0.55"),
        "output": Decimal("2.19"),
    },
    "kimi-k2.5": {
        "input": Decimal("0.60"),
        "output": Decimal("2.50"),
    },
    "kimi-k2.6": {
        "input": Decimal("0.60"),
        "output": Decimal("2.50"),
    },
}


def normalize_pricing_model(model: str | None) -> str | None:
    """
    Strip LiteLLM provider prefixes so pricing lookup uses stable model ids.
    """
    if model is None:
        return None

    if "/" in model:
        return model.rsplit("/", maxsplit=1)[-1]

    return model


def estimate_cost_usd(
    *,
    model: str | None,
    input_tokens: int | None,
    output_tokens: int | None,
) -> dict[str, Any]:
    """
    Estimate cost in USD from token usage.

    Returns a structured object so callers can expose why cost may be null.
    """
    pricing_model = normalize_pricing_model(model)

    if pricing_model is None:
        return {
            "cost_usd": None,
            "cost_source": "missing_model",
            "pricing_model": None,
        }

    if input_tokens is None or output_tokens is None:
        return {
            "cost_usd": None,
            "cost_source": "missing_token_usage",
            "pricing_model": pricing_model,
        }

    pricing = MODEL_PRICING_USD_PER_1M.get(pricing_model)
    if pricing is None:
        return {
            "cost_usd": None,
            "cost_source": "unknown_pricing",
            "pricing_model": pricing_model,
        }

    input_cost = Decimal(input_tokens) / TOKENS_PER_MILLION * pricing["input"]
    output_cost = Decimal(output_tokens) / TOKENS_PER_MILLION * pricing["output"]
    total = (input_cost + output_cost).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

    return {
        "cost_usd": float(total),
        "cost_source": "static_estimate",
        "pricing_model": pricing_model,
    }
