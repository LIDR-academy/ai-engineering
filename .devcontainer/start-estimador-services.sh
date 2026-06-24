#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-${ESTIMADOR_START_MODE:-api}}"

REPO_ROOT="${CODESPACE_VSCODE_FOLDER:-/workspaces/ai-engineering}"
PROJECT_DIR="$REPO_ROOT/estimador-cag"

cd "$PROJECT_DIR"

export REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"
export ESTIMADOR_BACKEND_URL="${ESTIMADOR_BACKEND_URL:-http://localhost:8000}"

log() {
  printf '[estimador] %s\n' "$1"
}

show_help() {
  cat <<'TXT'
[estimador] Startup modes:
  none   Start nothing. Print this help only.
  redis  Start Redis only.
  api    Start Redis and FastAPI.
  ui     Start Redis, FastAPI, and Streamlit.
  all    Alias for ui.

Manual commands:
  bash .devcontainer/start-estimador-services.sh api
  bash .devcontainer/start-estimador-services.sh ui
  bash .devcontainer/start-estimador-services.sh none
TXT
}

wait_for_redis() {
  log "Checking Redis..."
  for attempt in {1..30}; do
    if docker compose exec -T redis redis-cli ping >/tmp/estimador-redis-ping.log 2>&1; then
      log "Redis is ready."
      return 0
    fi

    if [ "$attempt" -eq 30 ]; then
      log "Redis did not become ready."
      cat /tmp/estimador-redis-ping.log || true
      exit 1
    fi

    sleep 1
  done
}

start_redis() {
  log "Starting Redis..."
  docker compose up -d redis
  wait_for_redis
}

stop_fastapi() {
  log "Stopping stale FastAPI process..."
  pkill -f "uvicorn app.main:app" || true
  sleep 1
}

stop_streamlit() {
  log "Stopping stale Streamlit process..."
  pkill -f "streamlit run streamlit_app.py" || true
  sleep 1
}

ensure_port_free() {
  local port="$1"
  local label="$2"

  if ss -ltn | grep -q ":${port} "; then
    log "Port ${port} is already occupied by an unknown process for ${label}."
    ss -ltnp | grep ":${port} " || true
    exit 1
  fi
}

start_fastapi() {
  if curl -fsS http://localhost:8000/health >/tmp/estimador-health.json 2>/tmp/estimador-health.err; then
    log "FastAPI is already healthy."
    cat /tmp/estimador-health.json
    echo
    return 0
  fi

  stop_fastapi
  ensure_port_free 8000 "FastAPI"

  log "Starting FastAPI on port 8000..."
  nohup env REDIS_URL="$REDIS_URL" uv run uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    > /tmp/estimador-fastapi.log 2>&1 &

  log "Waiting for FastAPI..."
  for attempt in {1..40}; do
    if curl -fsS http://localhost:8000/health >/tmp/estimador-health.json 2>/tmp/estimador-health.err; then
      log "FastAPI is ready."
      cat /tmp/estimador-health.json
      echo
      return 0
    fi

    if [ "$attempt" -eq 40 ]; then
      log "FastAPI did not become ready."
      log "FastAPI log:"
      tail -120 /tmp/estimador-fastapi.log || true
      exit 1
    fi

    sleep 1
  done
}

start_streamlit() {
  if curl -fsS http://localhost:8501 >/tmp/estimador-streamlit.html 2>/tmp/estimador-streamlit.err; then
    log "Streamlit is already healthy."
    return 0
  fi

  stop_streamlit
  ensure_port_free 8501 "Streamlit"

  log "Starting Streamlit on port 8501..."
  nohup env ESTIMADOR_BACKEND_URL="$ESTIMADOR_BACKEND_URL" uv run streamlit run streamlit_app.py \
    --server.address 0.0.0.0 \
    --server.port 8501 \
    > /tmp/estimador-streamlit.log 2>&1 &

  log "Waiting for Streamlit..."
  for attempt in {1..40}; do
    if curl -fsS http://localhost:8501 >/tmp/estimador-streamlit.html 2>/tmp/estimador-streamlit.err; then
      log "Streamlit is ready."
      return 0
    fi

    if [ "$attempt" -eq 40 ]; then
      log "Streamlit did not become ready."
      log "Streamlit log:"
      tail -120 /tmp/estimador-streamlit.log || true
      exit 1
    fi

    sleep 1
  done
}

case "$MODE" in
  none)
    show_help
    log "No services started."
    ;;
  redis)
    start_redis
    log "Redis ready."
    ;;
  api)
    start_redis
    start_fastapi
    log "API services ready."
    log "FastAPI log: /tmp/estimador-fastapi.log"
    ;;
  ui|all)
    start_redis
    start_fastapi
    start_streamlit
    log "API and UI services ready."
    log "FastAPI log:   /tmp/estimador-fastapi.log"
    log "Streamlit log: /tmp/estimador-streamlit.log"
    ;;
  *)
    log "Unknown startup mode: $MODE"
    show_help
    exit 2
    ;;
esac
