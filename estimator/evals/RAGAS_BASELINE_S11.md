# Session 11 — Citación verificable + baseline RAGAS

Entregable del pre-work de la Sesión 11. Cubre las dos partes del enunciado:

1. **Citación verificable a nivel de línea** (Parte 1).
2. **Baseline de calidad de generación con RAGAS** sobre el golden set extendido (Parte 2).

Todo el código (schema, prompt, verificación, harness) está en inglés; estas notas y el
`ground_truth` del golden set van en español, como permite el enunciado.

---

## Qué se cambió (Parte 1)

- **Schema** (`app/generation/rag/schemas.py`):
  - `SourceReference{chunk_id, document_id, evidence}` — la cita verificable de una línea.
  - `TaskItem` (cada línea de estimación) ahora lleva `grounded: bool` y `sources: list[SourceReference]`
    (antes `list[int]`). Un `model_validator` impone la regla de integridad:
    `grounded=True` ⇒ ≥1 fuente; `grounded=False` ⇒ sin fuentes y sin horas inventadas.
  - `CitationReport` / `LineCitation` — la salida del verificador.
- **Ensamblado de contexto** (`context_assembler.py`): cada `<source>` ahora expone también
  `document_id`, para que el modelo pueda copiar el presupuesto histórico concreto en cada cita.
- **Prompt de generación** (`prompt_builder.py`): atribución obligatoria por línea — `chunk_id`
  exacto del `<source>`, `document_id`, y `evidence` **verbatim** (no parafraseado); `grounded=false`
  cuando no hay soporte (sin horas a ojo).
- **Verificación post-generación** (`validation.py::verify_citations`): recorre cada línea y
  comprueba que todo `chunk_id` citado esté en el conjunto de chunks recuperados. Distingue líneas
  *grounded*, *dangling* (id inventado) e *insufficient* (sin datos). Se integra en el orquestador
  (`estimator.py`, con un reintento correctivo + downgrade a `confidence=low` si no se repara) y en
  el stage `/v1/estimate/stages/generate` (campo `citation_report` + `fabricated_source_ids`).

El contrato HTTP no cambia de forma: solo se enriquece el cuerpo con las fuentes por línea.

---

## Reporte de verificación de citaciones (obligatorio)

Generado por `scripts/demo_verify_citations_s11.py` (offline, sin red): una estimación grounded
real con **una citación colgante plantada a propósito** (`chunk_id=999`, nunca recuperado) y una
línea sin datos suficientes. Demuestra los tres criterios de aceptación de la Parte 1.

```
=== Citation verification report ===
lines: 4  grounded: 2  dangling: 1  insufficient: 1
verified citations: 2
dangling citations: ['999']

module                   line                     status        cited -> dangling
----------------------------------------------------------------------------------------
Authentication & SCA     OAuth 2.0 backend        grounded      ['101'] -> -
PSD2 & Open Banking      Open banking connectors  grounded      ['102'] -> -
Ledger                   Transaction ledger       dangling      ['999'] -> ['999']
Reporting                Regulatory reporting     insufficient  [] -> -

ACCEPTANCE: PASS
```

- **grounded=True con fuente real**: las 2 primeras líneas citan chunks 101/102 que sí estaban en
  el contexto.
- **citación colgante detectada**: la línea "Transaction ledger" cita 999 → marcada `dangling`.
- **sin datos suficientes**: "Regulatory reporting" no se rellena con horas, se marca `insufficient`
  y se expresa como Assumption.

El informe sobre una estimación **real del pipeline** (no plantada) se adjunta por cada consulta
en `evals/ragas_baseline_s11.json` (campo `citation_report` por query).

---

## Baseline RAGAS (Parte 2)

- **Golden set**: `evals/golden_generation_s11.json` — extiende las 5 consultas Q1–Q5 del golden
  set de la Sesión 10 (`golden_retrieval.json`) añadiendo un `ground_truth` (estimación de
  referencia por experto, en engineer-days ≈ horas/8, derivada de los presupuestos relevantes).
- **Harness**: `scripts/eval_ragas_s11.py` (recoge muestras ejecutando el pipeline real
  reformulate→retrieve→assemble→generate) + `scripts/score_ragas_s11.py` (puntúa con RAGAS).
- **Juez**: `gpt-4o-mini`; **embeddings**: `text-embedding-3-small`. Métricas:
  `faithfulness`, `answer_relevancy`, `context_precision`, `context_recall`.

> **Nota operativa**: `ragas 0.4.x` importa en carga `langchain_community.chat_models.vertexai`,
> que el `langchain-community` actual del proyecto ya no expone. El scoring en el venv del
> contenedor `estimator` **no es viable** (sin `pip` en el venv de producción). Flujo de dos pasos:
> ```bash
> # 1) recoger muestras (montar evals/ ad-hoc; no está en el bind-mount por defecto)
> docker compose run --rm -v ./estimator/evals:/app/evals estimator \
>   python scripts/eval_ragas_s11.py --collect-only evals/ragas_samples_s11.json
> # 2) puntuar en contenedor Python aislado (Opción A; fallback tras fallar Opción B)
> docker run --rm --env-file estimator/.env \
>   -v ./estimator/evals:/evals -v ./estimator/scripts:/scripts \
>   python:3.11-slim bash -c \
>   "pip install -q ragas langchain-openai datasets openai && \
>    python /scripts/score_ragas_s11.py /evals/ragas_samples_s11.json --out /evals/ragas_baseline_s11.json"
> ```

### Tabla de métricas (4 métricas × 5 consultas + promedio)

Run real del **2026-06-29** (juez `gpt-4o-mini`, embeddings `text-embedding-3-small`). Datos completos en
`evals/ragas_baseline_s11.json` (muestras en `evals/ragas_samples_s11.json`).

| query | faithfulness | answer_relevancy | context_precision | context_recall |
|---|---|---|---|---|
| Q1 | 0.531 | 0.187 | 1.000 | 0.000 |
| Q2 | 0.364 | 0.000 | 1.000 | 0.000 |
| Q3 | 0.629 | 0.170 | 1.000 | 0.714 |
| Q4 | 0.462 | 0.240 | 1.000 | 0.667 |
| Q5 | 0.290 | 0.076 | 1.000 | 0.714 |
| **average** | 0.455 | 0.134 | 1.000 | 0.419 |

### Verificación de citaciones sobre las estimaciones reales (las 5)

Salida real del verificador (`verify_citations`) sobre cada estimación generada por el pipeline:

| query | líneas | grounded | dangling | insufficient | citas verificadas |
|---|---|---|---|---|---|
| Q1 | 44 | 28 | 0 | 16 | 32 |
| Q2 | 40 | 27 | 0 | 13 | 33 |
| Q3 | 37 | 22 | 0 | 15 | 27 |
| Q4 | 28 | 28 | 0 | 0 | 32 |
| Q5 | 41 | 41 | 0 | 0 | 88 |
| **total** | **190** | **146** | **0** | **44** | **212** |

**Citaciones colgantes: 0/190 líneas.** Cada línea `grounded=True` cita un chunk real del contexto;
las 44 líneas sin soporte se marcan `insufficient` (no inventan horas), no se rellenan.

### Nota de hallazgos (lo que más chirría)

- **`context_precision` perfecto (1.0); `context_recall` mejora a 0.42 de media** (Q3/Q4/Q5 > 0).
  Sigue lastrado por el desajuste engineer-days (ground_truth) vs horas (corpus), pero el juez
  atribuye más contexto que en el run anterior. Q1/Q2 siguen en 0.
- **`answer_relevancy` sigue baja (0.13 de media)** pero ya no es ≈0 en todas: artefacto de formato
  pregunta (brief) vs respuesta (tabla estructurada), no señal de calidad pura.
- **`faithfulness` media 0.45** (antes 0.55): el generador descompone en subtareas; el juez no
  atribuye 1:1 cada cifra derivada a la del `<source>`. La citación verificable separa "la cita
  existe" de "la cifra se deduce de la cita" — **0 citaciones colgantes en 190 líneas**.
- **Q4 ya no es el peor caso de grounding:** 28/28 líneas grounded (run anterior: 6/31).

**Resumen para el directo:** citaciones colgantes 0/190; `context_recall` 0.42 (mejor que baseline
previo 0.11); `answer_relevancy` 0.13; `faithfulness` 0.45 con `context_precision` 1.0.
