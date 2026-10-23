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
- `backend/estructura/`: proyecto integral (SQLite, modelo, relaciones, transmisión de cargas,
  estados de resultados, cálculo selectivo, Excel/PDF). No contiene fórmulas del Anejo 19: delega en `core`.
- `backend/services/`: `report_pdf.py` (ReportLab), `projects.py` (ProjectStore sobre SQLite; importa
  una vez los JSON antiguos sin borrarlos).
- `backend/tests/`: Pytest. `docs/`: documentación técnica. `examples/`: ejemplos.
Detalle en `docs/arquitectura.md`.

## Referencia normativa
Código Estructural, Anejo 19 (BOE-A-2021-13681, BOE n.º 190, 10/08/2021). En la v0.2.0 se
cotejó el texto oficial del BOE para todo lo usado en flexión; las referencias del código
citan la página del BOE (pág. del PDF = pág. BOE − 98284). La matriz de trazabilidad, las
erratas detectadas y lo que sigue pendiente están en `docs/normativa.md`. No mezclar con
otras ediciones del EC2 ni con normas de otros países: el Anejo 19 difiere de la EN 1992-1-1
en puntos concretos (p. ej., A_s,min (9.1), rango f_yk 400–500, α_cc). Antes de implementar un
apartado nuevo, leerlo en el texto oficial y verificar sus remisiones.

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
docker build -t ha-anejo19 . && docker run -p 8000:8000 ha-anejo19   # imagen de despliegue (Render: render.yaml)
```

## Estado real de los módulos (v0.7.0)
| Módulo | Estado |
|---|---|
| Parámetros normativos | Cotejados con el texto oficial (BOE); pendiente solo la ductilidad de aceros (Arts. 34-35 CE) |
| Materiales (tabla A19.3.1, 3.1.3, 3.1.6, 3.1.7, 3.1.8, 3.2.7) | Implementado y cotejado · falta contraste bibliográfico |
| Secciones rectangular/T, varias capas, 8.2(2)-(3) | Implementado y cotejado · falta contraste bibliográfico |
| Vigas — flexión ELU (dimensionado rectangular, comprobación rect./T; 9.2.1.1, 9.2.1.2(3)) | Implementado y cotejado · falta contraste bibliográfico |
| Vigas — cortante ELU (V_Rd,c, cercos 45°–90°, bielas, 9.2.2) | Implementado y cotejado · falta contraste bibliográfico |
| Proyecto integral (niveles, losas, vigas, pilares, zapatas, relaciones, cargas con procedencia, resultados desactualizados, cálculo selectivo, historial) | Implementado · ver `docs/proyecto_integral.md` |
| Proyectos (SQLite, formato JSON 2, migración de JSON 1), informes PDF, memoria y planilla Excel | Implementado |
| Pilares — flexocompresión recta (N–M 6.1, 5.2, 5.8.3, curvatura nominal 5.8.8, 9.5) | Implementado y cotejado · falta contraste bibliográfico |
| ELS — fisuración y tensiones (7.2, 7.3) | Implementado y cotejado · falta contraste bibliográfico |
| ELS — deformaciones (7.4, 3.1.4, Apéndice B) | Implementado y cotejado · falta contraste bibliográfico |
| Losas macizas unidireccionales (9.3, flexión por metro, reparto, cortante sin armadura) | Implementado y cotejado · falta contraste bibliográfico |
| Losas bidireccionales y planas, punzonamiento (6.4, 9.4) | No disponible |

## Reglas del proyecto integral
- Las relaciones usan ids internos; los códigos son únicos por proyecto pero editables.
- No recalcular automáticamente ni mostrar resultados desactualizados como vigentes (estado por huella SHA-256).
- Transmisión solo por reglas documentadas (áreas tributarias, equilibrio isostático) o datos manuales;
  si faltan datos, pedirlos (`faltan_datos`), nunca suponerlos. No cambiar el motor desde `estructura/`.
- La planilla `Cálculos.xlsx` solo se usó como referencia de organización, no de fórmulas ni validación.

## Pendiente
- Proyecto integral: continuidad de vigas/losas, alternancia de sobrecargas, momentos en pilares,
  dimensionado estructural de zapatas, áreas tributarias automáticas.
- Contraste con ejemplos resueltos de bibliografía verificable (para pasar a «verificado»).
- Consultar los Arts. 34-35 del Código Estructural (ductilidad de aceros) y 43.4.1 (recubrimientos).
- Cortante: reducción β por cargas próximas a apoyos, rasante ala-alma (6.2.4), torsión (6.3),
  barras levantadas, comprobación de la armadura longitudinal con ΔF_td.
- Pilares: flexión esviada (5.8.9), rigidez nominal (5.8.7), método general (5.8.6), secciones
  circulares, cortante en pilares, coeficiente de fluencia (3.1.4).
- ELS: esfuerzo axil, pretensado, armado en dos direcciones, alas traccionadas (7.3), armadura de piel;
  flechas en vigas continuas con ley de momentos real (integración de curvaturas).
- Losas bidireccionales y planas, punzonamiento (6.4), armadura de cortante en losas (9.3.2).
- Contraste de todos los módulos con ejemplos resueltos de bibliografía verificable.
- Dimensionado de secciones en T; armadura de montaje/piel; flexión compuesta.
- Recubrimientos por durabilidad (4.4.1) y anchura eficaz (5.3.2.1).

## Decisiones
Ver `docs/decisiones.md` (D1–D30).
