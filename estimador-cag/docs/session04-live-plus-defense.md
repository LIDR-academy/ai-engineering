# Session 04 Live Plus Defense

## What was built

This branch implements a typed product estimation workflow on top of the existing FastAPI, Streamlit, Redis, and LiteLLM backend.

The user enters a product description in Streamlit. FastAPI validates it as a typed request. The service renders versioned prompts, calls an LLM through a provider fallback ladder, validates structured JSON, applies guardrails, stores valid responses in exact Redis cache, records semantic cache shadow metadata, and returns a structured response for the UI.

## Provider fallback ladder

The structured product path keeps this provider ladder:

    DeepSeek flash → DeepSeek pro → Kimi 2.5 backup → Kimi 2.6 backup_pro

This is intentional. DeepSeek is the primary provider, but provider load can cause failures. Kimi remains wired as a fallback family even though it is less reliable for structured JSON.

The ladder is protected by tests so future changes do not accidentally remove Kimi backup paths.

## Structured output contract

Typed product estimates return an `EstimationResult` object with:

* summary
* project_type
* detail_level
* output_format
* total_duration_weeks
* total_cost_eur
* confidence_pct
* phases
* assumptions
* risks
* recommendations

The product UI renders these fields directly instead of parsing markdown.

A compatibility markdown text field is still returned for older consumers.

## Aggregate normalization

LLMs can estimate phases but are unreliable at exact arithmetic.

The backend therefore normalizes deterministic aggregate values before final validation:

* `total_cost_eur` is computed from phase `cost_eur` values.
* `total_duration_weeks` is computed from phase `duration_weeks` values.

Pydantic then validates the final object.

This gives a stronger production contract than only asking the model to be careful.

## Fallback observability

Responses expose fallback metadata:

* `requested_tier`
* `served_tier`
* `fallback_used`
* `model`
* `provider`
* `tier`

This prevents fallback from becoming invisible. If DeepSeek fails and Kimi serves the request, the API can show that clearly.

Cache hits preserve the original fallback metadata.

## Exact cache first

Exact Redis cache is deterministic and remains the only cache that can serve responses.

Exact cache key material includes the request identity, prompt version, structured system prompt, rendered template prompt, and model identity.

Exact cache runs before semantic cache.

Exact cache hits skip semantic lookup.

## Semantic cache shadow mode

Semantic cache exists in shadow mode only.

It can observe whether a similar request would have matched, but it cannot serve responses.

Responses can expose:

* `semantic_cache_mode`
* `semantic_candidate_found`
* `semantic_candidate_key`
* `semantic_similarity`
* `semantic_bucket`

The semantic cache currently uses deterministic local embeddings to validate control flow. It is not a production vector store yet.

## Guardrails

Input guardrails run in the FastAPI typed endpoint before service execution. Blocked input cannot reach exact cache, semantic cache, or the provider.

Output guardrails run after structured validation and before cache storage. Invalid output is not cached.

## Runtime proof

Final runtime smoke confirmed:

* FastAPI `/health` returned ok.
* The typed estimate endpoint returned structured JSON.
* Redis exact cache metadata appeared in the API response.
* Fallback observability metadata appeared in the API response.
* Semantic cache shadow metadata appeared in the API response.
* Streamlit rendered the product form and structured estimate output.

Observed API metadata included:

    cached: true
    cache_backend: redis
    model: deepseek-v4-flash
    provider: deepseek
    tier: flash
    requested_tier: flash
    served_tier: flash
    fallback_used: false
    semantic_cache_mode: shadow
    semantic_candidate_found: false

## Validation gates

The branch was validated with:

    uv run ruff check app/ tests/ streamlit_app.py
    uv run pytest tests/ -v

The final tested suite included structured schema tests, provider tests, endpoint tests, guardrail tests, fallback observability tests, semantic cache tests, Streamlit tests, and regression tests.

## Known limitations

* Semantic cache does not serve responses yet.
* Semantic cache uses deterministic local embeddings, not production embeddings.
* Semantic cache is process local, not Redis Stack or vector database backed.
* Kimi fallback can still fail to produce valid structured JSON on some calls.
* Legacy transcription endpoints remain for compatibility.
* Streamlit currently displays cache/provider info, but semantic shadow metadata is primarily visible through the API response.
