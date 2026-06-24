# Cline: Configuración Rápida y Cambio de Modelos

## Estado Actual (out-of-the-box)
- **Act Mode (default):** DeepSeek V4-Flash (`deepseek-v4-flash`)
- **Costo:** ~$0.43/M tokens (el más barato del ranking)
- **API Key:** Leída automáticamente del entorno del Codespace

## Cambiar modelo rápido (1 comando)
```bash
# DeepSeek V4-Flash (default, más barato)
bash estimador-cag/scripts/switch-cline-model.sh deepseek

# DeepSeek V4-Pro (para razonamiento complejo)
bash estimador-cag/scripts/switch-cline-model.sh deepseek-pro

# Kimi K2.6 (backup cuando DeepSeek está caído)
bash estimador-cag/scripts/switch-cline-model.sh kimi
```
Después de cambiar: `Ctrl+Shift+P` → `Reload Window`

## Plan Mode vs Act Mode (diferentes modelos)
Cline permite usar **modelos distintos** para Plan y Act:

1. Abre Cline (icono 🤖)
2. Click en el engranaje ⚙️ arriba a la derecha
3. Activa ✅ **"Use different models for Plan and Act modes"**
4. Configura:
   - **Plan Mode:** Kimi K2.6 o DeepSeek V4-Pro (mejor razonamiento)
   - **Act Mode:** DeepSeek V4-Flash (más barato, rápido)
5. Click "Done"

## URLs correctas de los proveedores
| Proveedor | Base URL | Modelo |
|---|---|---|
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-v4-flash` / `deepseek-v4-pro` |
| Kimi | `https://api.moonshot.ai/v1` | `kimi-k2.6` / `kimi-k2.5` |

## Troubleshooting
- **"API key invalid"**: El secret no está en el Codespace. Ve a github.com/settings/codespaces → Secrets.
- **"No module named 'fastapi'"**: Ejecuta `uv sync` en el terminal.
- **No aparece el icono de Cline**: `Ctrl+Shift+P` → `Reload Window`.
