"""
LAYER: context (static CAG data)
RESPONSIBILITY: Provide few-shot examples baked into the system prompt
WHY IT EXISTS: Demonstrates the CAG pattern before dynamic RAG is introduced.
DEPENDS ON: Nothing (pure data)
"""

ESTIMATION_EXAMPLES = [
    {
        "meeting_summary": "El cliente necesita una plataforma web de gestion de inventario con roles de usuario, dashboard de metricas y exportacion a Excel. 10 usuarios concurrentes.", \
        "estimation": """## Estimacion: Plataforma de Gestion de Inventario

### Desglose de tareas:
1. Diseno UI/UX: 40 horas
2. Backend API (CRUD inventario): 60 horas
3. Autenticacion y roles: 20 horas
4. Dashboard con metricas: 30 horas
5. Testing y QA: 25 horas

**Total estimado: 175 horas**
**Equipo recomendado: 2 desarrolladores full-stack + 1 disenador UX (part-time)**
**Duracion estimada: 6-8 semanas**""",
    },
    {
        "meeting_summary": "Landing page con formulario de contacto, integracion HubSpot CRM, blog con editor WYSIWYG. Diseno en Figma. 4 semanas de plazo.",\
        "estimation": """## Estimacion: Landing Page + Blog + CRM

### Desglose de tareas:
1. Maquetacion responsive (Figma -> HTML/CSS): 25 horas
2. Formulario de contacto + validaciones: 10 horas
3. Integracion HubSpot API: 15 horas
4. Blog con editor WYSIWYG: 30 horas
5. SEO basico + performance: 10 horas
6. Testing cross-browser: 10 horas

**Total estimado: 100 horas**
**Equipo recomendado: 1 desarrollador full-stack + 1 disenador (part-time)**
**Duracion estimada: 3-4 semanas**""",
    },
]
