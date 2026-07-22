# S12 — Verificación del plan «Agente de estimación (bucle manual)»

Fecha de verificación: **2026-07-22**  
Plan de referencia: `agente_s12_manual_3db32335.plan.md`  
Transcripción de aceptación: `sample_transcript_complex.txt`

## Veredicto

El plan está **implementado y operativo**. Tras corregir defectos de schema/reasoning y del backend de retrieval real, una ejecución fresca con `sample_transcript_complex.txt` **cumple los 5 criterios de aceptación** tanto con stub como con **pgvector real**.

| Evidencia | Modo | Resultado |
|---|---|---|
| [`verification_trace_complex_real.txt`](./verification_trace_complex_real.txt) | **retrieval real** (`gpt-5` / `medium`, sin `--stub`) | **ACCEPTANCE: True** (primaria) |
| [`verification_trace_complex.txt`](./verification_trace_complex.txt) | stub | ACCEPTANCE: True (control) |

---

## Checklist del plan (fases 1–6)

| ID plan | Entregable | Estado | Evidencia |
|---|---|---|---|
| `schemas` | `app/generation/agentic/agent_schemas.py` | Hecho | `AgentStep`, `AgentResult`, `AgentEstimate`, `SearchBudgetsArgs`, `CalculateEstimateArgs`, `ToolFn` |
| `tools` | `app/generation/agentic/agent_tools.py` | Hecho (+fix) | `AGENT_TOOLS` plano + `strict: true`; `calculate_estimate` determinista (`CONTINGENCY_FACTOR=0.15`); formatters de traza |
| `search-backend` | Registry + `search_budgets` real/stub | Hecho (ubicación distinta) | `app/generation/agentic/tool_registry.py` (`build_agent_tool_registry`, `search_budgets_impl`, stub). **No** está en `dependencies.py` como decía el plan |
| `agent-loop` | `app/generation/agentic/agent_loop.py` | Hecho (+fix) | Bucle manual Responses API, `previous_response_id`, `function_call_output` + `call_id`, `asyncio.gather`, `DEFAULT_MAX_STEPS=10` |
| `run-script` | `scripts/run_agent_s12.py` | Hecho | Flags `--model`, `--effort`, `--stub`, `--max-steps`, `--out` |
| `validate-complex` | Criterios con transcript complex | Hecho (re-ejecutado) | Ver sección de criterios abajo |

### Fase 7 (opcional del plan)

No exigida por el ejercicio: endpoint FastAPI, `validate_estimate`, tests unitarios. **No implementados** (fuera del mínimo).

---

## Desviaciones / hallazgos respecto al plan

1. **Composition root**: el plan pedía `dependencies.py`; la factory vive en `tool_registry.py` (comentario: evitar cargar todo el stack RAG al arrancar el script). `search_budgets_impl` importa `rag` de forma perezosa ahí.
2. **Schema `strict: true` roto** (bloqueante): OpenAI exige que, en modo estricto, todo key de `properties` figure en `required` (opcionales vía `null`). El schema original fallaba con:
   > `Invalid schema for function 'search_budgets'... Missing 'year_min'`
3. **Razonamiento vacío en traza**: sin `reasoning.summary="auto"` la API no devuelve summaries → la traza mostraba `reasoning: —`. Corregido en `agent_loop.py`.
4. **Corpus de tareas**: ingerido en esta verificación — `1543` filas `chunk_type=historical_task` (60 proyectos).
5. **`exercises/` montado** en `estimator/docker-compose.yml` (`./exercises:/app/exercises`) y el servicio recreado.
6. **`example_trace_complex.txt` legado**: coherente en totales, pero la acción de `calculate_estimate` no muestra `reference_amounts` (formato antiguo) y las observaciones de móvil/analítica (1 hit) no cuadran con la matemática de 2 referencias (`total=3496.0`). Preferir las trazas `verification_trace_complex*.txt`.
7. **Bug retrieval real**: `search_budgets_impl` llamaba `runtime_retrieval.effective(...)` (API de modelos LLM); el correcto es `effective_search_mode()` / `effective_rerank()`.
8. **Umbral de distancia**: `TASK_HOURS_DISTANCE_THRESHOLD=0.45` es demasiado estricto para queries de componente sobre chunks de tarea (vecinos ~0.60–0.65 con filtro de sector). `search_budgets` usa `max(RETRIEVAL_DISTANCE_THRESHOLD, 0.75)`.
9. **Escala de horas con corpus real**: los hits son tareas históricas (~12–53 h), no presupuestos de componente completo; el total real (~136 h) es coherente aritméticamente pero subestima un proyecto de plataforma. El stub sigue siendo la comparación de “componente entero”.

### Fixes aplicados durante esta verificación

- `agent_tools.py`: schema `filters` / `date_range` compatible con strict mode; `format_action` de `calculate_estimate` incluye `reference_amounts`.
- `agent_loop.py`: `reasoning={"effort": ..., "summary": "auto"}`.
- `tool_registry.py`: API correcta de `RuntimeRetrievalConfig` + umbral de distancia para búsquedas de componente.
- `estimator/docker-compose.yml`: volumen `./exercises:/app/exercises`.

---

## Comprobaciones estáticas ejecutadas

Comando (contenedor `estimator`):

```bash
docker compose exec estimator python scripts/_verify_s12_static.py
```

Resultado relevante:

```
AGENT_TOOLS: ['search_budgets', 'calculate_estimate']
strict: True
flat schema keys: ['description', 'name', 'parameters', 'strict', 'type']
registry stub: ['calculate_estimate', 'search_budgets']
agent_tools imports rag? False
has MAX/DEFAULT_MAX_STEPS: True
uses previous_response_id: True
uses asyncio.gather: True
function_call_output: True
calc 2-refs-each total: 3496.0
```

`calculate_estimate` determinista (mediana × 1.15):

| Componente | Refs | Horas |
|---|---|---|
| Backend | 1150, 940 | 1201.8 |
| SAP | 860, 720 | 908.5 |
| Móvil | 780, 640 | 816.5 |
| Analítica | 560, 430 | 569.2 |
| **Total** | | **3496.0** |

---

## Preparación del entorno (retrieval real)

```bash
# 1) Montar exercises/ (ya en estimator/docker-compose.yml) y recrear
docker compose up -d estimator --force-recreate

# 2) Ingerir corpus de tareas (JSON existente → pgvector)
docker compose exec estimator python scripts/build_task_corpus.py \
  --ingest-only --base-url http://localhost:8000
# → Task corpus: 60 projects / 1543 tasks — 60 ingested
```

Comprobación DB: `historical_task | 1543`.

---

## Ejecución de aceptación — retrieval real (evidencia primaria)

```bash
docker compose exec estimator python scripts/run_agent_s12.py \
  exercises/session-12/sample_transcript_complex.txt \
  --model gpt-5 --effort medium \
  --out exercises/session-12/verification_trace_complex_real.txt
```

Scoring:

```
file: verification_trace_complex_real.txt
steps: 5
search_budgets: 4  PASS=True
calculate_estimate: 1  PASS=True
calc includes reference_amounts: True
status done: True
incomplete steps: none
empty reasoning steps: 0
components: 4 total=135.7 sum=135.7 coherent=True
ACCEPTANCE: True
```

Logs del retrieval (ej.): `rag_retrieve_done ... results=10 search_mode=vector vector_hits=10` en las 4 búsquedas paralelas.

---

## Ejecución de control — stub (evidencia secundaria)

```bash
docker compose exec estimator python scripts/run_agent_s12.py \
  exercises/session-12/sample_transcript_complex.txt \
  --model gpt-5 --effort medium --stub \
  --out exercises/session-12/verification_trace_complex.txt
```

```
steps: 7
search_budgets: 6
calculate_estimate: 1
components: 4 total=3651.3 sum=3651.3
ACCEPTANCE: True
```

---

## Criterios de aceptación (detalle — traza real)

### 1. Identifica más de un componente y hace más de una llamada a `search_budgets`

**PASS** — 4 componentes; **4** llamadas a `search_budgets` en paralelo (backend, SAP, móvil, analítica), cada una con hits reales del corpus.

```
STEP 1  search_budgets(... backend ...)     → 10 matches; median=28.5h
STEP 2  search_budgets(... SAP ...)         → 10 matches; median=28.0h
STEP 3  search_budgets(... mobile ...)      → 10 matches; median=26.0h
STEP 4  search_budgets(... analytics ...)   → 10 matches; median=35.5h
```

### 2. Llama a `calculate_estimate` con los componentes y sus referencias

**PASS** — STEP 5 con `reference_amounts` tomados de las observaciones (10 refs por componente).

```
calculate_estimate(components=[
  Backend ...[31, 24, 29, 42, 17, 17, 29, 33, 28, 24],
  Integración ERP SAP ...[41, 37, 52, 25, 33, 25, 23, 24, 17, 31],
  App móvil ...[29, 33, 28, 24, 12, 20, 53, 34, 20, 17],
  Panel de analítica ...[47, 42, 25, 36, 44, 26, 28, 35, 30, 46]
])
observation: total=135.7h across 4 components
```

### 3. Termina por sí solo (sin bucle infinito ni corte a mitad)

**PASS** — `status: done`; 5 steps << `max_steps=10`.

### 4. Produce una estimación estructurada coherente

**PASS**

| Componente | Horas | Unbudgeted |
|---|---:|:---:|
| Backend de negocio con API | 32.8 | no |
| Integración ERP SAP | 32.2 | no |
| App móvil repartidores | 29.9 | no |
| Panel de analítica | 40.8 | no |
| **Total** | **135.7** | = suma exacta |

Nota: horas a escala de **tarea** histórica (corpus `historical_task`), no de componente completo.

### 5. La traza muestra, para cada paso, razonamiento + acción + observación

**PASS** — 5/5 steps con los tres campos y reasoning no vacío (incl. reflexión del modelo sobre que los hits parecen tareas, no presupuestos enteros).

---

## Resumen de criterios

| Criterio | Stub | Retrieval real |
|---|---|---|
| >1 componente y >1 `search_budgets` | PASS (6) | PASS (4) |
| `calculate_estimate` con referencias | PASS | PASS |
| Termina solo (`done`) | PASS | PASS |
| Estimación estructurada coherente | PASS | PASS |
| Traza reason + action + observation | PASS | PASS |

**Agente listo** con evidencia de retrieval real en `verification_trace_complex_real.txt`.

---

## Artefactos generados en esta verificación

| Fichero | Rol |
|---|---|
| `exercises/session-12/verification_trace_complex_real.txt` | Traza con pgvector (evidencia primaria) |
| `exercises/session-12/verification_trace_complex.txt` | Traza con stub (control) |
| `exercises/session-12/S12_verification.md` | Este informe |
| `scripts/_verify_s12_static.py` / `scripts/_score_s12_trace.py` | Helpers de comprobación |
