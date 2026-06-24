#!/bin/bash
# Cambia el modelo de Cline copiando la config correcta
# Uso: bash scripts/switch-cline.sh [pro|flash|kimi|chatgpt]

set -e
PROVIDER="${1:-pro}"
cd "$(dirname "$0")/.."

CONFIG_FILE=".vscode/cline-providers/${PROVIDER}.json"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Config no encontrada: $CONFIG_FILE"
    echo "Opciones disponibles:"
    ls -1 .vscode/cline-providers/ | sed 's/.json//'
    exit 1
fi

# Copiar la config del proveedor al settings.json principal
cp "$CONFIG_FILE" .vscode/settings.json

echo "✅ Cline cambiado a: $PROVIDER"
echo "   Recarga VS Code: Ctrl+Shift+P → 'Reload Window'"
echo ""

# Mostrar info del proveedor
case "$PROVIDER" in
    pro)
        echo "   Modelo: DeepSeek V4-Pro (rank 24, score 1463)"
        echo "   Costo: $0.43/$0.87 por M tokens"
        echo "   Uso: Coding, razonamiento complejo"
        ;;
    flash)
        echo "   Modelo: DeepSeek V4-Flash (rápido, económico)"
        echo "   Costo: Más barato que Pro"
        echo "   Uso: Tareas simples, respuestas rápidas"
        ;;
    kimi)
        echo "   Modelo: Kimi K2.6 (rank 28, score 1460)"
        echo "   Costo: $0.95/$4 por M tokens"
        echo "   Uso: Backup cuando DeepSeek está caído"
        ;;
    chatgpt)
        echo "   Modelo: GPT-5.5 (rank 7, score 1488)"
        echo "   Costo: $5/$30 por M tokens (más caro)"
        echo "   Uso: Cuando necesitas lo mejor del mundo"
        ;;
esac
