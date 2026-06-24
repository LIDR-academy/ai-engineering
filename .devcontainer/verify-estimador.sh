#!/usr/bin/env bash
set -Eeuo pipefail

REPO_ROOT="${CODESPACE_VSCODE_FOLDER:-/workspaces/ai-engineering}"
PROJECT_DIR="$REPO_ROOT/estimador-cag"

export UV_LINK_MODE="${UV_LINK_MODE:-copy}"
export PATH="$HOME/.local/bin:$PATH"

echo ">>> verify-estimador: repo root is $REPO_ROOT"
echo ">>> verify-estimador: project dir is $PROJECT_DIR"

command -v uv >/dev/null 2>&1 || { echo ">>> uv is missing" >&2; exit 1; }

if [ ! -d "$PROJECT_DIR" ]; then
  echo ">>> Missing project directory: $PROJECT_DIR" >&2
  exit 1
fi

cd "$PROJECT_DIR"

uv run python - <<'PY'
from pathlib import Path
import sys

expected = "estimador-cag/.venv/bin/python"
executable = Path(sys.executable).as_posix()

print("python:", executable)

if expected not in executable and "estimador-cag/.venv/bin/python3" not in executable:
    raise SystemExit(
        "Expected uv to use estimador-cag/.venv/bin/python, got: "
        + executable
    )

import fastapi
import pydantic
import streamlit

print("pydantic:", pydantic.__version__)
print("fastapi:", fastapi.__version__)
print("streamlit:", streamlit.__version__)
PY

uv run ruff --version
uv run pytest --version
uv run fastapi --version
uv run streamlit --version

echo ">>> estimador-cag verification passed."
