# Documentación

Sistema de estimación de esfuerzo de software — tres capas sobre dos almacenes.

Si vienes de nuevo, empieza por **[Arquitectura](architecture.md)** y sigue por
**[Despliegue local](deployment-local.md)**.

---

## Técnica

Cómo está construido el sistema.

| Documento | Qué responde |
|---|---|
| [Arquitectura](architecture.md) | Las tres capas, la frontera público/privado, el contrato y los códigos de error |
| [`ai-service/ARCHITECTURE.md`](../ai-service/ARCHITECTURE.md) | Capas internas del servicio IA (foundation / domain / generation / api) |
| [`business-backend/ARCHITECTURE.md`](../business-backend/ARCHITECTURE.md) | Contextos internos del backend de negocio |
| [Decisiones](decisions.md) | Qué se decidió, por qué, y qué queda por confirmar |
| [`contract/`](contract/) | Las rutas que el backend de negocio consume, verificadas en CI |

## Estándares para el agente (Spec-Driven Development)

Los únicos documentos de `docs/` escritos **en inglés**, porque quien los lee es el
agente de código, no una persona. Instalados en la Sesión 17 (Lab SDD).

| Documento | Qué responde |
|---|---|
| [Base standards](base-standards.md) | Principios, cierre de decisiones, definition of done, palabras prohibidas |
| [Architecture guide](doc-architecture.md) | Dónde vive cada responsabilidad y qué contratos no se mueven por accidente |
| [Verification guide](doc-verification-guide.md) | Qué verificación prueba qué cambio, con los comandos reales |
| [AI service standards](ai-service-standards.md) | FastAPI: capas, schemas, errores tipados, guardrails, prompts |
| [Business backend standards](business-backend-standards.md) | Rails: frontera del cliente, degradación, persistencia, snapshot vs refetch |
| [`ai-specs/README.md`](../ai-specs/README.md) | El flujo de nueve pasos, las tres skills y cómo montarlo |

## Operativa

Cómo se arranca, se despliega y se arregla.

| Documento | Qué responde |
|---|---|
| [Despliegue local](deployment-local.md) | `docker compose up` y las 5 comprobaciones |
| [CI/CD](ci-cd.md) | El pipeline etapa por etapa, secretos, y por qué en CI no se llama al modelo |
| [Despliegue en EC2](deploy-ec2.md) | Puesta en cloud paso a paso: aprovisionar, TLS, desplegar, verificar |
| [Escalabilidad y alta concurrencia](scalability.md) | Los límites reales del sistema y qué se rompe primero |
| [Evaluación y monitorización](evaluation.md) | Golden set, arnés de evaluación y dashboard: si el sistema estima bien y a qué precio |
| [Observabilidad](observability.md) | Las cuatro señales de producción, el coste por tramo y las alertas |
| [Runbook: el servicio IA no responde](runbooks/ai-service-down.md) | Diagnóstico y reinicio seguro cuando algo está caído |

## Usuario

| Recurso | Qué es |
|---|---|
| <http://localhost:3000> | La interfaz. Punto de entrada de cualquier persona usuaria |
| `/docs` del servicio IA | Swagger generado desde los modelos Pydantic (solo alcanzable desde la red interna) |
| [`ai-service/exercises/`](../ai-service/exercises/) | Material de los ejercicios por sesión |
| [`templates/`](../templates/) | Las cuatro plantillas de artefacto del flujo SDD |

---

## Atajos

```bash
# Arrancar todo
cp .env.example .env        # rellena OPENAI_API_KEY y AI_SERVICE_TOKEN
docker compose up --build

# Comprobar que el sistema desplegado está vivo
python scripts/smoke_test.py --base-url http://localhost:3000

# Tests (ninguno llama al LLM)
cd ai-service && uv run pytest -q
cd business-backend && bin/rails test

# Verificar el contrato entre capas
cd ai-service && uv run python scripts/check_contract.py
```

> **Los secretos nunca están aquí.** El repositorio versiona `.env.example` con
> los nombres; los valores viven en tu `.env` local (ignorado por git) o en el
> gestor de secretos de la plataforma.
