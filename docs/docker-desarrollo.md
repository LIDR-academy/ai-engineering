# Docker y tests en desarrollo

Guía concisa para arrancar el monorepo con Docker y para correr tests del servicio FastAPI (`estimator`).

## Orquestación

El [`docker-compose.yml`](../docker-compose.yml) de la raíz solo hace `include:` de `estimator/` y `estimator-web/`. Arrancar desde la **raíz** pone los 5 servicios en una red compartida; Rails resuelve FastAPI en `http://estimator:8000`.

| Servicio | Imagen | Rol |
|----------|--------|-----|
| `estimator` | build `estimator:local` | FastAPI (IA) |
| `redis` | `redis/redis-stack:7.4.0-v0` | Cache semántico + RediSearch (obligatorio) |
| `estimator-postgres` | `pgvector/pgvector:pg16` | Corpus RAG / embeddings |
| `estimator-web` | build (Rails) | UI + backend de negocio |
| `postgres` | `postgres:16-alpine` | DB de Rails |

**Trap:** `docker compose up` desde un subdirectorio crea otro proyecto Compose y **otros volúmenes nombrados**. Para backend + frontend juntos, trabaja siempre desde la raíz del monorepo.

Los 5 servicios son los mínimos del diseño end-to-end (dos Postgres a propósito; redis-stack no sustituible por Redis alpine).

## Mínimos por objetivo

| Objetivo | Contenedores | Volúmenes nombrados |
|----------|--------------|---------------------|
| Verificar backend + frontend | los 5 | `redis_data`, `estimator_postgres_data`, `postgres_data`, `bundle_cache`, `node_modules` |
| Solo API IA (dev / scripts) | `estimator`, `redis`, `estimator-postgres` | `redis_data`, `estimator_postgres_data` |
| Solo Rails | `estimator-web`, `postgres` | `postgres_data`, `bundle_cache`, `node_modules` |

## Prerrequisitos (una vez)

```bash
cp estimator/.env.example estimator/.env
# Editar estimator/.env: OPENAI_API_KEY y/o ANTHROPIC_API_KEY
```

## Construir imágenes y arrancar

Desde la **raíz** del monorepo:

```bash
# Stack completo: construye estimator + estimator-web, pull del resto, arranca
docker compose up --build -d

# Solo backend IA (con build)
docker compose up --build -d estimator redis estimator-postgres
```

Seguimiento:

```bash
docker compose ps
docker compose logs -f estimator estimator-web
```

## Arrancar sin reconstruir

Si las imágenes ya existen:

```bash
docker compose up -d
# o explícito:
docker compose up -d --no-build

# Solo backend IA
docker compose up -d estimator redis estimator-postgres
```

Compose reutiliza `estimator:local` y la imagen de Rails; solo crea/arranca contenedores. Si faltan imágenes base (redis-stack, postgres, pgvector), las descarga.

## Cuándo reconstruir imágenes (y cuándo no)

### No hace falta rebuild

`docker compose up -d` basta cuando:

- Solo cambia código bajo bind mounts (`estimator/app`, `tests`, `data`, `scripts`, `alembic`; o el árbol de `estimator-web` vía `.:/rails`).
- Se reinician contenedores parados con las mismas imágenes.
- Cambian modelos LLM vía `PUT /api/v1/config/models` (Redis): no hace falta ni recreate.

Los bind mounts + `--reload` (uvicorn) / autoloader Rails cubren cambios de código. **Código ≠ rebuild.**

### Rebuild de `estimator`

```bash
docker compose build estimator
docker compose up -d estimator
```

Cuando cambian `pyproject.toml` / `uv.lock`, el `Dockerfile` o `.dockerignore` del estimator, o tras un fallo de cache de capas.

### Rebuild de `estimator-web`

```bash
docker compose build estimator-web
docker compose up -d estimator-web
```

Cuando cambian `Gemfile` / `Gemfile.lock` o el `Dockerfile` de Rails. Tras `bundle add` en el contenedor, el volumen `bundle_cache` ya persiste gems entre reinicios; el rebuild fija ese estado en la imagen.

### Recreate sin rebuild

```bash
docker compose up -d --force-recreate estimator
```

Cuando cambia `estimator/.env`: Settings está cacheado con `@lru_cache`; un `--reload` no basta.

También válido: `docker compose up --build -d` (rebuild + arranque de todo).

## Parar

```bash
docker compose down       # para contenedores; conserva volúmenes
docker compose down -v    # también borra volúmenes (resetea DBs y cachés)
```

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
