"""Flexión simple en ELU de vigas: dimensionado y comprobación.

Alcance implementado:

* Dimensionado de secciones RECTANGULARES en flexión simple (N_Ed = 0) con el
  bloque rectangular de tensiones (Anejo 19, 3.1.7(3)), con armadura de
  compresión cuando la profundidad de la fibra neutra supera el límite adoptado.
* Comprobación de secciones rectangulares y en T con armaduras en varias capas
  mediante el método general de compatibilidad de deformaciones con el diagrama
  parábola-rectángulo (``analysis.analyse_bending``).
* Armaduras mínima y máxima (9.2.1.1), separación entre barras (8.2) y propuesta
  de disposición práctica de barras.

Fuera de alcance (se informa como limitación): esfuerzo axil concomitante,
flexión esviada, secciones de ancho variable distinto de T, armaduras activas,
redistribución de momentos (salvo el parámetro δ del criterio de ductilidad),
anchura eficaz del ala (5.3.2.1, debe introducirla el usuario), recubrimientos
por durabilidad (4.4.1) y cortante/torsión.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

from ..materials import Concrete, ReinforcingSteel
from ..parameters import ParameterSet
from ..section import Layer, RectangularShape, ReinforcedSection, Shape, SectionError, TShape, min_clear_spacing
from ..trace import CalcTrace, fmt
from ..units import knm_to_nmm, nmm_to_knm
from .analysis import AnalysisError, BendingResult, analyse_bending

VALIDATION_STATUS = (
    "Implementado. Validación matemática interna (equilibrio, soluciones cerradas y "
    "comparación entre métodos) superada. Validación normativa independiente PENDIENTE: "
    "los parámetros marcados como 'pendiente de verificación' no se han contrastado con "
    "el texto oficial del Anejo 19."
)


class FlexureInputError(ValueError):
    pass


@dataclass
class FlexureInput:
    shape: Shape
    cover: float
    stirrup_diameter: float
    M_Ed_knm: float
    concrete_class: str = "C25/30"
    steel_grade: str = "B500S"
    steel_branch: str = "horizontal"
    situation: str = "persistente"
    dg: float = 20.0
    assumed_bar_diameter: float = 16.0      # solo dimensionado
    layers: list[Layer] = field(default_factory=list)  # solo comprobación
    params: ParameterSet = field(default_factory=ParameterSet)
    element_name: str = "Viga"

    def validate(self) -> None:
        if not math.isfinite(self.M_Ed_knm):
            raise FlexureInputError("M_Ed no es un número finito")
        if self.cover <= 0:
            raise FlexureInputError("El recubrimiento nominal debe ser positivo")
        if self.cover + self.stirrup_diameter >= self.shape.h / 2:
            raise FlexureInputError("Recubrimiento + estribo incompatibles con el canto")


# ----------------------------------------------------------------------------
# Elementos comunes
# ----------------------------------------------------------------------------

def _materials(inp: FlexureInput) -> tuple[Concrete, ReinforcingSteel]:
    c = Concrete.from_class(inp.concrete_class, inp.params, inp.situation)
    s = ReinforcingSteel.from_grade(inp.steel_grade, inp.params, inp.situation, inp.steel_branch)  # type: ignore[arg-type]
    return c, s


def _new_trace(calc: str, method: str, inp: FlexureInput) -> CalcTrace:
    tr = CalcTrace(calc, method, VALIDATION_STATUS)
    tr.units = {"longitudes": "mm", "áreas": "mm²", "tensiones": "MPa (N/mm²)",
                "momentos": "kN·m", "fuerzas": "kN", "deformaciones": "‰"}
    tr.inputs = {
        "elemento": inp.element_name,
        "seccion": inp.shape.to_dict(),
        "recubrimiento_nominal_mm": inp.cover,
        "diametro_estribo_mm": inp.stirrup_diameter,
        "tamano_arido_mm": inp.dg,
        "hormigon": inp.concrete_class,
        "acero": inp.steel_grade,
        "rama_diagrama_acero": inp.steel_branch,
        "situacion_proyecto": inp.situation,
        "M_Ed_kNm": inp.M_Ed_knm,
    }
    tr.assume("Flexión simple: esfuerzo axil N_Ed = 0 (6.1).")
    tr.assume("Las secciones planas permanecen planas; adherencia perfecta (6.1(2)).")
    tr.assume("Se desprecia la resistencia a tracción del hormigón (6.1(2)).")
    tr.assume("Diagrama de cálculo del acero bilineal (3.2.7(2)) con rama superior "
              f"{inp.steel_branch}.")
    tr.assume("Momento positivo: tracción en la cara inferior; negativo: tracción en la superior.")
    tr.limit("El recubrimiento nominal lo fija el usuario: el programa no calcula c_nom por "
             "durabilidad, adherencia ni resistencia al fuego (4.4.1).")
    tr.limit("No se comprueban cortante, torsión, anclajes, solapes, fisuración ni flechas.")
    tr.limit("La anchura eficaz del ala en secciones en T (5.3.2.1) debe introducirla el usuario.")
    return tr


def ductility_limit(conc: Concrete, params: ParameterSet, tr: CalcTrace | None = None) -> float:
    """Profundidad relativa máxima de la fibra neutra ξ_lim = x_u/d según 5.5(4).

    Con δ = 1 (sin redistribución) se adopta como criterio de ductilidad de proyecto.
    """
    delta = params["delta_redistribucion"]
    factor = 0.6 + 0.0014 / conc.eps_cu2
    if conc.fck <= 50:
        k1, k2b = params["k1_redist"], params["k2_redist_base"]
        k2 = k2b * factor
        xi = (delta - k1) / k2
        if tr:
            for k in ("delta_redistribucion", "k1_redist", "k2_redist_base"):
                tr.use_param(params, k)
            tr.step("Profundidad relativa límite de la fibra neutra", "Anejo 19, 5.5(4), expresión (5.10a)",
                    "ξ_lim = (δ − k1)/k2;  k2 = 1,25·(0,6 + 0,0014/ε_cu2)",
                    f"ξ_lim = ({fmt(delta)} − {fmt(k1)})/({fmt(k2b)}·(0,6 + 0,0014/{fmt(conc.eps_cu2, 5)}))",
                    xi, "-", "ξ_lim")
    else:
        k3, k4b = params["k3_redist"], params["k4_redist_base"]
        k4 = k4b * factor
        xi = (delta - k3) / k4
        if tr:
            for k in ("delta_redistribucion", "k3_redist", "k4_redist_base"):
                tr.use_param(params, k)
            tr.step("Profundidad relativa límite de la fibra neutra", "Anejo 19, 5.5(4), expresión (5.10b)",
                    "ξ_lim = (δ − k3)/k4;  k4 = 1,25·(0,6 + 0,0014/ε_cu2)",
                    f"ξ_lim = ({fmt(delta)} − {fmt(k3)})/({fmt(k4b)}·(0,6 + 0,0014/{fmt(conc.eps_cu2, 5)}))",
                    xi, "-", "ξ_lim")
    if tr:
        tr.assume("Criterio de ductilidad adoptado: x_u/d ≤ ξ_lim obtenido de la expresión (5.10) "
                  "con el valor de δ configurado. Con δ = 1 la expresión no es una exigencia "
                  "explícita del Anejo para secciones sin redistribución; se adopta como criterio "
                  "de proyecto para garantizar un comportamiento dúctil (decisión documentada en "
                  "docs/decisiones.md).")
    return xi


def as_min(conc: Concrete, steel: ReinforcingSteel, bt: float, d: float, params: ParameterSet,
           tr: CalcTrace | None = None) -> float:
    a = params["As_min_coef_fct"]
    g = params["As_min_coef_geom"]
    v1 = a * conc.fctm / steel.fyk * bt * d
    v2 = g * bt * d
    val = max(v1, v2)
    if tr:
        tr.use_param(params, "As_min_coef_fct")
        tr.use_param(params, "As_min_coef_geom")
        tr.step("Armadura mínima de tracción", "Anejo 19, 9.2.1.1(1), expresión (9.1N)",
                "A_s,min = max(0,26·(f_ctm/f_yk)·b_t·d; 0,0013·b_t·d)",
                f"A_s,min = max({fmt(a)}·({fmt(conc.fctm)}/{fmt(steel.fyk)})·{fmt(bt)}·{fmt(d, 1)}; "
                f"{fmt(g, 4)}·{fmt(bt)}·{fmt(d, 1)})", val, "mm²", "A_s,min")
    return val


def as_max(Ac: float, params: ParameterSet, tr: CalcTrace | None = None) -> float:
    k = params["As_max_coef"]
    val = k * Ac
    if tr:
        tr.use_param(params, "As_max_coef")
        tr.step("Armadura máxima (tracción o compresión)", "Anejo 19, 9.2.1.1(3)",
                "A_s,max = 0,04·A_c", f"A_s,max = {fmt(k)}·{fmt(Ac, 0)}", val, "mm²", "A_s,max")
    return val


def _bt(shape: Shape, sign: int) -> float:
    """Ancho medio de la zona traccionada (9.2.1.1(1)).

    En T con momento positivo el ala está comprimida → b_t = b_w. Con momento negativo
    el ala está traccionada; se adopta b_t = b_w del lado de la seguridad respecto a
    la cuantía mínima solo si el ala no se considera; aquí se toma b_f (ala traccionada)
    y se advierte.
    """
    if isinstance(shape, TShape):
        return shape.bw if sign > 0 else shape.bf
    return shape.bounding_width


# ----------------------------------------------------------------------------
# Dimensionado con bloque rectangular (sección rectangular)
# ----------------------------------------------------------------------------

@dataclass
class BlockDesign:
    d: float
    d2: float
    mu: float
    xi_lim: float
    x_lim: float
    M_lim: float
    x: float
    As1: float
    As2: float
    sigma_s2: float
    compression_needed: bool
    feasible: bool
    message: str = ""


def block_design(b: float, d: float, d2: float, M: float, conc: Concrete, steel: ReinforcingSteel,
                 xi_lim: float) -> BlockDesign:
    """Solución cerrada del bloque rectangular para sección rectangular (M en N·mm, > 0)."""
    lam, eta, fcd, fyd = conc.lam, conc.eta, conc.fcd, steel.fyd
    sc = eta * fcd
    # La armadura de tracción debe alcanzar f_yd para que la solución sea válida:
    xi_y = conc.eps_cu3 / (conc.eps_cu3 + steel.eps_yd)
    xi_eff = min(xi_lim, xi_y)
    x_lim = xi_eff * d
    M_lim = sc * b * lam * x_lim * (d - lam * x_lim / 2)
    mu = M / (b * d * d * sc)
    if M <= M_lim:
        disc = 1 - 2 * mu
        y = d * (1 - math.sqrt(disc))
        x = y / lam
        As1 = sc * b * y / fyd
        return BlockDesign(d, d2, mu, xi_eff, x_lim, M_lim, x, As1, 0.0, 0.0, False, True)
    # Armadura de compresión
    x = x_lim
    if x <= d2:
        return BlockDesign(d, d2, mu, xi_eff, x_lim, M_lim, x, math.nan, math.nan, 0.0, True, False,
                           "La fibra neutra límite queda por encima de la armadura de compresión: "
                           "aumentar el canto de la sección.")
    eps_s2 = conc.eps_cu3 * (x - d2) / x
    sig_s2 = steel.sigma(eps_s2)  # valor absoluto de compresión
    # descuento del hormigón desplazado si la barra está dentro del bloque
    sig_net = sig_s2 - (sc if d2 <= lam * x else 0.0)
    if sig_net <= 0:
        return BlockDesign(d, d2, mu, xi_eff, x_lim, M_lim, x, math.nan, math.nan, sig_s2, True, False,
                           "La armadura de compresión no resulta eficaz con la geometría dada.")
    As2 = (M - M_lim) / (sig_net * (d - d2))
    As1 = (sc * b * lam * x + As2 * sig_net) / fyd
    return BlockDesign(d, d2, mu, xi_eff, x_lim, M_lim, x, As1, As2, sig_s2, True, True)


def _layers_text(layers: list[Layer]) -> str:
    return " + ".join(f"{l.n}φ{int(l.diameter)}" for l in layers)


# ----------------------------------------------------------------------------
# Procedimientos públicos
# ----------------------------------------------------------------------------

def design_flexure(inp: FlexureInput) -> dict:
    """Dimensionado de la armadura longitudinal de una sección rectangular."""
    inp.validate()
    if not isinstance(inp.shape, RectangularShape):
        raise FlexureInputError(
            "El dimensionado automático está implementado solo para secciones rectangulares. "
            "Para secciones en T utilice la comprobación de una armadura existente (método general).")
    if inp.M_Ed_knm == 0:
        raise FlexureInputError("M_Ed = 0: no hay solicitación de flexión que dimensionar")
    p = inp.params
    conc, steel = _materials(inp)
    sign = 1 if inp.M_Ed_knm > 0 else -1
    tface = "inferior" if sign > 0 else "superior"
    cface = "superior" if sign > 0 else "inferior"
    M = knm_to_nmm(abs(inp.M_Ed_knm))
    b, h = inp.shape.b, inp.shape.h
    edge = inp.cover + inp.stirrup_diameter

    tr = _new_trace("Flexión simple ELU — dimensionado de sección rectangular",
                    "Bloque rectangular de tensiones (3.1.7(3)) con comprobación final por el método "
                    "general parábola-rectángulo (3.1.7(1), 6.1)", inp)
    tr.inputs["diametro_supuesto_mm"] = inp.assumed_bar_diameter
    tr.assume("Dimensionado con el bloque rectangular: válido para sección rectangular de ancho "
              "constante en la zona comprimida, flexión simple y fibra neutra dentro de la sección.")
    tr.assume("En el dimensionado se exige que la armadura de tracción alcance f_yd "
              "(ε_s ≥ ε_yd), lo que limita además ξ ≤ ε_cu3/(ε_cu3 + ε_yd).")
    tr.assume("Se descuenta el hormigón desplazado por la armadura de compresión situada dentro "
              "del bloque comprimido.")
    tr.limit("La propuesta no incluye armadura de montaje ni de piel: si no se requiere armadura "
             "de compresión, las barras de montaje deben añadirse por criterios constructivos.")

    conc.trace_design_values(tr)
    tr.step("Coeficiente de profundidad del bloque", "Anejo 19, 3.1.7(3), expresiones (3.19)-(3.20)",
            "λ = 0,8 (f_ck ≤ 50);  λ = 0,8 − (f_ck − 50)/400", f"f_ck = {fmt(conc.fck)} MPa",
            conc.lam, "-", "λ")
    tr.step("Factor de resistencia efectiva", "Anejo 19, 3.1.7(3), expresiones (3.21)-(3.22)",
            "η = 1,0 (f_ck ≤ 50);  η = 1,0 − (f_ck − 50)/200", f"f_ck = {fmt(conc.fck)} MPa",
            conc.eta, "-", "η")
    tr.step("Deformación última del hormigón", "Anejo 19, tabla 3.1", "ε_cu3 (= ε_cu2)",
            f"f_ck = {fmt(conc.fck)} MPa", conc.eps_cu3 * 1000, "‰", "ε_cu3")
    steel.trace_design_values(tr)

    phi = inp.assumed_bar_diameter
    d0 = h - edge - phi / 2
    d2_0 = edge + phi / 2
    tr.step("Canto útil inicial (una capa del diámetro supuesto)", "Definición geométrica",
            "d = h − c_nom − φ_t − φ/2",
            f"d = {fmt(h)} − {fmt(inp.cover)} − {fmt(inp.stirrup_diameter)} − {fmt(phi)}/2", d0, "mm", "d")
    xi_lim = ductility_limit(conc, p, tr)
    xi_y = conc.eps_cu3 / (conc.eps_cu3 + steel.eps_yd)
    tr.step("Profundidad relativa para la cedencia de la armadura traccionada",
            "Compatibilidad de deformaciones (6.1)", "ξ_y = ε_cu3/(ε_cu3 + ε_yd)",
            f"ξ_y = {fmt(conc.eps_cu3*1000)}/({fmt(conc.eps_cu3*1000)} + {fmt(steel.eps_yd*1000)})",
            xi_y, "-", "ξ_y")

    bd = block_design(b, d0, d2_0, M, conc, steel, xi_lim)
    sc = conc.eta * conc.fcd
    tr.step("Momento reducido", "Equilibrio (bloque rectangular)", "μ = M_Ed/(b·d²·η·f_cd)",
            f"μ = {fmt(M/1e6)}·10⁶/({fmt(b)}·{fmt(d0, 1)}²·{fmt(sc)})", bd.mu, "-", "μ")
    tr.step("Momento límite sin armadura de compresión", "Equilibrio (bloque rectangular)",
            "M_lim = η·f_cd·b·λ·x_lim·(d − λ·x_lim/2);  x_lim = ξ_lim,ef·d",
            f"M_lim = {fmt(sc)}·{fmt(b)}·{fmt(conc.lam)}·{fmt(bd.x_lim, 1)}·({fmt(d0, 1)} − "
            f"{fmt(conc.lam)}·{fmt(bd.x_lim, 1)}/2)", nmm_to_knm(bd.M_lim), "kN·m", "M_lim")
    if not bd.feasible:
        tr.warn(bd.message)
        tr.check("Viabilidad del dimensionado", "—", f"M_Ed = {fmt(M/1e6)} kN·m", "—", False, bd.message)
        return {"mode": "design", "ok": False, "trace": tr.to_dict(), "materials": _mat_dict(conc, steel),
                "design": None, "proposal": None, "verification": None}
    if not bd.compression_needed:
        tr.step("Profundidad del bloque comprimido", "Equilibrio de momentos",
                "λ·x = d·(1 − √(1 − 2μ))", f"λ·x = {fmt(d0, 1)}·(1 − √(1 − 2·{fmt(bd.mu, 4)}))",
                conc.lam * bd.x, "mm", "λx")
        tr.step("Armadura de tracción necesaria", "Equilibrio de fuerzas",
                "A_s1 = η·f_cd·b·λ·x/f_yd",
                f"A_s1 = {fmt(sc)}·{fmt(b)}·{fmt(conc.lam*bd.x, 1)}/{fmt(steel.fyd)}", bd.As1, "mm²", "A_s1")
    else:
        tr.warn("M_Ed > M_lim: se requiere armadura de compresión con x = x_lim.")
        tr.step("Deformación de la armadura comprimida", "Compatibilidad de deformaciones",
                "ε_s2 = ε_cu3·(x_lim − d2)/x_lim",
                f"ε_s2 = {fmt(conc.eps_cu3*1000)}·({fmt(bd.x_lim, 1)} − {fmt(d2_0, 1)})/{fmt(bd.x_lim, 1)}",
                conc.eps_cu3 * (bd.x_lim - d2_0) / bd.x_lim * 1000, "‰", "ε_s2")
        tr.step("Tensión de la armadura comprimida", "Anejo 19, 3.2.7", "σ_s2 = min(E_s·ε_s2; f_yd)",
                "", bd.sigma_s2, "MPa", "σ_s2")
        tr.step("Armadura de compresión necesaria", "Equilibrio de momentos",
                "A_s2 = (M_Ed − M_lim)/((σ_s2 − η·f_cd)·(d − d2))",
                f"A_s2 = ({fmt(M/1e6)} − {fmt(bd.M_lim/1e6)})·10⁶/(({fmt(bd.sigma_s2)} − {fmt(sc)})·"
                f"({fmt(d0, 1)} − {fmt(d2_0, 1)}))", bd.As2, "mm²", "A_s2")
        tr.step("Armadura de tracción necesaria", "Equilibrio de fuerzas",
                "A_s1 = (η·f_cd·b·λ·x_lim + A_s2·(σ_s2 − η·f_cd))/f_yd", "", bd.As1, "mm²", "A_s1")

    Asmin = as_min(conc, steel, _bt(inp.shape, sign), d0, p, tr)
    Ac = inp.shape.area
    Asmax = as_max(Ac, p, tr)
    As1_req = max(bd.As1, Asmin)
    if Asmin > bd.As1:
        tr.warn("La armadura mínima (9.2.1.1) es determinante sobre la de cálculo.")

    # --- Propuesta de armado ---
    candidates = _propose(inp, conc, steel, M, sign, tface, cface, xi_lim, bd.compression_needed, Asmax)
    proposal = candidates[0] if candidates else None
    verification = None
    if proposal is None:
        tr.warn("No se encontró una disposición práctica de barras (máx. dos capas en la cara "
                "traccionada y una en la comprimida, diámetros configurados) que cumpla todas las "
                "condiciones (resistencia, ductilidad, cuantías y separaciones). Considere aumentar "
                "la sección o utilizar un método más general.")
        tr.check("Disposición de armaduras", "8.2, 9.2.1.1", f"A_s1,nec = {fmt(As1_req, 0)} mm²",
                 "sin solución práctica", False)
    else:
        sec, res, d_act, bd_act, Asmin_act = proposal
        tr.step("Canto útil con la disposición propuesta", "Definición geométrica",
                "d = profundidad del c.d.g. de la armadura traccionada",
                _layers_text([l for l in sec.layers if l.face == tface]), d_act, "mm", "d")
        _trace_verification(tr, res, conc, steel, inp.M_Ed_knm, xi_lim, label="disposición propuesta")
        A1 = sec.area_on(tface)
        A2 = sec.area_on(cface)
        if A2 > 0 and not bd.compression_needed:
            tr.warn("La disposición propuesta incluye armadura de compresión aunque el dimensionado "
                    "teórico no la requiere: con las barras comerciales disponibles, el exceso de "
                    "armadura de tracción situaría la fibra neutra por encima de ξ_lim.")
        tr.check("Armadura de tracción ≥ necesaria (bloque rectangular, d real)",
                 "Equilibrio 6.1 / 3.1.7(3)", f"A_s1,nec = {fmt(max(bd_act.As1, Asmin_act), 0)} mm²",
                 f"A_s1 = {fmt(A1, 0)} mm²", A1 >= max(bd_act.As1, Asmin_act) - 1e-6)
        if bd_act.compression_needed:
            tr.check("Armadura de compresión ≥ necesaria", "Equilibrio 6.1",
                     f"A_s2,nec = {fmt(bd_act.As2, 0)} mm²", f"A_s2 = {fmt(A2, 0)} mm²",
                     A2 >= bd_act.As2 - 1e-6)
        _common_checks(tr, sec, conc, steel, sign, tface, cface, Asmin_act, Asmax)
        verification = res.to_dict()
        proposal = {
            "layers": [l.__dict__ for l in sec.layers],
            "text_tension": _layers_text([l for l in sec.layers if l.face == tface]),
            "text_compression": _layers_text([l for l in sec.layers if l.face == cface]) or None,
            "As_tension": A1, "As_compression": A2, "d": d_act,
            "geometry": sec.geometric_properties(),
            "alternatives": [
                {"text_tension": _layers_text([l for l in c[0].layers if l.face == tface]),
                 "text_compression": _layers_text([l for l in c[0].layers if l.face == cface]) or None,
                 "As_tension": c[0].area_on(tface), "As_compression": c[0].area_on(cface),
                 "d": c[2], "M_Rd_kNm": abs(nmm_to_knm(c[1].M_Rd)), "xi": c[1].xi,
                 "layers": [l.__dict__ for l in c[0].layers]}
                for c in candidates[:6]
            ],
        }

    design = {
        "d": d0, "d2": d2_0, "mu": bd.mu, "xi_lim": xi_lim, "xi_y": xi_y, "x_lim": bd.x_lim,
        "M_lim_kNm": nmm_to_knm(bd.M_lim), "x": bd.x, "As1": bd.As1, "As2": bd.As2,
        "As_min": Asmin, "As_max": Asmax, "As1_req": As1_req,
        "compression_needed": bd.compression_needed, "tension_face": tface,
    }
    return {"mode": "design", "ok": tr.all_checks_ok, "trace": tr.to_dict(),
            "materials": _mat_dict(conc, steel), "design": design, "proposal": proposal,
            "verification": verification}


def _max_bars_per_layer(width: float, edge: float, phi: float, dg: float, params: ParameterSet) -> int:
    s = min_clear_spacing(phi, dg, params)
    return int(math.floor((width - 2 * edge + s) / (phi + s) + 1e-9))


def _propose(inp: FlexureInput, conc, steel, M, sign, tface, cface, xi_lim, comp_needed, Asmax):
    """Busca la disposición de menor área que verifica todas las condiciones.

    Cara traccionada: hasta dos capas de un mismo diámetro; cara comprimida (solo si se
    requiere armadura de compresión): una capa. Para cada combinación se recalcula d con
    la geometría real, se repite el dimensionado y se verifica por el método general.
    """
    p = inp.params
    b = inp.shape.b
    edge = inp.cover + inp.stirrup_diameter
    phis = p["bar_diameters"]

    def bottom_search(top: list[Layer]):
        found = []
        for phi in phis:
            n_max = _max_bars_per_layer(b, edge, phi, inp.dg, p)
            if n_max < 2:
                continue
            for n in range(2, 2 * n_max + 1):
                layers_b = [Layer(tface, n, phi)] if n <= n_max else \
                    [Layer(tface, n_max, phi), Layer(tface, max(2, n - n_max), phi)]
                cand = _evaluate_candidate(inp, conc, steel, M, sign, tface, cface, xi_lim,
                                           layers_b, top, Asmax)
                if cand is not None:
                    found.append(cand)
                    break  # el primer n válido es el mínimo para este diámetro
        return found

    def comp_tops() -> list[list[Layer]]:
        out = []
        for phi in phis:
            n_max = _max_bars_per_layer(b, edge, phi, inp.dg, p)
            out.extend([[Layer(cface, n, phi)] for n in range(2, n_max + 1)])
        return out

    found_all = []
    if not comp_needed:
        found_all = bottom_search([])
    if not found_all:
        for top in comp_tops():
            found_all.extend(bottom_search(top))

    def key(cand):
        sec = cand[0]
        return (len([l for l in sec.layers if l.face == tface]),
                round(sec.area_on(tface) + sec.area_on(cface), 6),
                sum(l.n for l in sec.layers))

    found_all.sort(key=key)
    # alternativas únicas por texto de armado
    seen, uniq = set(), []
    for c in found_all:
        t = (_layers_text([l for l in c[0].layers if l.face == tface]),
             _layers_text([l for l in c[0].layers if l.face == cface]))
        if t not in seen:
            seen.add(t)
            uniq.append(c)
    return uniq


def _evaluate_candidate(inp, conc, steel, M, sign, tface, cface, xi_lim, layers_b, layers_t, Asmax):
    try:
        sec = ReinforcedSection(inp.shape, inp.cover, inp.stirrup_diameter, layers_b + layers_t,
                                inp.dg, inp.params)
    except SectionError:
        return None
    if sec.issues:
        return None
    d = sec.centroid_depth(tface)
    d2 = sec.centroid_depth(cface)
    d2 = inp.shape.h - d2 if d2 is not None else inp.cover + inp.stirrup_diameter
    bd = block_design(inp.shape.b, d, d2, M, conc, steel, xi_lim)
    if not bd.feasible:
        return None
    Asmin = as_min(conc, steel, _bt(inp.shape, sign), d, inp.params)
    A1, A2 = sec.area_on(tface), sec.area_on(cface)
    if A1 < max(bd.As1, Asmin) - 1e-6 or A2 < bd.As2 - 1e-6:
        return None
    if A1 > Asmax or A2 > Asmax:
        return None
    try:
        res = analyse_bending(sec, conc, steel, sign, "parabola-rectangulo")
    except AnalysisError:
        return None
    if abs(res.M_Rd) < M * (1 - 1e-9) or res.xi > xi_lim + 1e-9:
        return None
    return sec, res, d, bd, Asmin


def _trace_verification(tr: CalcTrace, res: BendingResult, conc, steel, M_Ed_knm: float, xi_lim: float,
                        label: str) -> None:
    tr.step(f"Profundidad de la fibra neutra ({label}, método general)",
            "Anejo 19, 6.1 y 3.1.7(1): equilibrio ΣN = 0 resuelto numéricamente",
            "ΣN(x) = ∫σ_c(ε(y))·b(y)·dy − Σ A_si·σ_si = 0", f"residuo = {fmt(res.residual_N/1e3, 6)} kN",
            res.x, "mm", "x")
    tr.step("Deformación en la fibra más comprimida", "Anejo 19, 6.1(5)-(6), figura 6.1",
            "ε_c = ε_cu2 (pivote B) o fijada por ε_ud (pivote A)", f"pivote {res.pivot}",
            res.eps_top * 1000, "‰", "ε_c")
    tr.step("Resultante de compresiones del hormigón", "Integración del diagrama parábola-rectángulo",
            "F_c = ∫σ_c·b(y)·dy", "", res.Fc / 1e3, "kN", "F_c")
    for i, bs in enumerate(res.bars, 1):
        tr.step(f"Barra {i} (φ{fmt(bs.diameter)}, {bs.face})", "Compatibilidad + diagrama 3.2.7",
                "ε_s = ε_c·(y − x)/x;  σ_s = f(ε_s)",
                f"y = {fmt(bs.y, 1)} mm; ε_s = {fmt(bs.strain*1000, 3)} ‰",
                bs.stress, "MPa", "σ_s")
    tr.step("Momento resistente último", "Equilibrio de momentos (6.1)",
            "M_Rd = −Σ F_i·y_i (respecto a la fibra comprimida)", "", nmm_to_knm(res.M_Rd), "kN·m", "M_Rd")
    tr.check("Resistencia a flexión", "Anejo 19, 6.1; 2.4 (E_d ≤ R_d)",
             f"|M_Ed| = {fmt(abs(M_Ed_knm))} kN·m", f"|M_Rd| = {fmt(abs(nmm_to_knm(res.M_Rd)))} kN·m",
             abs(nmm_to_knm(res.M_Rd)) >= abs(M_Ed_knm) * (1 - 1e-9))
    tr.check("Criterio de ductilidad x/d ≤ ξ_lim", "Anejo 19, 5.5(4) (criterio adoptado)",
             f"x/d = {fmt(res.xi, 3)}", f"ξ_lim = {fmt(xi_lim, 3)}", res.xi <= xi_lim + 1e-9)
    tbars = [b for b in res.bars if b.force > 0]
    yielded = all(b.yielded for b in tbars if b.y >= max(bb.y for bb in tbars) - 1e-6) if tbars else False
    tr.check("Cedencia de la armadura más traccionada", "Compatibilidad (6.1)",
             f"ε_s,max = {fmt(max(b.strain for b in res.bars)*1000)} ‰", f"ε_yd = {fmt(steel.eps_yd*1000)} ‰",
             yielded, "Si no plastifica, la rotura sería frágil (sin aviso).")


def _common_checks(tr, sec: ReinforcedSection, conc, steel, sign, tface, cface, Asmin, Asmax):
    A1, A2 = sec.area_on(tface), sec.area_on(cface)
    tr.check("Armadura mínima de tracción", "Anejo 19, 9.2.1.1(1)", f"A_s,min = {fmt(Asmin, 0)} mm²",
             f"A_s = {fmt(A1, 0)} mm²", A1 >= Asmin - 1e-6)
    tr.check("Armadura máxima de tracción", "Anejo 19, 9.2.1.1(3)", f"A_s = {fmt(A1, 0)} mm²",
             f"A_s,max = {fmt(Asmax, 0)} mm²", A1 <= Asmax + 1e-6)
    if A2 > 0:
        tr.check("Armadura máxima de compresión", "Anejo 19, 9.2.1.1(3)", f"A_s2 = {fmt(A2, 0)} mm²",
                 f"A_s,max = {fmt(Asmax, 0)} mm²", A2 <= Asmax + 1e-6)
    tr.check("Separación libre entre barras", "Anejo 19, 8.2(2)",
             "s ≥ s_min" if not sec.issues else "; ".join(sec.issues), "s_min según 8.2(2)", not sec.issues)
    if isinstance(sec.shape, TShape) and sign < 0:
        tr.warn("Momento negativo en sección en T: el ala está traccionada; se ha tomado b_t = b_f "
                "para la armadura mínima. La distribución de la armadura en el ala (9.2.1.2(2)) "
                "no se comprueba.")


def _mat_dict(conc: Concrete, steel: ReinforcingSteel) -> dict:
    return {"concrete": conc.properties(), "steel": steel.properties()}


def check_flexure(inp: FlexureInput) -> dict:
    """Comprobación de una sección con armadura existente (método general)."""
    inp.validate()
    if not inp.layers:
        raise FlexureInputError("Defina al menos una capa de armadura para la comprobación")
    p = inp.params
    conc, steel = _materials(inp)
    sign = 1 if inp.M_Ed_knm >= 0 else -1
    tface = "inferior" if sign > 0 else "superior"
    cface = "superior" if sign > 0 else "inferior"
    sec = ReinforcedSection(inp.shape, inp.cover, inp.stirrup_diameter, inp.layers, inp.dg, p)

    tr = _new_trace("Flexión simple ELU — comprobación de armadura existente",
                    "Método general: compatibilidad de deformaciones y equilibrio con diagrama "
                    "parábola-rectángulo (3.1.7(1), 6.1); comparación con bloque rectangular (3.1.7(3))", inp)
    tr.inputs["capas"] = [l.__dict__ for l in inp.layers]
    tr.assume("Se descuenta el hormigón desplazado por las barras situadas en la zona comprimida.")
    conc.trace_design_values(tr)
    tr.step("Exponente de la parábola", "Anejo 19, tabla 3.1", "n", f"f_ck = {fmt(conc.fck)}", conc.n, "-", "n")
    tr.step("Deformación de inicio de la rama horizontal", "Anejo 19, tabla 3.1", "ε_c2", "",
            conc.eps_c2 * 1000, "‰", "ε_c2")
    tr.step("Deformación última", "Anejo 19, tabla 3.1", "ε_cu2", "", conc.eps_cu2 * 1000, "‰", "ε_cu2")
    steel.trace_design_values(tr)
    sec.trace_geometry(tr)

    d = sec.centroid_depth(tface)
    if d is None:
        tr.check("Existencia de armadura de tracción", "6.1", f"cara {tface}", "sin barras", False)
        tr.warn("No hay armadura en la cara traccionada.")
        return {"mode": "check", "ok": False, "trace": tr.to_dict(), "materials": _mat_dict(conc, steel),
                "geometry": sec.geometric_properties(), "verification": None, "comparison": None}
    tr.step("Canto útil", "Definición geométrica", "d = profundidad del c.d.g. de la armadura traccionada",
            _layers_text([l for l in inp.layers if l.face == tface]), d, "mm", "d")
    xi_lim = ductility_limit(conc, p, tr)
    res = analyse_bending(sec, conc, steel, sign, "parabola-rectangulo")
    _trace_verification(tr, res, conc, steel, inp.M_Ed_knm if inp.M_Ed_knm != 0 else 0.0, xi_lim,
                        label="armadura existente")
    comparison = None
    try:
        rb = analyse_bending(sec, conc, steel, sign, "rectangular")
        comparison = rb.to_dict()
        tr.step("Momento resistente con bloque rectangular (contraste)", "Anejo 19, 3.1.7(3)",
                "Equilibrio con η·f_cd sobre λ·x", f"x = {fmt(rb.x, 1)} mm", nmm_to_knm(rb.M_Rd), "kN·m",
                "M_Rd,rect", note="Valor informativo; la comprobación usa el parábola-rectángulo.")
        if rb.eta_reduction:
            tr.warn("Se ha aplicado la reducción del 10 % de η·f_cd (nota de 3.1.7(3)) al disminuir "
                    "el ancho comprimido hacia la fibra extrema.")
    except AnalysisError as exc:
        tr.warn(f"Bloque rectangular no aplicable: {exc}")
    Asmin = as_min(conc, steel, _bt(inp.shape, sign), d, p, tr)
    Asmax = as_max(inp.shape.area, p, tr)
    _common_checks(tr, sec, conc, steel, sign, tface, cface, Asmin, Asmax)
    if res.xi > xi_lim:
        tr.warn("La fibra neutra supera el límite de ductilidad adoptado: conviene disponer armadura "
                "de compresión o aumentar la sección.")
    return {"mode": "check", "ok": tr.all_checks_ok, "trace": tr.to_dict(),
            "materials": _mat_dict(conc, steel), "geometry": sec.geometric_properties(),
            "verification": res.to_dict(), "comparison": comparison}
