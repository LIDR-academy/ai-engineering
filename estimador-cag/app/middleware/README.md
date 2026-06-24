# Observability Layer: `middleware/`

**Responsibility:** Request/response logging, metrics, and tracing.

**WHY it exists:** FastAPI middleware intercepts every HTTP request so we can
measure latency, log token usage, and expose runtime metrics without polluting
business logic in `services/` or `routers/`.

**Rules:**
- Only import from `app.config` and standard library
- Do NOT call LLMs here
- Keep middleware lightweight to avoid request slowdown
