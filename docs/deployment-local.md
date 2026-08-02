# Despliegue local (Sesión 15)

Arrancar el monorepo como microservicios con la frontera público/privado del ejercicio: solo el backend de negocio publica puerto al host.

## Nombres (enunciado ↔ este repo)

| Enunciado | Este monorepo |
|-----------|---------------|
| `ai-service` | `estimator` (FastAPI) |
| `business-backend` | `estimator-web` (Rails) |
| BBDD relacional | `postgres` (`postgres:16-alpine`) |
| BBDD vectorial | `estimator-postgres` (`pgvector/pgvector:pg16`) |
| — | `redis` (Redis Stack; CAG semántico — pieza extra necesaria) |

## Variables de entorno (una sola fuente)

La plantilla oficial es [`estimator/.env.example`](../estimator/.env.example). Cópiala una vez:

```bash
cp estimator/.env.example estimator/.env
# Rellena OPENAI_API_KEY y/o ANTHROPIC_API_KEY (y el resto si aplica)
```

| Enunciado | En este repo |
|-----------|--------------|
| `LLM_API_KEY` | `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` |
| `AI_SERVICE_TOKEN` | `ESTIMATE_API_KEY` (+ `RETRIEVAL_API_KEY` para retrieval) |
| `AI_SERVICE_URL` | `ESTIMATOR_API_BASE_URL` (`http://estimator:8000` en compose) |

**Fuente única de secretos:** `estimator/.env`.

- El servicio IA lo carga entero con `env_file`.
- Rails **no** monta ese fichero: Compose interpola solo `ESTIMATE_API_KEY` y `RETRIEVAL_API_KEY` hacia su `environment:` (la clave del LLM no entra en el contenedor web).

Por eso casi todos los comandos llevan `--env-file estimator/.env` (alimenta la interpolación `${VAR}` del YAML). Alternativa permanente en la shell: `set COMPOSE_ENV_FILES=estimator/.env` (PowerShell: `$env:COMPOSE_ENV_FILES="estimator/.env"`).

No crees un segundo `.env` en la raíz ni en `estimator-web/` con copias de esas keys.

Auth servicio→servicio: header `X-API-Key` (comparación constant-time). El endpoint `/health` no exige key.

## Arranque

Desde la raíz del monorepo:

```bash
# Modo deploy local (ejercicio): IA y datastores sin ports al host
docker compose --env-file estimator/.env \
  -f docker-compose.yml -f docker-compose.deploy.yml up --build
```

Los dos `-f` **fusionan** una sola config (no son dos stacks): el primero es la base (`include:` de ambos subproyectos); el segundo quita puertos internos y hace que Rails espere a `estimator` healthy.

```bash
# Modo desarrollo (Swagger/httpie en :8000, DBs en host)
docker compose --env-file estimator/.env up --build
```

Detalle de DX, rebuilds y volúmenes: [`docker-desarrollo.md`](docker-desarrollo.md).

## Comprobaciones (Paso 7)

Con el overlay de deploy (siempre con `--env-file estimator/.env`):

1. `docker compose --env-file estimator/.env -f docker-compose.yml -f docker-compose.deploy.yml ps` — servicios arriba; `estimator` y Postgres healthy.
2. `http://localhost:3000` — UI del backend de negocio.
3. `http://localhost:8000` — **no** responde (sin `ports:` en el servicio IA).
4. Estimación desde la UI: Rails → FastAPI (`X-API-Key`) → pgvector → respuesta.
5. `… down && … up` — vuelve sin pasos manuales (datos en volúmenes nombrados).
