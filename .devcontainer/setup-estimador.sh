#!/usr/bin/env bash
set -Eeuo pipefail

REPO_ROOT="${CODESPACE_VSCODE_FOLDER:-/workspaces/ai-engineering}"
PROJECT_DIR="$REPO_ROOT/estimador-cag"

export UV_LINK_MODE="${UV_LINK_MODE:-copy}"
export PATH="$HOME/.local/bin:$PATH"

install_pager_defaults() {
  local shell_rc="$1"
  local start_marker="# SESSION08_PAGER_DEFAULTS_START"
  local end_marker="# SESSION08_PAGER_DEFAULTS_END"

  touch "$shell_rc"

  if grep -q "$start_marker" "$shell_rc"; then
    return 0
  fi

  {
    echo ""
    echo "$start_marker"
    echo "export GIT_PAGER=cat"
    echo "export PAGER=cat"
    echo "export LESS=FRX"
    echo "$end_marker"
  } >> "$shell_rc"
}

install_pager_defaults "$HOME/.zshrc"
install_pager_defaults "$HOME/.bashrc"

echo ">>> setup-estimador: repo root is $REPO_ROOT"
echo ">>> setup-estimador: project dir is $PROJECT_DIR"

if ! command -v uv >/dev/null 2>&1; then
  echo ">>> uv not found. Installing uv for the current user..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"

install_pager_defaults() {
  local shell_rc="$1"
  local start_marker="# SESSION08_PAGER_DEFAULTS_START"
  local end_marker="# SESSION08_PAGER_DEFAULTS_END"

  touch "$shell_rc"

  if grep -q "$start_marker" "$shell_rc"; then
    return 0
  fi

  {
    echo ""
    echo "$start_marker"
    echo "export GIT_PAGER=cat"
    echo "export PAGER=cat"
    echo "export LESS=FRX"
    echo "$end_marker"
  } >> "$shell_rc"
}

install_pager_defaults "$HOME/.zshrc"
install_pager_defaults "$HOME/.bashrc"
fi

if [ ! -d "$PROJECT_DIR" ]; then
  echo ">>> Missing project directory: $PROJECT_DIR" >&2
  exit 1
fi

cd "$PROJECT_DIR"

echo ">>> Syncing estimador-cag with dev extras..."
uv sync --extra dev

echo ">>> Registering Jupyter kernel only if ipykernel is available..."
if uv run python -c 'import ipykernel' >/dev/null 2>&1; then
  uv run python -m ipykernel install --user --name=lidr-estimador-cag --display-name='LIDR estimador-cag'
else
  echo ">>> ipykernel is not importable. Skipping kernel registration."
fi

CLINE_SETUP="$REPO_ROOT/.devcontainer/cline-config/setup-cline.sh"
if [ -f "$CLINE_SETUP" ]; then
  echo ">>> Running Cline setup as non fatal bootstrap..."
  bash "$CLINE_SETUP" || echo ">>> Cline setup failed, continuing because app toolchain is ready."
fi

echo ">>> estimador-cag setup complete."
