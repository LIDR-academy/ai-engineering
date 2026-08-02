# syntax=docker/dockerfile:1
# The syntax directive enables BuildKit features used below: RUN --mount=type=cache
# (persistent uv download/wheel cache) and COPY --link (content-addressable layers
# that survive base-image and cross-worktree changes without re-materializing).

# =============================================================================
# Stage 1 — Builder
# =============================================================================
# We use a multi-stage build so that build tools (uv, compilers, headers) stay
# out of the final image, keeping it small and reducing the attack surface.
FROM python:3.11-slim AS builder

# Install uv — a fast Python package manager written in Rust. Pin the minor
# version (instead of :latest) so the layer cache is deterministic across
# builds and across worktrees rather than silently invalidating on new releases.
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /bin/

WORKDIR /app

# uv build knobs:
# - UV_COMPILE_BYTECODE=1 pre-compiles .pyc at install time → faster cold start.
# - UV_LINK_MODE=copy avoids cross-device hardlink warnings when the uv cache
#   lives on a different mount (the cache mount below) than the target venv.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Install production dependencies only (no dev tools like pytest/ruff).
# --no-install-project skips installing our own package (we just need deps).
#
# The manifests are bind-mounted (not COPYed) so they never become part of a
# layer here, and the uv cache is mounted persistently: on repeated builds uv
# reuses already-downloaded wheels instead of re-fetching the multi-hundred-MB
# ML stack. The cache is shared by every build on this daemon, so switching
# worktrees/branches with an unchanged uv.lock is near-instant.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --locked --no-install-project --no-dev


# =============================================================================
# Stage 2 — Runtime
# =============================================================================
# Start from a clean slim image — no build tools, no uv, no cached layers
# from the builder stage. Only the virtual environment is carried over.
FROM python:3.11-slim AS runtime

# Never run containers as root. Create a dedicated user and group with FIXED
# numeric ids so that COPY --link --chown (which cannot resolve names — the
# linked layer has no view of this image's /etc/passwd) sets ownership correctly.
RUN groupadd --system --gid 10001 appgroup && \
    useradd --system --uid 10001 --gid appgroup --create-home appuser

WORKDIR /app

# Bring in the pre-built virtual environment from the builder stage.
# --chown sets ownership in the same layer (no second full-size chown layer),
# and --link makes this a standalone content-addressed layer that is reused
# across worktrees and is not invalidated by earlier-layer changes.
COPY --from=builder --chown=10001:10001 --link /app/.venv /app/.venv

# Copy application source code, owned by the runtime user in the same layer.
COPY --chown=10001:10001 app/ /app/app/

# Put the virtual environment's bin directory first on PATH so `python` and
# `uvicorn` resolve to the versions installed inside the venv.
ENV PATH="/app/.venv/bin:$PATH"
# Print logs immediately instead of buffering — critical for container logging.
ENV PYTHONUNBUFFERED=1
# Don't generate .pyc files at runtime; they add no value inside a container.
ENV PYTHONDONTWRITEBYTECODE=1

# Switch to the non-root user for all subsequent commands and at runtime.
USER appuser

EXPOSE 8000

# Docker-native health check. The orchestrator (Compose, Swarm, K8s) will
# mark the container as unhealthy if this probe fails consecutively.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
