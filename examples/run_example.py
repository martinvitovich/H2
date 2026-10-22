"""Ejecuta un ejemplo JSON con el motor de cálculo y muestra el resumen.

Uso (desde la raíz del repositorio):
    backend/.venv/bin/python examples/run_example.py examples/viga_rect_dimensionado.json
    (Windows: backend\\.venv\\Scripts\\python.exe examples\\run_example.py ...)

Opcional: --pdf salida.pdf genera el informe de cálculo.

Los resultados de estos ejemplos NO son valores de referencia validados: sirven para
reproducir el procedimiento y revisarlo manualmente.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from api.schemas import ColumnRequest, FlexureRequest, ShearRequest  # noqa: E402
from core.elu.pilares import column_check  # noqa: E402
from core.elu.cortante import shear_beam  # noqa: E402
from core.elu.flexion import check_flexure, design_flexure  # noqa: E402
from services.report_pdf import build_column_report, build_flexure_report, build_shear_report  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--pdf")
    a = ap.parse_args()
    data = json.loads(Path(a.file).read_text(encoding="utf-8"))
    shear = "V_Ed_kN" in data
    column = "N_Ed_kN" in data
    if column:
        req = ColumnRequest.model_validate(data)
        res = column_check(req.build())
    elif shear:
        req = ShearRequest.model_validate(data)
        res = shear_beam(req.build())
    else:
        req = FlexureRequest.model_validate(data)
        inp = req.build()
        res = design_flexure(inp) if req.mode == "design" else check_flexure(inp)
    tr = res["trace"]
    print(f"{tr['calculation']}\nNorma: {tr['norm']['name']}\n")
    for s in tr["steps"]:
        val = "" if s["result"] is None else f" = {s['result']:.4g} {s['unit']}"
        print(f"- {s['title']}: {s['equation']}{val}   [{s['reference']}]")
    print("\nVerificaciones:")
    for c in tr["checks"]:
        print(f"  [{'OK' if c['ok'] else 'NO'}] {c['name']}: {c['demand']} | {c['capacity']}")
    if not shear and not column and res.get("proposal"):
        p = res["proposal"]
        print(f"\nArmadura propuesta: {p['text_tension']} / {p['text_compression'] or '-'}")
    if shear and res["result"].get("proposal"):
        p = res["result"]["proposal"]
        print(f"\nCercos propuestos: φ{p['diameter']:g} de {p['legs']} ramas c/{p['spacing']:g} mm")
    for w in tr["warnings"]:
        print(f"AVISO: {w}")
    if a.pdf:
        build = build_column_report if column else build_shear_report if shear else build_flexure_report
        Path(a.pdf).write_bytes(build(res, req.model_dump(), "Ejemplo", ""))
        print(f"\nInforme: {a.pdf}")


if __name__ == "__main__":
    main()
