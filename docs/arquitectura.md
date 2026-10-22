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
                                                           │   ├─ elu/cortante.py  cortante (6.2, 9.2.2)
                                                           │   ├─ elu/nm.py        interacción N–M (6.1)
                                                           │   ├─ elu/pilares.py   pilares (5.2, 5.8, 9.5)
                                                           │   ├─ elu/losas.py     losas macizas unidireccionales (9.3)
                                                           │   ├─ els/elastic.py   secciones homogeneizada y fisurada
                                                           │   ├─ els/fluencia.py  fluencia y retracción (3.1.4, Ap. B)
                                                           │   ├─ els/fisuracion.py, els/flechas.py
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
| POST | /api/vigas/cortante | cortante: dimensionado (`mode=design`) o comprobación (`mode=check`) |
| POST | /api/informes/vigas/cortante | informe PDF de cortante |
| POST | /api/pilares | pilar: segundo orden y flexocompresión |
| POST | /api/informes/pilares | informe PDF de pilar |
| POST | /api/losas, /api/informes/losas | losas macizas unidireccionales e informe |
| GET | /api/els/catalogo | clases de exposición (w_max) y sistemas (K) |
| POST | /api/els/fisuracion, /api/els/deformaciones | ELS |
| POST | /api/informes/els/fisuracion, /api/informes/els/deformaciones | informes PDF de ELS |
| GET/POST/PUT/DELETE | /api/proyectos[/{id}], /api/proyectos/importar | proyectos |

Documentación interactiva: http://127.0.0.1:8000/docs
