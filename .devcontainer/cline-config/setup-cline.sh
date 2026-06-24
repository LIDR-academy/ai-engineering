#!/usr/bin/env bash
set -euo pipefail

echo "=== Cline setup ==="

mkdir -p ~/.cline/data

if [ -z "${DEEPSEEK_API_KEY:-}" ]; then
  echo "WARNING: DEEPSEEK_API_KEY is missing from Codespaces secrets."
  echo "Cline DeepSeek defaults will be written, but API calls may fail until the secret is configured."
fi

if [ -z "${KIMI_API_KEY:-}" ]; then
  echo "WARNING: KIMI_API_KEY is missing. Kimi fallback will not work until the secret is configured."
fi

cp /workspaces/ai-engineering/.devcontainer/cline-config/globalState.template.json \
  ~/.cline/data/globalState.json

cat > ~/.cline/data/secrets.json <<EOF
{
  "moonshotApiKey": "${KIMI_API_KEY:-}",
  "deepSeekApiKey": "${DEEPSEEK_API_KEY:-}"
}
EOF

chmod 600 ~/.cline/data/secrets.json

echo "Cline state written:"
python - <<'PY'
import json
from pathlib import Path

p = Path.home() / ".cline" / "data" / "globalState.json"
data = json.loads(p.read_text())

for key in [
    "planModeApiProvider",
    "planModeApiModelId",
    "planModeOpenAiModelId",
    "actModeApiProvider",
    "actModeApiModelId",
    "actModeOpenAiModelId",
    "planActSeparateModelsSetting",
]:
    print(f"{key}: {data.get(key)}")
PY

echo ""
echo "IMPORTANT:"
echo "Cline internal state is not guaranteed stable."
echo "After Codespaces opens, verify manually:"
echo "Plan: DeepSeek / deepseek-v4-pro"
echo "Act:  DeepSeek / deepseek-v4-flash"
echo ""
echo "✅ Cline defaults preloaded"
