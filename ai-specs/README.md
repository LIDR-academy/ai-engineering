# Spec-Driven Development en este repositorio

Contexto técnico, skills y plantillas para trabajar con un agente de código sin acabar
con tres mil líneas que nadie entiende. Material del **Lab auxiliar de SDD** (Sesión 17).

Todo lo que lee el agente está en **inglés**, por la norma del programa. Este README
está en español.

## Dónde vive cada pieza

Ya está instalado en el repositorio. No hay que copiar nada:

```
CLAUDE.md                             # instrucciones que Claude Code lee siempre
docs/
  base-standards.md                   # fuente única: principios, cierre de decisiones, DoD
  doc-architecture.md                 # capas, ownership, el contrato entre servicios
  doc-verification-guide.md           # qué verificación prueba qué cambio
  ai-service-standards.md             # FastAPI: capas, schemas, errores tipados, guardrails
  business-backend-standards.md       # Rails: frontera del cliente, degradación, persistencia
ai-specs/skills/
  close-requirement/SKILL.md          # idea vaga -> requisito con decisiones cerradas
  spec-review/SKILL.md                # auditoría de la spec ANTES de implementar
  adversarial-review/SKILL.md         # red team sobre el cambio ya implementado
templates/
  01-requirement.md
  02-technical-contract.md
  03-delta-spec.md
  04-tasks.md
openspec/config.yml                   # contexto del proyecto para el generador
```

## Puesta en marcha

Lo único que hace falta en una máquina nueva:

```bash
# 1. OpenSpec (requiere Node >= 20.19)
npm install -g @fission-ai/openspec@latest
openspec init
openspec config profile          # perfil extendido: /opsx:propose, /opsx:apply, ...

# 2. Exponer las skills a Claude Code
mkdir -p .claude
ln -s ../ai-specs/skills .claude/skills
```

`.claude/` está en `.gitignore` a propósito: la fuente única versionada es
`ai-specs/skills/`, y cada quien la expone a su herramienta con un symlink (Claude
Code, Cursor, Codex). Una sola copia, varios clientes.

Verifica que ha funcionado abriendo Claude Code en la raíz y preguntando:

```
Sin escribir código: ¿qué reglas de este proyecto se aplican antes de que
generemos una spec, y de dónde las has sacado? Cita los ficheros.
```

Si cita `CLAUDE.md`, `docs/base-standards.md` y la lista de palabras prohibidas, está
leyendo el contexto. Si no cita ficheros, el contexto no está cargado.

## Orden de uso

| Paso | Qué haces | Artefacto |
| ---- | --------- | --------- |
| 1 | `close-requirement` sobre una idea vaga | `templates/01-requirement.md` |
| 2 | `/opsx:explore` para anclar en el código | notas, ningún fichero |
| 3 | `/opsx:propose` genera la propuesta | delta specs + `design.md` + `tasks.md` |
| 4 | `spec-review` audita lo generado | informe de hallazgos |
| 5 | Apruebas el contrato técnico | `templates/02-technical-contract.md` firmado |
| 6 | `/opsx:apply` implementa tarea a tarea | código + checkboxes |
| 7 | Verificación con evidencia | `reports/YYYY-MM-DD-verification.md` |
| 8 | `adversarial-review` en **sesión nueva** | informe de red team |
| 9 | `/opsx:archive` y PR | historial |

El paso 5 es el único punto donde un humano bloquea el flujo. Es deliberado.

Los nombres exactos de los comandos dependen del perfil y de la versión de OpenSpec, y
cada herramienta los escribe distinto (Cursor y Copilot usan `/opsx-propose`, Codex
`$openspec-propose`). Teclea `/` y comprueba la lista antes de fiarte de este cuadro.

## Cuándo NO usar esto

- Prototipos y spikes que se van a tirar.
- Cambios de una línea.
- Exploración: cuando aún no sabes qué quieres construir.

SDD tiene un coste fijo de entre veinte y cuarenta minutos por cambio. Se paga solo
cuando el cambio toca un contrato, cuando lo va a mantener alguien más, o cuando
equivocarse es caro. En el resto, estorba.

## Llevártelo a otro proyecto

Los `docs/` están escritos contra **este** repositorio, con sus rutas y sus comandos
reales. Si tu caso de uso es otro, cambia el dominio pero conserva la estructura: son
los cinco documentos que el agente necesita para no inventarse tu arquitectura.

El error más común al empezar es montar el tooling y no adaptar `docs/`. Con contexto
genérico el agente genera specs genéricas, y la conclusión que se saca es "esto no
funciona". Funciona el proceso, no los ficheros de ejemplo.

Prompt para adaptarlos:

```
Actualiza los documentos de docs/ manteniendo exactamente la misma estructura y los
mismos nombres de fichero. Sustituye el dominio y los ejemplos por los reales de este
repositorio: inspecciona el código antes de escribir nada, cita ficheros concretos y
no inventes endpoints que no existan. Todo en inglés.
```

## Créditos

Basado en el trabajo de la comunidad LIDR: [`LIDR-academy/manual-SDD`](https://github.com/LIDR-academy/manual-SDD)
y [`LIDR-academy/ai-specs`](https://github.com/LIDR-academy/ai-specs) (Specboot), de
Javier Vargas. OpenSpec: [`Fission-AI/OpenSpec`](https://github.com/Fission-AI/OpenSpec).
