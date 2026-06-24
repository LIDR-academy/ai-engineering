# Transcripcion de Ejemplo para Testing

Este archivo contiene la transcripcion de reunion que usa el ejercicio de LIDR
como parametro de prueba para el endpoint `/api/v1/estimate`.

## Contenido

> En la reunion con el equipo de marketing, el cliente explico que necesita una
> landing page con formulario de contacto, integracion con su CRM actual (HubSpot),
> y una seccion de blog con editor WYSIWYG. El plazo ideal seria tenerlo listo
> en 4 semanas. El diseno ya existe en Figma.

## Uso

```bash
# Via curl
curl -X POST http://localhost:8000/api/v1/estimate \\
  -H "Content-Type: application/json" \\
  -d '{"transcription": "En la reunion con el equipo de marketing...", "tier": "flash"}'

# Via script incluido
bash scripts/test_api.sh
```
