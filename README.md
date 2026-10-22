# HA-Anejo19 — Cálculo de hormigón armado (Código Estructural, Anejo 19)

Aplicación web para el dimensionado y la verificación de elementos de hormigón armado
según el **Anejo 19 del Código Estructural español (Real Decreto 470/2021)**. Los
cálculos se ejecutan en un motor Python independiente (FastAPI) y cada resultado incluye
las ecuaciones aplicadas con sus valores, referencias, hipótesis, verificaciones y
advertencias. Genera informes PDF y guarda proyectos.

> **Aviso.** Herramienta de apoyo académico y profesional. Los resultados deben ser
> revisados independientemente por un ingeniero estructural responsable antes de su uso
> en un proyecto real. Los parámetros se han cotejado con el texto oficial del Anejo 19 (BOE);
> lo que sigue pendiente se detalla en [docs/normativa.md](docs/normativa.md).

## Funcionalidades (v0.3.0)

- **Vigas — flexión simple ELU**: dimensionado de secciones rectangulares (con armadura
  de compresión si procede), propuesta de barras con alternativas, comprobación de
  secciones rectangulares y en T con armaduras en varias capas (método general
  parábola-rectángulo), armaduras mínima/máxima (9.2.1.1, expresión (9.1)), sujeción de
  barras comprimidas (9.2.1.2(3)), separaciones (8.2), criterio de ductilidad.
- **Vigas — cortante ELU**: V_Rd,c (6.2.2), dimensionado y comprobación de cercos verticales o
  inclinados con ángulo de bielas variable (0,5 ≤ cot θ ≤ 2), compresión en bielas, cuantía
  mínima y separaciones (9.2.2), tracción adicional ΔF_td.
- Materiales (tabla A19.3.1, diagramas de cálculo), secciones con dibujo a escala.
- «Normativa y procedimiento» en cada cálculo; configuración normativa editable.
- Informes PDF; proyectos guardados en JSON versionado (importar/exportar).
- Pendiente: losas, pilares, ELS (se muestran como «No disponible»).

## Requisitos

- Python 3.10 o superior
- Node.js 18 o superior (con npm)

## Instalación

```bash
git clone <repositorio> && cd H2
npm run setup
```

`setup` crea `backend/.venv`, instala las dependencias de Python
(`backend/requirements-dev.txt`) y las del frontend.

## Uso

```bash
npm run dev
```

Abra <http://localhost:5173>. La API queda en <http://127.0.0.1:8000> (documentación en
`/docs`). `Ctrl+C` detiene ambos procesos.

Modo «producción» local (un único proceso): `npm run start` → <http://127.0.0.1:8000>.

## Pruebas

```bash
npm test            # pytest del motor, servicios y API
npm run typecheck   # comprobación de tipos del frontend
```

Ejemplos de línea de comandos: `backend/.venv/bin/python examples/run_example.py examples/viga_rect_dimensionado.json --pdf informe.pdf`

## Estructura

```
frontend/            interfaz React + TypeScript
backend/main.py      aplicación FastAPI
backend/api/         rutas y modelos Pydantic
backend/core/        motor de cálculo (parámetros, materiales, secciones, ELU, ELS)
backend/services/    informes PDF y proyectos
backend/tests/       pruebas (pytest)
docs/                normativa, decisiones, validación, arquitectura
examples/            ejemplos de entrada
scripts/             scripts de arranque multiplataforma
```

## Solución de problemas

| Síntoma | Solución |
|---|---|
| `No se encontró backend/.venv` | Ejecute `npm run setup`. |
| `python3: command not found` (Windows) | Instale Python desde python.org marcando «Add to PATH»; el script usa `python` en Windows. |
| La web muestra «No se pudo conectar con el servidor de cálculo» | El backend no está en marcha o falló: revise las líneas `[backend]` de la consola. |
| `Port 5173 is in use` / `address already in use :8000` | Cierre la otra instancia o use `HA_BACKEND_PORT=8001 npm run dev`. |
| Error de certificados al instalar | Configure el proxy/certificados corporativos de pip y npm. |

Variables de entorno: `HA_BACKEND_PORT`, `HA_DATA_DIR` (carpeta de proyectos),
`HA_CORS_ORIGINS`.

## Documentación

- [CLAUDE.md](CLAUDE.md): reglas del proyecto y estado de los módulos.
- [docs/normativa.md](docs/normativa.md): trazabilidad normativa y puntos pendientes.
- [docs/decisiones.md](docs/decisiones.md), [docs/validacion.md](docs/validacion.md),
  [docs/arquitectura.md](docs/arquitectura.md).
