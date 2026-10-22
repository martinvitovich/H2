# CLAUDE.md — HA-Anejo19

Instrucciones permanentes del proyecto. Mantener actualizado en cada cambio relevante.

## Objetivo
Aplicación web para el cálculo, dimensionado y verificación de estructuras de hormigón
armado según el **Anejo 19 del Código Estructural (RD 470/2021)**. Uso académico y de
apoyo profesional; los resultados deben revisarse por un ingeniero responsable.

## Arquitectura
- `frontend/`: React 18 + TypeScript + Vite 6 + Tailwind 4 + Recharts. Nunca calcula
  resultados estructurales.
- `backend/main.py`: FastAPI. `backend/api/`: rutas y modelos Pydantic.
- `backend/core/`: motor de cálculo puro (sin dependencias web). `parameters.py`,
  `units.py`, `materials.py`, `section.py`, `trace.py`, `status.py`, `elu/`, `els/`.
- `backend/services/`: `report_pdf.py` (ReportLab), `projects.py` (JSON versionado).
- `backend/tests/`: Pytest. `docs/`: documentación técnica. `examples/`: ejemplos.
Detalle en `docs/arquitectura.md`.

## Referencia normativa
Código Estructural, Anejo 19 (BOE-A-2021-13681). El PDF oficial **no fue accesible**
desde el entorno de desarrollo (red bloqueada): ver `docs/normativa.md` para la matriz
de trazabilidad y los puntos pendientes de cotejo. No mezclar con otras ediciones del
EC2 ni con normas de otros países. Si se obtiene acceso al texto oficial, la primera
tarea es cotejar `docs/normativa.md` y actualizar los estados en `core/parameters.py`.

## Convenciones de unidades
Interno: mm, mm², N, MPa, N·mm, deformaciones adimensionales. API/UI: kN·m, kN, ‰.
Conversiones solo vía `core/units.py`. Momento positivo = tracción en la cara inferior.
Coordenada y desde la fibra superior hacia abajo.

## Reglas para implementar fórmulas
1. Identificar apartado y ecuación del Anejo 19 antes de implementar; verificar las
   remisiones a otros apartados.
2. Ningún coeficiente normativo fuera de `core/parameters.py` (con referencia, rango y
   estado de verificación).
3. Cada función de cálculo registra en `CalcTrace`: entradas, unidades, hipótesis,
   parámetros usados, ecuaciones con sustitución, resultados intermedios,
   verificaciones, advertencias y limitaciones.
4. Declarar el dominio de validez; rechazar (error 422) o advertir fuera de él.
5. No inventar fórmulas, coeficientes ni valores de referencia. Lo no verificable se
   documenta como pendiente.
6. No declarar que un elemento cumple si faltan datos: usar `ok=None` (no evaluable).

## Procedimiento de validación
Ver `docs/validacion.md`. Tests de consistencia matemática con cálculos manuales
independientes y tolerancias justificadas; ejemplos bibliográficos solo si son
verificables. Un módulo pasa a `verificado` en `core/status.py` solo tras el cotejo
normativo independiente.

## Comandos
```bash
npm run setup      # crea backend/.venv, instala Python y npm
npm run dev        # backend :8000 + frontend :5173 (http://localhost:5173)
npm test           # pytest
npm run typecheck  # TypeScript
npm run build      # compila frontend
npm run start      # compila y sirve todo desde FastAPI (:8000)
```

## Estado real de los módulos (v0.1.0)
| Módulo | Estado |
|---|---|
| Parámetros normativos | Implementado; γ_c/γ_s confirmados por fuente secundaria; resto pendiente de cotejo |
| Materiales (tabla 3.1, 3.1.6, 3.1.7, 3.2.7) | Implementado · validación pendiente |
| Secciones rectangular/T, varias capas, 8.2 | Implementado · validación pendiente |
| Vigas — flexión ELU (dimensionado rectangular, comprobación rect./T) | Implementado · validación pendiente |
| Proyectos (JSON v1) e informes PDF | Implementado |
| Cortante, losas, pilares, ELS fisuración y deformaciones | No disponible |

## Pendiente
- Cotejo del texto oficial del Anejo 19 (prioritario).
- Fase 3: cortante (6.2) y estribos. Fase 4: pilares, interacción N–M, 5.8.
- Fase 5: fisuración (7.3) y flechas (7.4). Fase 6: consolidación.
- Dimensionado de secciones en T; armadura de montaje/piel; flexión compuesta.
- Recubrimientos por durabilidad (4.4.1) y anchura eficaz (5.3.2.1).

## Decisiones
Ver `docs/decisiones.md` (D1–D10).
