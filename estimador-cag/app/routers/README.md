# Transport Layer: `routers/`

**Responsibility:** HTTP in, HTTP out. Thin.

**WHY it exists:** Routers must contain zero business logic. They validate incoming
requests via Pydantic schemas, delegate to `services/`, and format outgoing responses.
This separation allows swapping FastAPI for another framework without touching business logic.

**Rules:**
- Only import from `app.schemas` and `app.services`
- No direct LLM client calls
- No database queries
