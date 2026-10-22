# Arquitectura

```
frontend/ (React + TS + Vite + Tailwind)  ──HTTP /api──▶  backend/main.py (FastAPI)
                                                           ├─ api/        rutas y validación (Pydantic)
                                                           ├─ core/       motor de cálculo (sin dependencias web)
                                                           │   ├─ parameters.py  parámetros normativos
                                                           │   ├─ units.py       unidades
                                                           │   ├─ materials.py   hormigón y acero
                                                           │   ├─ section.py     geometría y armaduras
                                                           │   ├─ trace.py       trazabilidad
                                                           │   ├─ status.py      estado de módulos
                                                           │   ├─ elu/analysis.py  método general (6.1)
                                                           │   ├─ elu/flexion.py   dimensionado/comprobación
                                                           │   └─ els/           (pendiente)
                                                           └─ services/   informes PDF y proyectos
```

- El **motor** (`core`) no importa nada de FastAPI ni de servicios: puede usarse desde
  scripts (`examples/run_example.py`) o tests.
- La **API** solo valida, delega y serializa. Los errores de dominio (`SectionError`,
  `MaterialError`, `ParameterError`, …) se devuelven como HTTP 422 con mensaje en español.
- El **frontend** nunca calcula resultados estructurales: incluso la posición de las
  barras del dibujo se obtiene del backend (`/api/secciones/propiedades`).
- Los **servicios** generan PDF a partir del resultado y gestionan proyectos.

## Endpoints principales

| Método | Ruta | Descripción |
|---|---|---|
| GET | /api/health, /api/info | estado, norma y módulos |
| GET/POST | /api/norma/parametros | parámetros por defecto / validar sobrescrituras |
| GET | /api/materiales/catalogo | clases y aceros |
| POST | /api/materiales | propiedades y diagramas |
| POST | /api/secciones/propiedades | geometría y barras |
| POST | /api/vigas/flexion | dimensionado (`mode=design`) o comprobación (`mode=check`) |
| POST | /api/informes/vigas/flexion | informe PDF |
| GET/POST/PUT/DELETE | /api/proyectos[/{id}], /api/proyectos/importar | proyectos |

Documentación interactiva: http://127.0.0.1:8000/docs
