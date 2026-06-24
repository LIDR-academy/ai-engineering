# Data Contracts Layer: `schemas/`

**Responsibility:** Pydantic models for request/response validation.

**WHY it exists:** Schemas act as the contract between HTTP layer (routers) and
business layer (services). Guarantees:
1. Incoming JSON matches expected shape (fail fast on bad input)
2. Outgoing JSON is serializable and typed
3. OpenAPI documentation generates automatically

**Rules:**
- No business logic
- No database models (those live in `models/` in future modules)
- Use Pydantic v2 syntax
