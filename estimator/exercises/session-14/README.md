# Sesión 14 — Sistema multi-agente: supervisor, mínimo privilegio e intervención humana

En la Sesión 13 el flujo de estimación pasó a ser un **grafo explícito**. Esta sesión
cruza la frontera: **quien decide qué se ejecuta a continuación deja de ser el código
y pasa a ser el modelo**.

## Lo que ya tenías (y no se toca)

- El estado tipado de la S13 es la pizarra compartida. `SupervisorState` **hereda** de
  `EstimationState`.
- El checkpointer (`AsyncPostgresSaver`) se comparte; el router namespacea los
  `thread_id` como `s14:<estimation_id>`.
- Las tools son las de la S12 (`search_budgets`, `derive_task_hours` ≈
  `calculate_estimate`, `validate_estimate`). Se **reparten**, no se crean nuevas.

El flujo S13-live y `/v1/estimate/graph` quedan **intactos**.

## Niveles

1. **Supervisor + agentes** — topología estrella con `StateGraph` + `Command`; cada
   agente con mínimo privilegio de tools.
2. **HITL** — `interrupt()` cuando confianza baja / fuera de rango / sin precedente;
   `status = awaiting_human_review` + `POST …/resume`.
3. **Privilegio + auditoría** — `guarded_dispatch` + `agent_contributions` /
   `agent_action` en structlog.

## Cómo ejecutar

```bash
# Smoke offline (MemorySaver + stub). Necesita OPENAI_API_KEY.
uv run python scripts/run_supervisor_s14.py --memory --stub \
    --out exercises/session-14/example_run_edge_case.txt

# HTTP
http POST :8000/v1/estimate/supervisor X-API-Key:$ESTIMATE_API_KEY \
     transcript=@exercises/session-14/sample_transcript_edge_case.txt
http POST :8000/v1/estimate/supervisor/<id>/resume X-API-Key:$ESTIMATE_API_KEY \
     decision=approve note="revisado"
```

## Material

| Fichero | Para qué |
|---|---|
| `sample_transcript_edge_case.txt` | Dispara la pausa humana (dominio sin precedente). |
| `sample_transcript_happy_path.txt` | Contraste con componentes análogos. |
| `example_run_edge_case.txt` | Traza del entregable (pausa + resume). |
