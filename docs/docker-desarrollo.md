# Docker y tests en desarrollo

Guía concisa para arrancar el monorepo con Docker y para correr tests del servicio FastAPI (`estimator`).

## Orquestación

El [`docker-compose.yml`](../docker-compose.yml) de la raíz declara `name: estimator` y hace `include:` de `estimator/` y `estimator-web/`. Arrancar desde la **raíz** pone los 5 servicios en una red compartida; Rails resuelve FastAPI en `http://estimator:8000`.

El nombre de proyecto fijo + tags de imagen fijos + volúmenes con nombre explícito hacen que **cualquier worktree o rama** reutilice las mismas imágenes y los mismos datos sembrados. No hace falta regenerar nada al cambiar de carpeta.

| Servicio | Imagen | Rol |
|----------|--------|-----|
| `estimator` | `estimator:local` | FastAPI (IA) |
| `redis` | `redis/redis-stack:7.4.0-v0` | Cache semántico + RediSearch (obligatorio) |
| `estimator-postgres` | `pgvector/pgvector:pg16` | Corpus RAG / embeddings |
| `estimator-web` | `estimator-web:local` | UI + backend de negocio |
| `postgres` | `postgres:16-alpine` | DB de Rails |

**Trap (subdirectorio):** `docker compose up` desde `estimator/` o `estimator-web/` crea otro proyecto Compose (sin el `name:` de la raíz) y **otros volúmenes**. Para backend + frontend juntos, trabaja siempre desde la raíz del monorepo.

**Trap (worktree):** sin `name: estimator` Compose usaría el nombre de la carpeta (`Estimator_S14` → `estimator_s14`) y montaría volúmenes vacíos. El compose raíz ya lo evita.

Los 5 servicios son los mínimos del diseño end-to-end (dos Postgres a propósito; redis-stack no sustituible por Redis alpine).

## Mínimos por objetivo

| Objetivo | Contenedores | Volúmenes (nombre Docker) |
|----------|--------------|---------------------------|
| Verificar backend + frontend | los 5 | `estimator_redis_data`, `estimator_postgres_data`, `estimator_web_postgres_data`, `estimator_web_bundle_cache`, `estimator_web_node_modules` |
| Solo API IA (dev / scripts) | `estimator`, `redis`, `estimator-postgres` | `estimator_redis_data`, `estimator_postgres_data` |
| Solo Rails | `estimator-web`, `postgres` | `estimator_web_postgres_data`, `estimator_web_bundle_cache`, `estimator_web_node_modules` |

## Prerrequisitos (una vez)

```bash
cp estimator/.env.example estimator/.env
# Editar estimator/.env: OPENAI_API_KEY y/o ANTHROPIC_API_KEY
```

## Arrancar sin reconstruir (caso habitual)

Si las imágenes ya existen (p. ej. construidas en otro worktree):

```bash
# Desde la raíz del monorepo
docker compose up -d
# o explícito:
docker compose up -d --no-build

# Solo backend IA
docker compose up -d estimator redis estimator-postgres
```

Compose reutiliza `estimator:local` y `estimator-web:local`; solo crea/arranca contenedores. Si faltan imágenes base (redis-stack, postgres, pgvector), las descarga.

Seguimiento:

```bash
docker compose ps
docker compose logs -f estimator estimator-web
```

## Construir imágenes (solo cuando haga falta)

```bash
# Primera vez en la máquina, o tras cambiar deps/Dockerfile
docker compose up --build -d

# Solo backend IA (con build)
docker compose up --build -d estimator redis estimator-postgres
```

## Cuándo reconstruir imágenes (y cuándo no)

### No hace falta rebuild

`docker compose up -d` basta cuando:

- Solo cambia código bajo bind mounts (`estimator/app`, `tests`, `data`, `scripts`, `exercises`, `alembic`; o el árbol de `estimator-web` vía `.:/rails`).
- Se cambia de rama o de worktree con las mismas deps.
- Se reinician contenedores parados con las mismas imágenes.
- Cambian modelos LLM vía `PUT /api/v1/config/models` (Redis): no hace falta ni recreate.

Los bind mounts + `--reload` (uvicorn) / autoloader Rails cubren cambios de código. **Código ≠ rebuild.**

### Rebuild de `estimator`

```bash
docker compose build estimator
docker compose up -d estimator
```

Cuando cambian `pyproject.toml` / `uv.lock`, el `Dockerfile` o `.dockerignore` del estimator, o tras un fallo de cache de capas. El Dockerfile usa BuildKit (`RUN --mount=type=cache` para uv) y pin CPU-only de torch: un `uv.lock` sin cambiar es casi gratis de re-materializar.

### Rebuild de `estimator-web`

```bash
docker compose build estimator-web
docker compose up -d estimator-web
```

Cuando cambian `Gemfile` / `Gemfile.lock` o el `Dockerfile` de Rails. El build usa cache mount de bundler; el volumen `estimator_web_bundle_cache` ya persiste gems entre reinicios.

### Recreate sin rebuild

```bash
docker compose up -d --force-recreate estimator
```

Cuando cambia `estimator/.env`: Settings está cacheado con `@lru_cache`; un `--reload` no basta.

## Parar

```bash
docker compose down       # para contenedores; conserva volúmenes
docker compose down -v    # también borra volúmenes (resetea DBs y cachés → hay que reseede)
```

## Migración desde un proyecto Compose antiguo (una vez)

Si ya tenías datos bajo un proyecto derivado del worktree (p. ej. `estimator_s13_*`), cópialos a los nombres fijos antes del primer `up` con el compose nuevo. Docker no renombra volúmenes:

```bash
# 1. Parar el stack viejo
docker compose -p estimator_s13 down

# 2. Crear destino y copiar (repetir por cada par from→to)
docker volume create estimator_redis_data
docker run --rm -v estimator_s13_redis_data:/from -v estimator_redis_data:/to alpine \
  sh -c "cd /from && cp -a . /to"

docker volume create estimator_postgres_data
docker run --rm -v estimator_s13_estimator_postgres_data:/from -v estimator_postgres_data:/to alpine \
  sh -c "cd /from && cp -a . /to"

docker volume create estimator_web_postgres_data
docker run --rm -v estimator_s13_postgres_data:/from -v estimator_web_postgres_data:/to alpine \
  sh -c "cd /from && cp -a . /to"

docker volume create estimator_web_bundle_cache
docker run --rm -v estimator_s13_bundle_cache:/from -v estimator_web_bundle_cache:/to alpine \
  sh -c "cd /from && cp -a . /to"

docker volume create estimator_web_node_modules
docker run --rm -v estimator_s13_node_modules:/from -v estimator_web_node_modules:/to alpine \
  sh -c "cd /from && cp -a . /to"

# 3. Retag imagen Rails si existía con el tag del proyecto viejo
docker tag estimator_s13-estimator-web:latest estimator-web:local

# 4. Arrancar SIN rebuild
docker compose up -d --no-build
```

Tras verificar pgvector, Rails DB y Redis, se pueden borrar los volúmenes/imágenes `estimator_s13_*` huérfanos.

## Puertos útiles

| URL / puerto | Servicio |
|--------------|----------|
| http://localhost:3000 | Rails |
| http://localhost:8000/health | FastAPI |
| http://localhost:8000/docs | Swagger |
| localhost:5432 | Postgres Rails |
| localhost:5433 | Postgres pgvector |
| localhost:6379 / :8001 | Redis / RedisInsight |

## Tests Python (`estimator`) con uv

### Entorno virtual

```bash
cd estimator
uv sync
uv run pytest -v
```

- `uv sync` crea (si no existe) el venv por defecto: **`estimator/.venv`** (gitignored).
- `uv run` usa ese `.venv` sin necesidad de activarlo.
- `uv sync` **sin flags** instala las deps del proyecto **y** el grupo `dev` (`pytest`, `pytest-asyncio`, `httpx`, `fakeredis`, `ruff`, etc. en `pyproject.toml`).
- La imagen Docker usa `uv sync --no-dev`: **no** incluye esas librerías de test.

### ¿Local o en Docker?

**Preferible en el host** con el comando de arriba:

- La imagen `estimator:local` no trae deps de test.
- La mayoría de tests usan fakes (`fakeredis`, mocks); no necesitan Redis/Postgres reales.
- Iteración más rápida.

Docker sirve para **servicios** (API viva, Redis Stack, pgvector), no como runner habitual de pytest.

### Pytest dentro del contenedor (opcional)

Contenedor: servicio `estimator`. Hay que instalar deps de test ad-hoc (se pierden al recrear el contenedor):

```bash
docker compose up -d estimator redis estimator-postgres
docker compose exec estimator bash -c '
  python -m ensurepip --upgrade &&
  python -m pip install --quiet pytest pytest-asyncio fakeredis httpx
'
docker compose exec estimator python -m pytest tests/ -v
```

## Tests Rails

```bash
docker compose exec estimator-web bin/rails test
```

El bundle de la imagen de desarrollo ya incluye los grupos test.
