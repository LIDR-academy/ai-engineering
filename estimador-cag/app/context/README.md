# CAG Context Layer: `context/`

**Responsibility:** Static few-shot examples for Context-Augmented Generation.

**WHY it exists:** Session 2 uses static context (few-shot examples baked into the prompt).
Future modules (3-4) will replace this with dynamic RAG retrieval.

**Rules:**
- Store only static, version-controlled data
- No database queries
- No LLM calls
