# Cline: Proveedores Configurados

## ¿DeepSeek Flash o Pro?

| Modelo | Rank | Score | Costo | ¿Cuándo usar? |
|---|---|---|---|---|
| **DeepSeek V4-Pro** | 24 | 1463 | $0.43/$0.87 | **DEFAULT**. Coding, arquitectura, debugging. |
| **DeepSeek V4-Flash** | — | — | Más barato | Solo tareas simples (resumen, refactor menor). |
| **Kimi K2.6** | 28 | 1460 | $0.95/$4 | Backup cuando DeepSeek cae (401/503). |
| **GPT-5.5** | 7 | 1488 | $5/$30 | Cuando necesitas el #1 del mundo (planning complejo). |

**Veredicto:** Flash NO aparece en el top 46 del leaderboard. Es suficiente para chat simple, pero para coding usa **Pro** (tu default ahora).

## Cambiar proveedor (1 comando)

```bash
# DeepSeek Pro (default, recomendado)
bash scripts/switch-cline.sh pro

# DeepSeek Flash (barato, rápido)
bash scripts/switch-cline.sh flash

# Kimi (backup cuando DeepSeek cae)
bash scripts/switch-cline.sh kimi

# ChatGPT (el mejor, más caro)
bash scripts/switch-cline.sh chatgpt
```

Después de cambiar: `Ctrl+Shift+P` → `Reload Window`

## Plan Mode vs Act Mode (diferentes modelos)

1. Abre Cline → Click en ⚙️ arriba a la derecha
2. Activa ✅ **"Use different models for Plan and Act modes"**
3. **Plan Mode** (diseño, arquitectura):
   - Cambia a `kimi` o `chatgpt` (mejor razonamiento)
4. **Act Mode** (ejecución, código):
   - Mantén `pro` o `flash` (más barato)
5. Click "Done"

## Si Kimi sigue dando 401

El error 401 de Moonshot suele ser:
1. **URL incorrecta**: Asegúrate de usar `https://api.moonshot.ai/v1` (no `.cn`)
2. **Key inválida**: Verifica en https://platform.moonshot.ai/
3. **Modelo incorrecto**: Usa `kimi-k2.6` (no `kimi-k2.5`)

Para diagnosticar:
```bash
curl https://api.moonshot.ai/v1/models \
  -H "Authorization: Bearer $KIMI_API_KEY"
```
