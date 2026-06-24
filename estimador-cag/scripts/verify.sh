#!/bin/bash
# Script de verificacion rapida despues de setup
set -e

echo ">>> Verificando entorno LIDR Task 2+3..."
cd "$(dirname "$0")/.."

# 1. Dependencias
uv sync

# 2. Lint
uv run ruff check app/ tests/ streamlit_app.py

# 3. Tests
uv run pytest tests/ -v

# 4. Syntax
for f in app/main.py app/config.py app/services/llm_service.py app/services/provider.py app/services/cache.py app/middleware/logging.py app/routers/estimations.py app/schemas/estimation.py streamlit_app.py; do
    uv run python -m py_compile "$f"
done

# 5. Import checks
uv run python -c "from app.main import app; print('✅ FastAPI import OK')"
uv run python -c "from app.services.llm_service import estimate_stream; print('✅ Streaming import OK')"
uv run python -c "from app.services.provider import get_provider; print('✅ Provider wrapper OK')"
uv run python -c "from app.services.cache import cached_estimate; print('✅ Cache OK')"
uv run python -c "from app.middleware.logging import setup_logging; print('✅ Middleware OK')"
uv run python -c "import streamlit; print('✅ Streamlit OK')"

echo ""
echo ">>> ✅ TASK 2+3 VERIFICADO. Listo para push."
