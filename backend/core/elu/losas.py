"""Losas macizas unidireccionales de hormigón armado (Anejo 19, 9.3, con 6.1, 6.2.2 y 9.2.1.1).

Cálculo por banda de 1 m de ancho:

* Flexión simple ELU: dimensionado con el bloque rectangular y comprobación con el método general
  (los mismos procedimientos que en vigas, ``flexion.block_design`` y ``analysis.analyse_bending``).
* Cuantías mínima y máxima (9.3.1.1(1) → 9.2.1.1(1) y (3)), con la alternativa A_s,min = 1,2·A_s,nec
  para losas con riesgo pequeño de rotura frágil (nota de 9.3.1.1(1)).
* Separación máxima s < 300 mm y s < 3h (9.3.1.1(3)); separación libre mínima (8.2(2)).
* Armadura transversal secundaria ≥ 20 % de la principal (9.3.1.1(2)).
* Cortante sin armadura de cortante V_Rd,c (6.2.2); en losas puede omitirse la armadura mínima de
  cortante cuando es posible la redistribución transversal (6.2.1(4)).

Fuera de alcance: losas bidireccionales y planas (9.4), punzonamiento (6.4), armadura de cortante
en losas (9.3.2), bordes libres y esquinas (9.3.1.3, 9.3.1.4), anclajes (8.4.4).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..materials import Concrete, ReinforcingSteel
from ..parameters import ParameterSet
from ..section import Bar, RectangularShape, ReinforcedSection, min_clear_spacing
from ..trace import CalcTrace, fmt
from ..units import kn_to_n, knm_to_nmm, n_to_kn, nmm_to_knm
from .analysis import analyse_bending
from .cortante import vrdc
from .flexion import as_max, as_min, block_design, ductility_limit

VALIDATION_STATUS = (
    "Implementado. Ecuaciones y parámetros cotejados con el texto oficial del Anejo 19 "
    "(BOE-A-2021-13681, apartados 9.3, 9.2.1.1, 6.1 y 6.2.2). Validación matemática interna superada. "
    "PENDIENTE: contraste con ejemplos resueltos de bibliografía independiente."
)
WIDTH = 1000.0  # banda de cálculo (mm)


class SlabInputError(ValueError):
    pass


@dataclass
class SlabInput:
    h: float
    cover: float                    # recubrimiento nominal hasta la armadura principal (mm)
    m_Ed_knm: float                 # momento de cálculo por metro (kN·m/m), + tracción inferior
    v_Ed_kn: float = 0.0            # cortante de cálculo por metro (kN/m)
    span: float | None = None       # luz eficaz l_eff (mm), para 9.3(1)
    mode: str = "design"
    bar_diameter: float = 12.0      # armadura principal
    bar_spacing: float | None = None   # comprobación
    secondary_diameter: float | None = 8.0
    secondary_spacing: float | None = None
    compression_bar_diameter: float | None = None   # armadura en la cara comprimida (opcional)
    compression_bar_spacing: float | None = None
    low_brittle_risk: bool = False  # nota de 9.3.1.1(1)
    concrete_class: str = "C25/30"
    steel_grade: str = "B500S"
    situation: str = "persistente"
    dg: float = 20.0
    params: ParameterSet = field(default_factory=ParameterSet)
    element_name: str = "Losa"

    def validate(self) -> None:
        if self.h <= 0 or self.cover <= 0:
            raise SlabInputError("Canto y recubrimiento deben ser positivos")
        if self.cover + self.bar_diameter >= self.h / 2:
            raise SlabInputError("Recubrimiento y diámetro incompatibles con el canto")
        if not math.isfinite(self.m_Ed_knm) or self.m_Ed_knm == 0:
            raise SlabInputError("Indique un momento de cálculo m_Ed no nulo")
        if self.v_Ed_kn < 0:
            raise SlabInputError("v_Ed es el valor absoluto del cortante por metro (≥ 0)")
        if self.mode not in ("design", "check"):
            raise SlabInputError("Modo no válido")
        if self.mode == "check" and (self.bar_spacing is None or self.bar_spacing <= 0):
            raise SlabInputError("Indique la separación de la armadura principal")
        if self.bar_spacing is not None and self.bar_spacing <= self.bar_diameter:
            raise SlabInputError("La separación debe ser mayor que el diámetro")


def _strip(h: float, conc_cover: float, As_t: float, d: float, As_c: float, d2: float, sign: int,
           params: ParameterSet) -> ReinforcedSection:
    """Banda de 1 m con la armadura representada por barras equivalentes de igual área (solo
    intervienen el área y la profundidad en el análisis de flexión)."""
    sec = ReinforcedSection(RectangularShape(WIDTH, h), conc_cover, 0.0, [], 20.0, params)
    tface, cface = ("inferior", "superior") if sign > 0 else ("superior", "inferior")
    y_t = d if sign > 0 else h - d
    y_c = d2 if sign > 0 else h - d2
    bars = [Bar(WIDTH / 2, y_t, math.sqrt(4 * As_t / math.pi), 1, tface)]
    if As_c > 0:
        bars.append(Bar(WIDTH / 2, y_c, math.sqrt(4 * As_c / math.pi), 1, cface))
    sec.bars = bars
    return sec


def slab_check(inp: SlabInput) -> dict:
    inp.validate()
    p = inp.params
    conc = Concrete.from_class(inp.concrete_class, p, inp.situation)
    steel = ReinforcingSteel.from_grade(inp.steel_grade, p, inp.situation)
    sign = 1 if inp.m_Ed_knm > 0 else -1
    h = inp.h
    M = knm_to_nmm(abs(inp.m_Ed_knm))
    phi = inp.bar_diameter
    d = h - inp.cover - phi / 2

    tr = CalcTrace("Losa maciza unidireccional — " + ("dimensionado" if inp.mode == "design" else "comprobación"),
                   "Banda de 1 m: flexión simple (6.1, 3.1.7), cuantías y separaciones (9.3.1), cortante sin "
                   "armadura (6.2.2)", VALIDATION_STATUS)
    tr.units = {"longitudes": "mm", "armaduras": "mm²/m", "momentos": "kN·m/m", "cortantes": "kN/m"}
    tr.inputs = {"elemento": inp.element_name, "h_mm": h, "recubrimiento_mm": inp.cover, "m_Ed_kNm_m": inp.m_Ed_knm,
                 "v_Ed_kN_m": inp.v_Ed_kn, "l_eff_mm": inp.span, "modo": inp.mode, "phi_mm": phi,
                 "s_mm": inp.bar_spacing, "phi_secundaria_mm": inp.secondary_diameter,
                 "s_secundaria_mm": inp.secondary_spacing, "phi_comprimida_mm": inp.compression_bar_diameter,
                 "s_comprimida_mm": inp.compression_bar_spacing, "riesgo_rotura_fragil_pequeno": inp.low_brittle_risk,
                 "hormigon": inp.concrete_class, "acero": inp.steel_grade}
    tr.assume("Losa maciza unidireccional calculada por banda de 1 m de ancho en flexión simple.")
    tr.assume("La armadura de cada cara se representa por su área por metro a la profundidad de su eje.")
    tr.assume("El recubrimiento nominal se mide hasta la armadura principal (losa sin cercos).")
    tr.limit("No se comprueban punzonamiento (6.4), losas bidireccionales o planas (9.4), bordes libres y esquinas "
             "(9.3.1.3-9.3.1.4) ni anclajes (8.4.4, 9.3.1.2(1)).")
    conc.trace_design_values(tr)
    steel.trace_design_values(tr)
    tr.step("Canto útil", "Definición geométrica", "d = h − c − φ/2", f"{fmt(h)} − {fmt(inp.cover)} − {fmt(phi)}/2",
            d, "mm", "d")

    # 9.3(1)
    if inp.span is None:
        tr.check("Ámbito de losa (l_eff ≥ 5h)", "Anejo 19, 9.3(1) (BOE pág. 98430)", "l_eff no indicada",
                 f"5h = {fmt(5 * h)} mm", None, "Indique la luz eficaz.")
    else:
        tr.check("Ámbito de losa (l_eff ≥ 5h)", "Anejo 19, 9.3(1) (BOE pág. 98430)", f"l_eff = {fmt(inp.span)} mm",
                 f"5h = {fmt(5 * h)} mm", inp.span >= 5 * h)

    xi_lim = ductility_limit(conc, p, tr)
    d2 = inp.cover + (inp.compression_bar_diameter or 0) / 2
    bd = block_design(WIDTH, d, d2, M, conc, steel, xi_lim)
    tr.step("Momento reducido", "Equilibrio (bloque rectangular, 3.1.7(3))", "μ = m_Ed/(b·d²·η·f_cd), b = 1000 mm",
            "", bd.mu, "-", "μ")
    if not bd.feasible or bd.compression_needed:
        tr.warn("El momento supera el límite sin armadura de compresión: aumente el canto de la losa.")
    As_req = bd.As1 if bd.feasible else math.nan
    if bd.feasible:
        tr.step("Armadura de tracción necesaria", "Equilibrio (bloque rectangular)",
                "A_s = η·f_cd·b·λ·x/f_yd" + (" (+ compresión)" if bd.compression_needed else ""), "", As_req, "mm²/m",
                "A_s,nec")
    low = inp.low_brittle_risk and bd.feasible
    Asmin = as_min(conc, steel, RectangularShape(WIDTH, h), sign, p, tr, low, As_req if low else None)
    if inp.low_brittle_risk:
        tr.assume("Losa con riesgo pequeño de rotura frágil: A_s,min = 1,2·A_s,nec (nota de 9.3.1.1(1)), por "
                  "decisión del usuario.")
    Asmax = as_max(WIDTH * h, p, tr)
    s_lim = min(300.0, 3 * h)
    tr.step("Separación máxima de barras", "Anejo 19, 9.3.1.1(3) (BOE pág. 98430)", "s < 300 mm y s < 3h",
            f"min(300; 3·{fmt(h)})", s_lim, "mm", "s_max (estricta)")
    smin_clear = min_clear_spacing(phi, inp.dg, p)
    step = p["stirrup_spacing_step"]

    result: dict = {"d": d, "As_req": As_req, "As_min": Asmin, "As_max": Asmax, "s_lim": s_lim, "mu": bd.mu}
    # --- disposición ---
    if inp.mode == "design":
        need = max(As_req if math.isfinite(As_req) else math.inf, Asmin)
        alts = []
        for f in p["bar_diameters"]:
            dd = h - inp.cover - f / 2
            bdf = block_design(WIDTH, dd, d2, M, conc, steel, xi_lim)
            if not bdf.feasible:
                continue
            req_f = max(bdf.As1, p["As_min_secondary_factor"] * bdf.As1 if low else Asmin)
            if not math.isfinite(req_f):
                continue
            a1 = math.pi * f ** 2 / 4
            s = math.floor(min(a1 * WIDTH / req_f, s_lim - 1e-9) / step) * step
            if s - f < min_clear_spacing(f, inp.dg, p) or s <= 0:
                continue
            alts.append({"diameter": f, "spacing": s, "As": a1 * WIDTH / s, "d": dd})
        alts.sort(key=lambda a: (a["As"], -a["spacing"]))
        result["alternatives"] = alts[:6]
        pick = next((a for a in alts if a["diameter"] == phi), alts[0] if alts else None)
        if pick is None:
            tr.check("Disposición de la armadura principal", "9.3.1.1", f"A_s,nec = {fmt(need, 0)} mm²/m",
                     "sin solución práctica", False)
            return _finish(tr, result, conc, steel)
        phi, s, d = pick["diameter"], pick["spacing"], pick["d"]
        tr.step("Armadura principal propuesta", "Criterio del programa (redondeo a 25 mm); 9.3.1.1(3)",
                "s = A_φ·1000/A_s,nec ≤ s_max", f"φ{fmt(phi)}", s, "mm", "s")
        result["proposal"] = {"diameter": phi, "spacing": s}
    else:
        s = inp.bar_spacing
    As = math.pi * phi ** 2 / 4 * WIDTH / s
    result.update({"phi": phi, "s": s, "As": As, "d": d})
    tr.step("Armadura principal dispuesta", "Geometría", "A_s = (π·φ²/4)·1000/s", f"φ{fmt(phi)} c/{fmt(s)} mm",
            As, "mm²/m", "A_s")

    # armadura en cara comprimida (opcional)
    As_c = 0.0
    if inp.compression_bar_diameter and inp.compression_bar_spacing:
        As_c = math.pi * inp.compression_bar_diameter ** 2 / 4 * WIDTH / inp.compression_bar_spacing
    sec = _strip(h, inp.cover, As, d, As_c, d2, sign, p)
    res = analyse_bending(sec, conc, steel, sign, "parabola-rectangulo")
    MRd = abs(res.M_Rd)
    result["m_Rd"] = MRd
    result["xi"] = res.xi
    tr.step("Momento resistente por metro (método general)", "Anejo 19, 6.1; 3.1.7(1)", "m_Rd (ΣN = 0)",
            f"x = {fmt(res.x, 1)} mm", nmm_to_knm(MRd), "kN·m/m", "m_Rd")
    tr.check("Resistencia a flexión", "Anejo 19, 6.1", f"|m_Ed| = {fmt(abs(inp.m_Ed_knm))} kN·m/m",
             f"m_Rd = {fmt(nmm_to_knm(MRd))} kN·m/m", MRd >= M * (1 - 1e-9))
    tr.check("Criterio de ductilidad x/d ≤ ξ_lim", "Anejo 19, 5.5(4) (criterio adoptado)", f"x/d = {fmt(res.xi, 3)}",
             f"ξ_lim = {fmt(xi_lim, 3)}", res.xi <= xi_lim + 1e-9)
    tr.check("Armadura mínima", "Anejo 19, 9.3.1.1(1) → 9.2.1.1(1)", f"A_s = {fmt(As, 0)} mm²/m",
             f"A_s,min = {fmt(Asmin, 0)} mm²/m", As >= Asmin - 1e-6)
    tr.check("Armadura máxima", "Anejo 19, 9.3.1.1(1) → 9.2.1.1(3)", f"A_s = {fmt(As, 0)} mm²/m",
             f"A_s,max = {fmt(Asmax, 0)} mm²/m", As <= Asmax + 1e-6)
    tr.check("Separación máxima de la armadura principal", "Anejo 19, 9.3.1.1(3)", f"s = {fmt(s)} mm",
             f"< {fmt(s_lim)} mm", s < s_lim)
    tr.check("Separación libre mínima", "Anejo 19, 8.2(2)", f"s − φ = {fmt(s - phi)} mm",
             f"s_min = {fmt(min_clear_spacing(phi, inp.dg, p), 1)} mm", s - phi >= min_clear_spacing(phi, inp.dg, p) - 1e-9)

    # armadura secundaria
    sec_req = 0.2 * As
    tr.step("Armadura transversal secundaria mínima", "Anejo 19, 9.3.1.1(2) (BOE pág. 98430)", "A_s,t ≥ 0,20·A_s",
            f"0,20·{fmt(As, 0)}", sec_req, "mm²/m", "A_s,t,min")
    result["As_secondary_min"] = sec_req
    if inp.secondary_diameter:
        fs = inp.secondary_diameter
        if inp.secondary_spacing:
            ss = inp.secondary_spacing
        else:
            ss = math.floor(min(math.pi * fs ** 2 / 4 * WIDTH / sec_req, s_lim - 1e-9) / step) * step
            tr.step("Armadura secundaria propuesta", "Criterio del programa; 9.3.1.1(2)-(3)", "", f"φ{fmt(fs)}", ss, "mm", "s_t")
        As_t = math.pi * fs ** 2 / 4 * WIDTH / ss
        result["secondary"] = {"diameter": fs, "spacing": ss, "As": As_t}
        tr.check("Armadura transversal secundaria", "Anejo 19, 9.3.1.1(2)", f"A_s,t = {fmt(As_t, 0)} mm²/m (φ{fmt(fs)} c/{fmt(ss)})",
                 f"0,20·A_s = {fmt(sec_req, 0)} mm²/m", As_t >= sec_req - 1e-6)
        tr.check("Separación de la armadura secundaria", "Anejo 19, 9.3.1.1(3)", f"s_t = {fmt(ss)} mm", f"< {fmt(s_lim)} mm",
                 ss < s_lim)
    else:
        tr.check("Armadura transversal secundaria", "Anejo 19, 9.3.1.1(2)", "no indicada",
                 f"0,20·A_s = {fmt(sec_req, 0)} mm²/m", None, "Indique la armadura de reparto.")

    # cortante
    if inp.v_Ed_kn > 0:
        rc = vrdc(conc, WIDTH, d, As, 0.0, WIDTH * h, p, tr)
        result["v_Rd_c"] = rc["VRdc"]
        ok = kn_to_n(inp.v_Ed_kn) <= rc["VRdc"] * (1 + 1e-9)
        tr.check("Cortante sin armadura de cortante", "Anejo 19, 6.2.1(3), 6.2.2 (BOE págs. 98359-98360)",
                 f"v_Ed = {fmt(inp.v_Ed_kn)} kN/m", f"V_Rd,c = {fmt(n_to_kn(rc['VRdc']))} kN/m", ok,
                 "" if ok else "Aumente el canto o la armadura longitudinal, o disponga armadura de cortante "
                 "(canto ≥ 200 mm, 9.3.2(1); véase el módulo de cortante).")
        tr.assume("Se omite la armadura mínima de cortante: en losas macizas con posibilidad de redistribución "
                  "transversal de las cargas (6.2.1(4)).")
        tr.assume("A_sl = armadura principal dispuesta, prolongada l_bd + d más allá de la sección (figura A19.6.3).")
    else:
        tr.limit("No se ha indicado v_Ed: no se comprueba el cortante.")

    # informaciones complementarias
    m_abs = abs(inp.m_Ed_knm)
    tr.step("Armadura superior por empotramiento parcial no considerado", "Anejo 19, 9.3.1.2(2) (BOE pág. 98431)",
            "resistir ≥ 25 % del momento máximo del vano (15 % en apoyos extremos), extendida ≥ 0,2·l",
            f"0,25·{fmt(m_abs)} = {fmt(0.25 * m_abs)} kN·m/m; 0,15·{fmt(m_abs)} = {fmt(0.15 * m_abs)} kN·m/m",
            None, "", note="Aplicable si m_Ed es el momento máximo de vano y el apoyo tiene un empotramiento "
                           "parcial no considerado en el cálculo.")
    tr.step("Armadura en apoyos de losas simplemente apoyadas", "Anejo 19, 9.3.1.2(1)",
            "al menos la mitad de la armadura de centro de vano debe prolongarse hasta el apoyo", "", None, "")
    if h <= 200:
        tr.step("Control de la fisuración", "Anejo 19, 7.3.3(1) (BOE pág. 98396)",
                "h ≤ 200 mm y disposiciones de 9.3 ⇒ no se requieren medidas específicas (sin tracción axil significativa)",
                f"h = {fmt(h)} mm", None, "")
    return _finish(tr, result, conc, steel)


def _finish(tr, result, conc, steel) -> dict:
    return {"ok": tr.all_checks_ok, "trace": tr.to_dict(), "result": result,
            "materials": {"concrete": conc.properties(), "steel": steel.properties()}}
