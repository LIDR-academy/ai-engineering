# S12 — Verificación del plan «Agente de estimación (bucle manual)»

Fecha de verificación: **2026-07-22**  
Plan de referencia: `agente_s12_manual_3db32335.plan.md`  
Transcripción de aceptación: `sample_transcript_complex.txt`

## Veredicto

El plan está **implementado y operativo**. Tras corregir dos defectos que impedían una traza válida contra la API actual (`strict` schema inválido + ausencia de `reasoning.summary`), una ejecución fresca con `sample_transcript_complex.txt` **cumple los 5 criterios de aceptación**.

Evidencia principal: [`verification_trace_complex.txt`](./verification_trace_complex.txt)  
(`gpt-5`, `effort=medium`, `--stub`, 2026-07-22)

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
4. **Corpus real vacío** en este entorno: `budget_chunks` tiene **0 filas**. El path de retrieval real no se pudo validar end-to-end sin `--ingest`. La aceptación se verificó con `--stub` (red de seguridad del ejercicio).
5. **`exercises/` no está montado** en el `docker-compose` del servicio `estimator` (solo `app/`, `tests/`, `data/`, `scripts/`, alembic). Para ejecutar hay que `docker cp` de `exercises/` o montar el volumen.
6. **`example_trace_complex.txt` legado**: coherente en totales, pero la acción de `calculate_estimate` no muestra `reference_amounts` (formato antiguo) y las observaciones de móvil/analítica (1 hit) no cuadran con la matemática de 2 referencias (`total=3496.0` = mediana con 2 refs en móvil/BI). No debe usarse como evidencia primaria frente a `verification_trace_complex.txt`.

### Fixes aplicados durante esta verificación

- `agent_tools.py`: schema `filters` / `date_range` compatible con strict mode; `format_action` de `calculate_estimate` incluye `reference_amounts`.
- `agent_loop.py`: `reasoning={"effort": ..., "summary": "auto"}`.

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

## Ejecución de aceptación (evidencia viva)

```bash
docker cp exercises/. estimator:/app/exercises/
docker compose exec estimator python scripts/run_agent_s12.py \
  exercises/session-12/sample_transcript_complex.txt \
  --model gpt-5 --effort medium --stub \
  --out /tmp/verification_trace_complex.txt
# copia local: exercises/session-12/verification_trace_complex.txt
```

Scoring automático:

```bash
docker compose exec estimator python scripts/_score_s12_trace.py \
  /tmp/verification_trace_complex.txt
```

```
steps: 7
search_budgets: 6  PASS=True
calculate_estimate: 1  PASS=True
calc includes reference_amounts: True
status done: True
incomplete steps: none
empty reasoning steps: 0
components: 4 total=3651.3 sum=3651.3 coherent=True
ACCEPTANCE: True
```

---

## Criterios de aceptación (detalle)

### 1. Identifica más de un componente y hace más de una llamada a `search_budgets`

**PASS** — 4 componentes reconocibles; **6** llamadas a `search_budgets` con queries distintas (backend, SAP×2 con reformulación, móvil×2, analítica).

Extracto:

```
STEP 1  search_budgets(... backend ...)
STEP 2  search_budgets(... SAP ...)          → 0 matches → reformula
STEP 3  search_budgets(... SAP / industrial ...)
STEP 4  search_budgets(... mobile ...)
STEP 5  search_budgets(... mobile variant ...)
STEP 6  search_budgets(... analytics ...)
```

### 2. Llama a `calculate_estimate` con los componentes y sus referencias

**PASS** — STEP 7:

```
calculate_estimate(components=[
  Backend ...[940, 1150],
  Integración con SAP ...[860, 720],
  App móvil ...[780],
  Panel de analítica ...[560]
])
observation: total=3651.3h across 4 components
```

### 3. Termina por sí solo (sin bucle infinito ni corte a mitad)

**PASS** — `status: done` tras mensaje final del modelo; 7 steps << `max_steps=10`; no `max_steps_exceeded`.

### 4. Produce una estimación estructurada coherente

**PASS**

| Componente | Horas | Unbudgeted |
|---|---:|:---:|
| Backend de negocio con API | 1201.8 | no |
| Integración con SAP | 908.5 | no |
| App móvil repartidores | 897.0 | no |
| Panel de analítica | 644.0 | no |
| **Total** | **3651.3** | = suma exacta |

Coherencia aritmética: `1201.8 + 908.5 + 897.0 + 644.0 = 3651.3`.

### 5. La traza muestra, para cada paso, razonamiento + acción + observación

**PASS** — 7/7 steps con los tres campos; reasoning no vacío (p. ej. STEP 2 explica la reformulación SAP; STEP 3 documenta el cambio de sector a `industrial`).

---

## Resumen de criterios

| Criterio | Resultado |
|---|---|
| >1 componente y >1 `search_budgets` | PASS (4 comps, 6 searches) |
| `calculate_estimate` con referencias | PASS |
| Termina solo (`done`) | PASS |
| Estimación estructurada coherente | PASS |
| Traza reason + action + observation | PASS |

**Agente listo para el entregable del ejercicio**, con la salvedad de que esta evidencia usa `--stub`. Para el path con retrieval real hace falta ingerir el corpus de tareas (`scripts/build_task_corpus.py --ingest`) y montar/copiar `exercises/`.

---

## Artefactos generados en esta verificación

| Fichero | Rol |
|---|---|
| `exercises/session-12/verification_trace_complex.txt` | Traza fresca que cumple aceptación |
| `exercises/session-12/S12_verification.md` | Este informe |
| `scripts/_verify_s12_static.py` / `scripts/_score_s12_trace.py` | Helpers de comprobación usados aquí (no son parte del entregable del ejercicio) |
