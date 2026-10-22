"""Generación del informe PDF de cálculo (ReportLab).

El informe se construye exclusivamente a partir del resultado y del registro de
trazabilidad devueltos por el motor de cálculo: no recalcula nada.
"""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path
from typing import Any

from reportlab.graphics.shapes import Circle, Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from xml.sax.saxutils import escape

from version import SOFTWARE_NAME, __version__

_FONT_DIR = Path(__file__).resolve().parent / "fonts"
_FONTS_OK = False


def _register_fonts() -> None:
    global _FONTS_OK
    if _FONTS_OK:
        return
    pdfmetrics.registerFont(TTFont("DejaVu", str(_FONT_DIR / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(_FONT_DIR / "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVuMono", str(_FONT_DIR / "DejaVuSansMono.ttf")))
    from reportlab.pdfbase.pdfmetrics import registerFontFamily
    registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-Bold", italic="DejaVu", boldItalic="DejaVu-Bold")
    _FONTS_OK = True


def _styles():
    ss = getSampleStyleSheet()
    base = ParagraphStyle("base", parent=ss["Normal"], fontName="DejaVu", fontSize=8.5, leading=11)
    return {
        "base": base,
        "small": ParagraphStyle("small", parent=base, fontSize=7.5, leading=9.5),
        "mono": ParagraphStyle("mono", parent=base, fontName="DejaVuMono", fontSize=7.5, leading=9.5),
        "h1": ParagraphStyle("h1", parent=base, fontName="DejaVu-Bold", fontSize=15, leading=19, spaceAfter=6),
        "h2": ParagraphStyle("h2", parent=base, fontName="DejaVu-Bold", fontSize=11, leading=14,
                             spaceBefore=10, spaceAfter=4, textColor=colors.HexColor("#1f3a5f")),
        "warn": ParagraphStyle("warn", parent=base, textColor=colors.HexColor("#8a4b00")),
    }


def _p(text: Any, st) -> Paragraph:
    return Paragraph(escape(str(text)), st)


def _num(v: Any, nd: int = 3) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        if v != 0 and (abs(v) >= 1e7 or abs(v) < 1e-3):
            return f"{v:.{max(nd, 1)}e}".replace(".", ",")
        s = f"{v:.{nd}f}"
        if "." in s:
            s = s.rstrip("0").rstrip(".")
        return s.replace(".", ",")
    return str(v)


def _table(rows, col_widths, st, header=True) -> Table:
    data = [[c if isinstance(c, Paragraph) else _p(c, st) for c in r] for r in rows]
    t = Table(data, colWidths=col_widths, repeatRows=1 if header else 0)
    style = [
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#b8c2cc")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef5")))
    t.setStyle(TableStyle(style))
    return t


def _section_drawing(geometry: dict, width_pt: float = 70 * mm) -> Drawing:
    shape = geometry["shape"]
    h = shape["h"]
    B = shape.get("b") or shape.get("bf")
    scale = min(width_pt / B, 85 * mm / h)
    W, H = B * scale + 20, h * scale + 20
    d = Drawing(W, H)
    ox, oy = 10, 10

    def Y(y):  # y desde la fibra superior → coordenadas de dibujo
        return oy + (h - y) * scale

    fill = colors.HexColor("#d9dee4")
    if shape["kind"] == "rectangular":
        d.add(Rect(ox, oy, B * scale, h * scale, fillColor=fill, strokeColor=colors.black, strokeWidth=0.8))
    else:
        bf, hf, bw = shape["bf"], shape["hf"], shape["bw"]
        d.add(Rect(ox, Y(hf), bf * scale, hf * scale, fillColor=fill, strokeColor=colors.black, strokeWidth=0.8))
        x0 = (bf - bw) / 2
        d.add(Rect(ox + x0 * scale, oy, bw * scale, (h - hf) * scale, fillColor=fill,
                   strokeColor=colors.black, strokeWidth=0.8))
    for b in geometry["bars"]:
        d.add(Circle(ox + b["x"] * scale, Y(b["y"]), max(b["diameter"] * scale / 2, 1.2),
                     fillColor=colors.HexColor("#b03a2e"), strokeColor=colors.black, strokeWidth=0.3))
    d.add(String(ox, H - 8, f"Escala aprox. 1:{round(1 / (scale / (72 / 25.4)))}", fontName="DejaVu", fontSize=6))
    return d


def build_flexure_report(result: dict, request: dict, project_name: str = "", author: str = "") -> bytes:
    geom = None
    lines: list[str] = []
    if result.get("mode") == "design" and result.get("proposal"):
        pr = result["proposal"]
        geom = pr["geometry"]
        lines.append(f"Armadura propuesta — tracción: {pr['text_tension']} (A_s = {_num(pr['As_tension'], 0)} mm²); "
                     f"compresión: {pr['text_compression'] or 'no requerida por el cálculo'}"
                     f"{'' if not pr['text_compression'] else ' (A_s2 = ' + _num(pr['As_compression'], 0) + ' mm²)'}; "
                     f"d = {_num(pr['d'], 1)} mm.")
    elif result.get("geometry"):
        geom = result["geometry"]
    return _build_report(result, request, project_name, author, geom, lines)


def build_shear_report(result: dict, request: dict, project_name: str = "", author: str = "") -> bytes:
    R = result["result"]
    lines = [f"V_Rd,c = {_num(R['VRdc']['VRdc'] / 1e3, 2)} kN; cot θ = {_num(R.get('cot_theta'), 3)} "
             f"(θ = {_num(R.get('theta_deg'), 1)}°); V_Rd,max = {_num((R.get('VRd_max') or 0) / 1e3, 2)} kN."]
    if result.get("mode") == "design":
        pr = R.get("proposal")
        if pr and pr.get("spacing"):
            lines.append(f"Cercos propuestos: φ{_num(float(pr['diameter']))} de {pr['legs']} ramas cada "
                         f"{_num(float(pr['spacing']), 0)} mm (A_sw/s necesaria = {_num(R['Asw_s_design'] * 1000, 1)} mm²/m).")
        else:
            lines.append("Sin disposición de cercos válida (véanse advertencias).")
    else:
        lines.append(f"Cercos existentes: φ{_num(float(request['stirrup_diameter']))} de {request['stirrup_legs']} "
                     f"ramas cada {_num(float(request['stirrup_spacing']), 0)} mm.")
    if R.get("VRd_s") is not None:
        lines.append(f"V_Rd,s = {_num(R['VRd_s'] / 1e3, 2)} kN.")
    if R.get("Delta_Ftd") is not None:
        lines.append(f"Tracción adicional en la armadura longitudinal ΔF_td = {_num(R['Delta_Ftd'] / 1e3, 2)} kN (6.18).")
    return _build_report(result, request, project_name, author, R.get("geometry"), lines)


def _build_report(result: dict, request: dict, project_name: str, author: str, geom: dict | None,
                  result_lines: list[str]) -> bytes:
    _register_fonts()
    S = _styles()
    tr = result["trace"]
    buf = io.BytesIO()
    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("DejaVu", 7)
        canvas.setFillColor(colors.HexColor("#555555"))
        canvas.drawString(15 * mm, 10 * mm, f"{SOFTWARE_NAME} v{__version__} · {tr['norm']['id']} · {now}")
        canvas.drawRightString(195 * mm, 10 * mm, f"Página {doc.page}")
        canvas.drawString(15 * mm, 287 * mm, f"{project_name} — {request.get('element_name', '')}")
        canvas.restoreState()

    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm,
                            title=f"Informe de cálculo — {request.get('element_name', '')}",
                            author=author or SOFTWARE_NAME)
    E: list = []
    E.append(_p("Informe de cálculo — " + tr["calculation"], S["h1"]))
    E.append(_table([
        ["Proyecto", project_name or "—"],
        ["Elemento", request.get("element_name", "—")],
        ["Autor", author or "—"],
        ["Norma", tr["norm"]["name"]],
        ["Edición", tr["norm"]["edition"]],
        ["Método", tr["method"]],
        ["Estado de validación", tr["validation_status"]],
        ["Software", f"{SOFTWARE_NAME} v{__version__}"],
        ["Fecha", now],
    ], [40 * mm, 140 * mm], S["base"], header=False))
    E.append(Spacer(1, 4))
    E.append(_p("AVISO: herramienta de apoyo académico y profesional. Los resultados deben ser revisados "
                "independientemente por un ingeniero estructural responsable antes de su uso en un "
                "proyecto constructivo real.", S["warn"]))

    # Datos de entrada
    E.append(_p("1. Datos de entrada y unidades", S["h2"]))
    rows = [["Dato", "Valor"]]
    for k, v in tr["inputs"].items():
        if isinstance(v, dict):
            v = "; ".join(f"{kk} = {_num(vv) if isinstance(vv, float) else vv}" for kk, vv in v.items()
                          if vv is not None)
        elif isinstance(v, list):
            v = " | ".join("; ".join(f"{kk} = {_num(vv) if isinstance(vv, float) else vv}"
                                     for kk, vv in it.items() if vv is not None)
                           if isinstance(it, dict) else str(it) for it in v)
        elif isinstance(v, bool):
            v = "sí" if v else "no"
        elif v is None:
            v = "—"
        elif isinstance(v, float):
            v = _num(v)
        rows.append([k.replace("_", " "), v])
    E.append(_table(rows, [60 * mm, 120 * mm], S["small"]))
    E.append(Spacer(1, 3))
    E.append(_p("Unidades: " + "; ".join(f"{k}: {v}" for k, v in tr["units"].items()), S["small"]))

    # Materiales
    E.append(_p("2. Materiales", S["h2"]))
    c = result["materials"]["concrete"]
    s = result["materials"].get("steel") or result["materials"]["stirrups"]
    E.append(_table([
        ["Hormigón", "Valor", "Acero" if "steel" in result["materials"] else "Acero de cercos", "Valor"],
        ["Clase", c["name"], "Designación", s["name"]],
        ["f_ck (MPa)", _num(c["fck"]), "f_yk (MPa)", _num(s["fyk"])],
        ["γ_c", _num(c["gamma_c"]), "γ_s", _num(s["gamma_s"])],
        ["α_cc", _num(c["alpha_cc"]), "f_yd (MPa)", _num(s["fyd"])],
        ["f_cd (MPa)", _num(c["fcd"]), "E_s (MPa)", _num(s["Es"], 0)],
        ["f_ctm (MPa)", _num(c["fctm"]), "ε_yd (‰)", _num(s["eps_yd"] * 1000)],
        ["E_cm (MPa)", _num(c["Ecm"], 0), "Rama superior", s["branch"]],
        ["ε_c2 / ε_cu2 (‰)", f"{_num(c['eps_c2']*1000)} / {_num(c['eps_cu2']*1000)}",
         "ε_ud (‰)", _num(s["eps_ud"] * 1000) if s["eps_ud"] else "sin límite (rama horizontal)"],
        ["n; λ; η", f"{_num(c['n'])}; {_num(c['lambda'])}; {_num(c['eta'])}", "Situación", s["situation"]],
    ], [40 * mm, 50 * mm, 40 * mm, 50 * mm], S["small"]))

    # Geometría y armado
    E.append(_p("3. Geometría y armaduras", S["h2"]))
    if geom:
        info = [["Propiedad", "Valor"],
                ["A_c (mm²)", _num(geom["Ac"], 0)], ["y_g desde fibra superior (mm)", _num(geom["yg"], 1)],
                ["I_g (mm⁴)", _num(geom["Ig"])], ["A_s inferior (mm²)", _num(geom["As_inferior"], 0)],
                ["A_s superior (mm²)", _num(geom["As_superior"], 0)],
                ["d (cara inferior) (mm)", _num(geom["d_inferior"], 1)]]
        t = Table([[_section_drawing(geom), _table(info, [55 * mm, 35 * mm], S["small"])]],
                  colWidths=[90 * mm, 90 * mm])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        E.append(t)
    for line in result_lines:
        E.append(Spacer(1, 3))
        E.append(_p(line, S["base"]))

    # Hipótesis
    E.append(_p("4. Hipótesis de cálculo", S["h2"]))
    for a in tr["assumptions"]:
        E.append(_p("• " + a, S["base"]))

    # Parámetros normativos
    E.append(_p("5. Parámetros normativos utilizados", S["h2"]))
    rows = [["Símbolo", "Valor", "Referencia", "Estado"]]
    for p in tr["parameters_used"]:
        rows.append([p["symbol"] + " — " + p["description"], f"{p['value']} {p['unit']}", p["reference"],
                     p["status"].replace("_", " ")])
    E.append(_table(rows, [75 * mm, 25 * mm, 45 * mm, 35 * mm], S["small"]))

    # Procedimiento
    E.append(_p("6. Procedimiento: ecuaciones, sustituciones y resultados intermedios", S["h2"]))
    rows = [["Paso", "Ecuación / sustitución", "Resultado", "Referencia"]]
    for st in tr["steps"]:
        eq = st["equation"] + (("\n" + st["substitution"]) if st["substitution"] else "")
        res = "—" if st["result"] is None else f"{st['symbol']} = {_num(st['result'])} {st['unit']}"
        rows.append([st["title"], Paragraph(escape(eq).replace("\n", "<br/>"), S["mono"]), res, st["reference"]])
    E.append(_table(rows, [42 * mm, 70 * mm, 33 * mm, 35 * mm], S["small"]))

    # Verificaciones
    E.append(_p("7. Tabla de verificaciones", S["h2"]))
    rows = [["Verificación", "Solicitación / valor", "Límite / capacidad", "Resultado", "Referencia"]]
    for ck in tr["checks"]:
        res = "CUMPLE" if ck["ok"] is True else ("NO CUMPLE" if ck["ok"] is False else "NO EVALUABLE")
        rows.append([ck["name"], ck["demand"], ck["capacity"], res, ck["reference"]])
    t = _table(rows, [45 * mm, 35 * mm, 35 * mm, 22 * mm, 43 * mm], S["small"])
    for i, ck in enumerate(tr["checks"], 1):
        col = "#e3f4e6" if ck["ok"] is True else ("#fbe3e1" if ck["ok"] is False else "#fff4d6")
        t.setStyle(TableStyle([("BACKGROUND", (3, i), (3, i), colors.HexColor(col))]))
    E.append(t)
    overall = tr["all_checks_ok"]
    E.append(Spacer(1, 4))
    E.append(_p("Resultado global: " + ("TODAS LAS VERIFICACIONES SE CUMPLEN" if overall is True else
                                         "HAY VERIFICACIONES NO SUPERADAS" if overall is False else
                                         "VERIFICACIÓN INCOMPLETA"), S["h2"]))

    # Advertencias y limitaciones
    E.append(_p("8. Advertencias y limitaciones", S["h2"]))
    for w in tr["warnings"]:
        E.append(_p("⚠ " + w, S["warn"]))
    for l in tr["limitations"]:
        E.append(_p("• " + l, S["base"]))
    E.append(Spacer(1, 6))
    E.append(_p(f"Documento generado por {SOFTWARE_NAME} v{__version__} el {now}. Estado de cada parámetro: "
                "«verificado texto oficial» = cotejado con el Anejo 19 publicado en el BOE; «pendiente "
                "verificacion» = depende de disposiciones no consultadas; «no normativo» = criterio del programa.",
                S["small"]))
    doc.build(E, onFirstPage=on_page, onLaterPages=on_page)
    return buf.getvalue()
