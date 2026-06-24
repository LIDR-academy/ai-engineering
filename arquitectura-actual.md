# Diagnóstico arquitectónico del sistema RAG actual

**Branch de trabajo:** `gg-session-09/pre-work`
**Branch espejo del enunciado:** `session-09/pre-work`
**Transcripción trazada:** `examples/transcripts/02_ambiguous.txt`
**Estado:** diagnóstico arquitectónico basado en ejecución real del sistema actual, sin cambios de producción.

## Resumen ejecutivo

Al cierre de la Sesión 08, el servicio IA ya puede ingerir presupuestos históricos, crear chunks estructurados, vectorizarlos con `text-embedding-3-small`, persistirlos en PostgreSQL + pgvector y recuperar los chunks más cercanos mediante `POST /search`. Eso cubre la parte de **Retrieval** del camino RAG, pero todavía no cierra el objetivo del proyecto: recibir una transcripción de reunión y devolver una estimación fundamentada.

El trace con `02_ambiguous.txt` demuestra que el sistema funciona técnicamente, pero también muestra sus límites: una transcripción de tienda gourmet/ecommerce se convierte en un único vector y recupera chunks de un presupuesto fintech. La conclusión arquitectónica no es que pgvector falle; la conclusión es que faltan las etapas de **Query Understanding → Metadata-filtered Retrieval → Context Assembly / Augmentation → Generation → Quality Gate**.

> **Nota de fidelidad con el enunciado.** El enunciado nombra `ingest/`, `embedding_pipeline/` y `storage/` como capas conceptuales. En esta rama, esa capa de almacenamiento aparece materializada como `app/persistence/repository.py` y PostgreSQL + pgvector. No es una divergencia funcional: es el mapeo entre el lenguaje del ejercicio y la implementación real observada.

---

## 1. Diagrama de la arquitectura actual

```text
ARQUITECTURA ACTUAL

[Frontend / Cliente]
  Browser / Demo / Script
  examples/transcripts/02_ambiguous.txt
        |
        v
[Business backend FastAPI]
  GET  /health
  POST /embeddings/ingest
  POST /search
  POST /embeddings/compare
  GET  /search/metrics
        |
        v
[AI service actual]
  ingest / embeddings:
    JSONStructuralChunker
      -> OpenAIEmbedder text-embedding-3-small
      -> PersistentEmbeddingIngestionService
      -> storage / persistence layer
         concrete implementation: DocumentRepository
      -> PostgreSQL + pgvector
         tables: documents, chunks

  search:
    transcript or query
      -> OpenAIEmbedder text-embedding-3-small
      -> SearchService
      -> pgvector cosine distance
      -> top-k chunks

  compare:
    deterministic keyword fake embedder
    learning endpoint only

IMPLEMENTED FLOW ENDS HERE:
  top-k chunks are returned.
  There is no Query Understanding stage.
  There is no metadata-filtered retrieval policy.
  There is no Context Assembly / Augmentation stage.
  There is no generated estimate.
  There is no RAG quality gate.
```

### Observación

La arquitectura actual tiene una base sólida de recuperación semántica persistente, pero el flujo acaba al devolver chunks. Si llega una transcripción real de cliente, el sistema no la convierte en requisitos estructurados, no decide qué evidencia es suficiente, no reconstruye presupuestos padre y no genera una estimación.

---

## 2. Trace anotado de una transcripción

Transcripción usada: `examples/transcripts/02_ambiguous.txt`.

La transcripción describe una primera llamada con Rubén Castaño, gerente de Casa Castaño, una tienda de productos gourmet. El cliente divaga, pero deja señales concretas: vender por internet, fidelización por puntos o club, dashboard de pedidos/stock/productos más vendidos, pago con tarjeta, correo de confirmación y posible expansión futura a Francia.

### 2.1 Precondición de branch y base técnica

```text
Current branch:
gg-session-09/pre-work

Lineage check:
YES: live-inspired hardening is ancestor of current HEAD
YES: strict pgvector branch is also ancestor of current HEAD
```

**Observación:** El trabajo se hizo sobre la rama con convención `gg` y parte de la base mejorada de Sesión 08 inspirada en el directo. También se creó la rama espejo `session-09/pre-work` porque el enunciado literal usa ese nombre.

### 2.2 Migración y estado de base de datos

Comando ejecutado para migrar:

```bash
cd /workspaces/ai-engineering

docker compose run --rm ai_service uv run alembic current || true
docker compose run --rm ai_service uv run alembic upgrade head
docker compose run --rm ai_service uv run alembic current
```

Resultado relevante:

```text
Running upgrade  -> 0001_session08_pgvector, Create pgvector document and chunk storage for Session 08.
Running upgrade 0001_session08_pgvector -> 0002_session08_hnsw_vector_index, Add HNSW cosine vector index for Session 08 extra-mile search.
0002_session08_hnsw_vector_index (head)
```

Verificación de tablas y extensión:

```bash
cd /workspaces/ai-engineering

docker compose exec postgres psql -U estimator -d estimator -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"
docker compose exec postgres psql -U estimator -d estimator -c "\dt"
docker compose exec postgres psql -U estimator -d estimator -c "SELECT COUNT(*) AS documents_count FROM documents;"
docker compose exec postgres psql -U estimator -d estimator -c "SELECT COUNT(*) AS chunks_count FROM chunks;"
```

Resultado relevante antes de la ingesta:

```text
vector extension: vector 0.8.2
tables: alembic_version, chunks, documents
documents_count before ingest: 0
chunks_count before ingest: 0
```

**Observación:** La infraestructura de pgvector estaba correctamente creada después de migrar, pero la base empezó vacía. Sin ingesta, `/search` responde técnicamente, pero no puede devolver evidencia.

### 2.3 Ingesta del corpus histórico de ejemplo

Comando ejecutado:

```bash
cd /workspaces/ai-engineering/estimador-cag

uv run python query_examples.py --base-url http://localhost:8000 --ingest-example-corpus | tee /tmp/session09-query-examples-output.txt
```

Respuesta de ingesta:

```json
{
  "document_id": 1,
  "chunks_created": 4,
  "embedding_dimension": 1536,
  "ingestion_time_ms": 771,
  "_client_elapsed_ms": 778
}
```

Verificación posterior:

```text
documents_count: 1
chunks_count: 4
```

**Observación:** El corpus trazado contiene un único presupuesto histórico con cuatro chunks. Esto basta para diagnosticar el sistema, pero no basta para una estimación real robusta. De hecho, esta limitación aparece después en el trace: al pedir `k=5`, solo existen cuatro chunks recuperables.

### 2.4 Vectorización de la transcripción completa

Comando ejecutado para vectorizar la transcripción completa contra el módulo real de embeddings:

```bash
cd /workspaces/ai-engineering/estimador-cag

uv run python - <<'PY' | tee /tmp/session09-embedding-vector-evidence.txt
import math
from pathlib import Path

from app.embedding_pipeline.embedder import OpenAIEmbedder

transcript = Path("../examples/transcripts/02_ambiguous.txt").read_text(encoding="utf-8")

embedder = OpenAIEmbedder()
vector = embedder.embed_one(transcript)

norm = math.sqrt(sum(float(x) * float(x) for x in vector))

print("embedding_dimension:", len(vector))
print("first_component:", vector[0])
print("last_component:", vector[-1])
print("l2_norm:", norm)
PY
```

Salida capturada:

```text
2026-06-15 16:18:18 [info     ] embedding_batch_completed      chunk_count=1 latency_ms=3391 model=text-embedding-3-small token_count=890
embedding_dimension: 1536
first_component: 0.00624847412109375
last_component: 0.0190277099609375
l2_norm: 1.0003498345455109
```

**Observación:** Ese vector representa toda la conversación como un único punto semántico de 1536 dimensiones. El problema es arquitectónico: la transcripción mezcla ecommerce, fidelización, dashboard, pagos, correo e internacionalización futura, pero el sistema no separa esas señales en requisitos recuperables.

### 2.5 Búsqueda semántica top-5 con la transcripción completa

Comando ejecutado:

```bash
cd /workspaces/ai-engineering

python - <<'PY' | tee /tmp/session09-search-trace.json
import json
from pathlib import Path
import urllib.request

transcript = Path("examples/transcripts/02_ambiguous.txt").read_text(encoding="utf-8")

payload = {
    "query": transcript,
    "k": 5,
}

req = urllib.request.Request(
    "http://localhost:8000/search",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)

with urllib.request.urlopen(req, timeout=30) as response:
    body = response.read().decode("utf-8")
    parsed = json.loads(body)
    print(json.dumps(parsed, indent=2, ensure_ascii=False))
PY
```

Resumen de la respuesta:

```text
query_length: 2853
k: 5
search_time_ms: 181
results_count: 4
embedding_dimension: 1536
first_component: 0.00624847412109375
last_component: 0.0190277099609375
l2_norm: 1.0003498345455109
```

Respuesta cruda relevante de `/search`, preservando chunks, metadata y distancias:

```json
{
  "k": 5,
  "search_time_ms": 181,
  "filters_applied": {},
  "results": [
    {
      "chunk_id": 4,
      "document_id": 1,
      "chunk_type": "budget_component",
      "content": "[Project: Fintech modernization project with REST APIs, JWT authentication, external integrations, Kubernetes migration, and an operations dashboard.]\n[Client sector: finance | Country: ES | Year: 2024 | Main technology: python | Total estimated hours: 520]\n\nComponent: Operations dashboard\nDescription: Internal dashboard for operations teams to monitor audit events, integration status, and financial workflow health.\nTech stack: typescript, react\nComplexity: medium\nEstimated hours: 80\nDependencies: INT-001",
      "distance": 0.6812073805009786,
      "metadata": {
        "budget_id": "BUD-SESSION08-EXAMPLE",
        "component_id": "UI-001",
        "client_sector": "finance",
        "estimated_hours": 80,
        "tech_stack": ["typescript", "react"],
        "year": 2024
      }
    },
    {
      "chunk_id": 2,
      "document_id": 1,
      "chunk_type": "budget_component",
      "content": "[Project: Fintech modernization project with REST APIs, JWT authentication, external integrations, Kubernetes migration, and an operations dashboard.]\n[Client sector: finance | Country: ES | Year: 2024 | Main technology: python | Total estimated hours: 520]\n\nComponent: External payment provider integration\nDescription: Integration with external banking and payment systems, including webhook handling, retry logic, and audit logging.\nTech stack: python, fastapi, postgresql\nComplexity: medium\nEstimated hours: 120\nDependencies: AUTH-001",
      "distance": 0.701399437355401,
      "metadata": {
        "budget_id": "BUD-SESSION08-EXAMPLE",
        "component_id": "INT-001",
        "client_sector": "finance",
        "estimated_hours": 120,
        "tech_stack": ["python", "fastapi", "postgresql"],
        "year": 2024
      }
    },
    {
      "chunk_id": 1,
      "document_id": 1,
      "chunk_type": "budget_component",
      "content": "[Project: Fintech modernization project with REST APIs, JWT authentication, external integrations, Kubernetes migration, and an operations dashboard.]\n[Client sector: finance | Country: ES | Year: 2024 | Main technology: python | Total estimated hours: 520]\n\nComponent: JWT authentication API\nDescription: REST API development with JWT authentication, token refresh, role-based authorization, and financial-sector security controls.\nTech stack: python, fastapi, postgresql, redis\nComplexity: high\nEstimated hours: 140\nDependencies: none",
      "distance": 0.7205973391351352,
      "metadata": {
        "budget_id": "BUD-SESSION08-EXAMPLE",
        "component_id": "AUTH-001",
        "client_sector": "finance",
        "estimated_hours": 140,
        "tech_stack": ["python", "fastapi", "postgresql", "redis"],
        "year": 2024
      }
    },
    {
      "chunk_id": 3,
      "document_id": 1,
      "chunk_type": "budget_component",
      "content": "[Project: Fintech modernization project with REST APIs, JWT authentication, external integrations, Kubernetes migration, and an operations dashboard.]\n[Client sector: finance | Country: ES | Year: 2024 | Main technology: python | Total estimated hours: 520]\n\nComponent: Kubernetes migration\nDescription: Migration from monolith to microservices architecture using Kubernetes, containerized services, health checks, and deployment automation.\nTech stack: docker, kubernetes, python\nComplexity: high\nEstimated hours: 180\nDependencies: AUTH-001, INT-001",
      "distance": 0.7213019645316079,
      "metadata": {
        "budget_id": "BUD-SESSION08-EXAMPLE",
        "component_id": "MIG-001",
        "client_sector": "finance",
        "estimated_hours": 180,
        "tech_stack": ["docker", "kubernetes", "python"],
        "year": 2024
      }
    }
  ]
}
```

**Observación:** La búsqueda pidió cinco chunks, pero devolvió cuatro porque el corpus solo tiene cuatro. Todos pertenecen a `BUD-SESSION08-EXAMPLE` y al sector finance. La transcripción, en cambio, es ecommerce/gourmet. Esto demuestra que el sistema recupera vecinos semánticos disponibles, no evidencia suficiente ni necesariamente adecuada.

### 2.6 Lectura de los chunks devueltos

| Rank | chunk_id | budget_id | component | sector | hours | distance | relevancia para Casa Castaño |
| ---: | ---: | --- | --- | --- | ---: | ---: | --- |
| 1 | 4 | BUD-SESSION08-EXAMPLE | UI-001 | finance | 80 | 0.681207 | Parcial: dashboard sí, dominio y escala no. |
| 2 | 2 | BUD-SESSION08-EXAMPLE | INT-001 | finance | 120 | 0.701399 | Parcial: pagos/integración sí, banking/webhooks no necesariamente. |
| 3 | 1 | BUD-SESSION08-EXAMPLE | AUTH-001 | finance | 140 | 0.720597 | Débil: seguridad/JWT puede existir, pero no es lo central de la tienda gourmet. |
| 4 | 3 | BUD-SESSION08-EXAMPLE | MIG-001 | finance | 180 | 0.721302 | Poco relevante: Kubernetes/migración no aparece en la transcripción. |

**Conclusión del trace:** El retrieval funciona como mecanismo técnico, pero no como estimador. La señal útil está mezclada con falsos positivos de dominio, no hay filtros de metadata, no hay umbral de suficiencia y no hay reconstrucción del presupuesto padre.

---

## 3. Diagnóstico: cinco fallos identificados

### Fallo 1 — La transcripción completa se usa como una única query semántica

- **Problema observado:** La transcripción tiene `2853` caracteres y se incrusta como un único vector. El sistema no separa ecommerce, fidelización, dashboard, pagos, correo e internacionalización futura.
- **Causa probable:** Falta una etapa de Query Understanding que convierta la reunión cruda en requisitos estructurados y consultas recuperables.
- **Propuesta de solución:** Añadir `QueryUnderstanding` / `TranscriptAnalyzer` para extraer dominio, sector, features, restricciones, incertidumbres y una query canónica trazable.

### Fallo 2 — No hay retrieval filtrado por metadata ni detección de mismatch de dominio

- **Problema observado:** Una transcripción de tienda gourmet/ecommerce recupera cuatro chunks de un presupuesto finance. `filters_applied` aparece vacío en la respuesta.
- **Causa probable:** El retriever actual usa similitud vectorial, pero no aplica filtros por sector, tipo de proyecto, país, tecnología o escala antes de ordenar vecinos.
- **Propuesta de solución:** Añadir un `MetadataFilteredRetriever` o una política de retrieval que combine filtros estructurados con búsqueda vectorial. Si no hay corpus compatible, debe marcar `insufficient_evidence`.

### Fallo 3 — Las distancias son relativamente parecidas y no hay umbral de suficiencia

- **Problema observado:** Los cuatro resultados tienen distancias entre `0.6812` y `0.7213`, pero el sistema los devuelve sin advertir baja confianza o posible falso positivo.
- **Causa probable:** Falta una política de score, umbrales calibrados y clasificación de evidencia suficiente versus débil.
- **Propuesta de solución:** Añadir un `RetrievalPolicy` / `RAGQualityGate` que evalúe distancia, diversidad, compatibilidad de metadata y cobertura de requisitos antes de aceptar chunks como evidencia.

### Fallo 4 — La granularidad del chunk pierde el rollup del presupuesto padre

- **Problema observado:** La respuesta de `/search` devuelve componentes sueltos: `UI-001` con 80 horas, `INT-001` con 120 horas, `AUTH-001` con 140 horas y `MIG-001` con 180 horas. Cada hit contiene una parte de un presupuesto histórico, pero no reconstruye el presupuesto completo ni explica cómo esas horas se relacionan con una estimación final para Casa Castaño.
- **Causa probable:** El chunking por componente es útil para recuperar piezas concretas, pero no hay una etapa que reagrupe resultados por `budget_id`, recupere totales del presupuesto padre, compare alcance completo ni convierta componentes aislados en una base de estimación.
- **Propuesta de solución:** Añadir un `ContextAssembler` que, después del retrieval, reagrupe chunks por `budget_id`, adjunte total hours, componentes hermanos, supuestos y señales de escala. Después, un `RAGQualityGate` debería decidir si esa evidencia es suficiente, insuficiente o requiere aclaración.

### Fallo 5 — El flujo se detiene antes de Augmentation y Generation

- **Problema observado:** La respuesta final del sistema es una lista de chunks con metadata y distancia. No genera módulos estimados, horas, supuestos, riesgos, exclusiones ni preguntas abiertas para el cliente.
- **Causa probable:** La arquitectura actual implementa Retrieval, pero no implementa las etapas de Augmentation y Generation del flujo RAG end-to-end.
- **Propuesta de solución:** Añadir `AugmentationBuilder` para construir un `EvidenceBundle` y `EstimateGenerator` para producir una estimación tipada y fundamentada en esa evidencia.

### Otros fallos observados

- El corpus trazado es demasiado pequeño: un presupuesto, cuatro chunks.
- El sistema no distingue señales firmes del cliente frente a ideas futuras o inciertas, como la posible expansión a Francia.
- La respuesta no explica por qué un chunk fue devuelto ni qué requisito de la transcripción cubre.

---

## 4. Propuesta de evolución arquitectónica

```text
PROPUESTA DE EVOLUCIÓN ARQUITECTÓNICA

[Frontend / Cliente]
  Usuario
  Meeting transcript
  Estimate view + evidence card
        |
        v
[Business backend FastAPI]
  NEW POST /estimate-from-transcript
  POST /search
  POST /embeddings/ingest
  GET  /metrics
        |
        v
[AI service futuro RAG end-to-end]

  NEW Query Understanding / TranscriptAnalyzer
    raw transcript
    -> structured requirements + canonical query

  NEW QueryPlanner
    structured requirements
    -> multiple focused retrieval queries

  NEW Metadata-filtered Retriever / RetrievalPolicy
    sector/type/scale filters + vector search
    -> accepted chunks or insufficient_evidence

  Existing SearchService
    focused retrieval queries
    -> pgvector cosine search

  NEW Context Assembler / AugmentationBuilder
    accepted chunks grouped by budget_id
    -> EvidenceBundle with parent-budget rollup

  NEW EstimateGenerator
    EvidenceBundle + structured requirements
    -> typed estimate proposal

  NEW RAGQualityGate
    estimate + evidence + requirements
    -> accept, repair, reject, or clarify

  NEW Repair / Clarify loop
    weak evidence or missing requirements
    -> retry retrieval or ask the user

[PostgreSQL + pgvector]
  documents
  chunks
```

### Responsabilidad y flujo de datos

La transcripción cruda entra por el backend y pasa primero por `QueryUnderstanding`, que extrae requisitos y una query canónica. `QueryPlanner` divide esa intención en búsquedas concretas; `Metadata-filtered Retriever` combina filtros y vector search; `Context Assembler` reagrupa chunks por `budget_id` y reconstruye evidencia con rollup del presupuesto padre; `EstimateGenerator` produce una estimación tipada; `RAGQualityGate` valida cobertura, grounding y suficiencia. La pieza más crítica para construir primero es `QueryUnderstanding`, porque sin requisitos estructurados todo lo demás sigue dependiendo de una query gigante y ambigua.

### Alineación con el flujo RAG de la Sesión 09

La evolución propuesta no se queda en repetir `Query -> Retrieval -> Augmentation -> Generation` como terminología genérica. En este sistema concreto, `Query` significa entender una transcripción ambigua y convertirla en requisitos estructurados; `Retrieval` significa buscar con filtros de metadata y vector search; `Augmentation` significa reagrupar chunks por presupuesto padre y construir evidencia útil; `Generation` significa producir una estimación validada, trazable y honesta sobre sus supuestos.

---

## Conclusión

El sistema actual es una base correcta de retrieval semántico persistente, pero todavía no es un RAG completo para estimaciones. La ejecución con `02_ambiguous.txt` demuestra que el sistema vectoriza la transcripción y devuelve chunks cercanos, pero no valida si esos chunks son suficientes, no detecta mismatch de dominio, no reconstruye el presupuesto padre y no genera un presupuesto.

El siguiente paso arquitectónico debe ser transformar la transcripción en requisitos estructurados y, desde ahí, cerrar el flujo hacia retrieval filtrado, context assembly, generation y quality gate.
