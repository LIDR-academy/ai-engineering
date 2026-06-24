# Business Logic Layer: `services/`

**Responsibility:** Prompts, LLM calls, processing.

**WHY it exists:** Separating prompt engineering from HTTP transport means:
1. Unit-test logic without spinning up a web server
2. Swap LLM providers without touching router code
3. Reuse logic in CLI tools, Streamlit apps, or background workers

**Rules:**
- Only import from `app.config` and `app.context`
- Return plain dicts, not HTTP responses
- Handle tier routing and fallback logic here
