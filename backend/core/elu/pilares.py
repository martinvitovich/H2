"""Pilares aislados de sección rectangular en flexión compuesta recta (Anejo 19).

Procedimiento implementado:

1. Longitud efectiva l_0: β·l (figura A19.5.7) o expresiones (5.15)/(5.16) a partir de k1, k2.
2. Esbeltez λ = l_0/i (5.14) y esbeltez límite λ_lim (5.13); si λ ≤ λ_lim se desprecian los
   efectos de segundo orden (5.8.3.1).
3. Imperfecciones geométricas e_i = θ_i·l_0/2 (5.1)-(5.2) o e_i = l_0/400 (5.2(9)).
4. Momento de primer orden equivalente M_0e (5.32) en elementos arriostrados sin cargas
   transversales.
5. Efectos de segundo orden por el método de la curvatura nominal (5.8.8): (5.31)-(5.37).
6. Excentricidad mínima e_0 = h/30 ≥ 20 mm (6.1(4)).
7. Resistencia de la sección por el diagrama de interacción N–M del método general (6.1).
8. Disposiciones de pilares (9.5).

Fuera de alcance: flexión esviada (5.8.9; se debe comprobar cada dirección por separado),
método de la rigidez nominal (5.8.7) y método general (5.8.6), efectos globales (5.8.3.3),
secciones no rectangulares, pilares circulares, zunchado.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..materials import Concrete, ReinforcingSteel
from ..parameters import ParameterSet
from ..section import Layer, RectangularShape, ReinforcedSection
from ..trace import CalcTrace, fmt
from ..units import kn_to_n, knm_to_nmm, n_to_kn, nmm_to_knm
from .nm import NMError, NMSection, interaction_diagram

VALIDATION_STATUS = (
    "Implementado. Ecuaciones y parámetros cotejados con el texto oficial del Anejo 19 "
    "(BOE-A-2021-13681, apartados 5.2, 5.8, 6.1 y 9.5). Validación matemática interna superada. "
    "PENDIENTE: contraste con ejemplos resueltos de bibliografía independiente."
)


class ColumnInputError(ValueError):
    pass


@dataclass
class ColumnInput:
    b: float
    h: float                       # dimensión en la dirección de la flexión estudiada
    cover: float
    stirrup_diameter: float
    layers: list[Layer]
    N_Ed_kn: float                 # compresión positiva
    M01_knm: float                 # momentos de primer orden en extremos (mismo signo: tracciones del mismo lado)
    M02_knm: float
    length: float                  # longitud libre l (mm)
    braced: bool = True
    l0_mode: str = "beta"          # "beta" | "k"
    beta: float | None = 1.0
    k1: float | None = None
    k2: float | None = None
    transverse_load: bool = False
    M0_span_knm: float | None = None
    phi_ef: float | None = None
    phi_inf: float | None = None
    m0eqp_ratio: float | None = None
    ei_simplified: bool = False
    stirrup_spacing: float | None = None
    intermediate_bars_tied: bool = False
    concrete_class: str = "C25/30"
    steel_grade: str = "B500S"
    steel_branch: str = "horizontal"
    situation: str = "persistente"
    dg: float = 20.0
    params: ParameterSet = field(default_factory=ParameterSet)
    element_name: str = "Pilar"

    def validate(self) -> None:
        for name in ("N_Ed_kn", "M01_knm", "M02_knm", "length"):
            if not math.isfinite(getattr(self, name)):
                raise ColumnInputError(f"{name} no es un número finito")
        if self.N_Ed_kn <= 0:
            raise ColumnInputError("El módulo de pilares requiere un axil de compresión N_Ed > 0")
        if self.length <= 0:
            raise ColumnInputError("La longitud del pilar debe ser positiva")
        if self.l0_mode not in ("beta", "k"):
            raise ColumnInputError("Modo de longitud efectiva no válido ('beta' o 'k')")
        if self.l0_mode == "beta" and (self.beta is None or self.beta <= 0):
            raise ColumnInputError("Indique el coeficiente β de longitud efectiva (l_0 = β·l)")
        if self.l0_mode == "k" and (self.k1 is None or self.k2 is None or self.k1 < 0 or self.k2 < 0):
            raise ColumnInputError("Indique las flexibilidades relativas k1 y k2 (≥ 0) de los extremos")
        if self.transverse_load and self.M0_span_knm is None:
            raise ColumnInputError("Con cargas transversales hay que indicar el momento máximo de primer orden en el vano")
        if self.phi_ef is not None and self.phi_ef < 0:
            raise ColumnInputError("φ_ef no puede ser negativo")
        if self.ei_simplified and not self.braced:
            raise ColumnInputError("La simplificación e_i = l_0/400 solo es aplicable a pilares en sistemas arriostrados (5.2(9))")
        if self.stirrup_spacing is not None and self.stirrup_spacing <= 0:
            raise ColumnInputError("La separación de cercos debe ser positiva")


def _l0(inp: ColumnInput, tr: CalcTrace) -> float:
    l = inp.length
    if inp.l0_mode == "beta":
        l0 = inp.beta * l
        tr.step("Longitud efectiva", "Anejo 19, 5.8.3.2(2), figura A19.5.7 (BOE pág. 98341)",
                "l_0 = β·l", f"l_0 = {fmt(inp.beta)}·{fmt(l)}", l0, "mm", "l_0")
        tr.assume(f"Longitud efectiva l_0 = {fmt(inp.beta)}·l según las condiciones de apoyo indicadas por el usuario "
                  "(figura A19.5.7).")
        return l0
    k1, k2 = inp.k1, inp.k2
    kmin = tr.use_param(inp.params, "k_restraint_min")
    if min(k1, k2) < kmin:
        tr.warn(f"k1 o k2 < {fmt(kmin)}: el Anejo recomienda un valor mínimo de 0,1 porque la coacción "
                "completa es difícil de conseguir (5.8.3.2(3), nota).")
    if inp.braced:
        l0 = 0.5 * l * math.sqrt((1 + k1 / (0.45 + k1)) * (1 + k2 / (0.45 + k2)))
        tr.step("Longitud efectiva (elemento arriostrado)", "Anejo 19, 5.8.3.2(3), expresión (5.15) (BOE pág. 98341)",
                "l_0 = 0,5·l·√[(1 + k1/(0,45 + k1))·(1 + k2/(0,45 + k2))]",
                f"k1 = {fmt(k1)}; k2 = {fmt(k2)}; l = {fmt(l)}", l0, "mm", "l_0")
    else:
        a = math.sqrt(1 + 10 * k1 * k2 / (k1 + k2)) if (k1 + k2) > 0 else 1.0
        bb = (1 + k1 / (1 + k1)) * (1 + k2 / (1 + k2))
        l0 = l * max(a, bb)
        tr.step("Longitud efectiva (elemento no arriostrado)", "Anejo 19, 5.8.3.2(3), expresión (5.16) (BOE pág. 98341)",
                "l_0 = l·max{√(1 + 10·k1·k2/(k1 + k2)); (1 + k1/(1 + k1))·(1 + k2/(1 + k2))}",
                f"k1 = {fmt(k1)}; k2 = {fmt(k2)}; l = {fmt(l)}", l0, "mm", "l_0")
    return l0


def column_check(inp: ColumnInput) -> dict:
    inp.validate()
    p = inp.params
    conc = Concrete.from_class(inp.concrete_class, p, inp.situation)
    steel = ReinforcingSteel.from_grade(inp.steel_grade, p, inp.situation, inp.steel_branch)  # type: ignore[arg-type]
    hb_lim = p["col_h_b_max"]
    if max(inp.b, inp.h) > hb_lim * min(inp.b, inp.h):
        raise ColumnInputError(f"La mayor dimensión supera {fmt(hb_lim)} veces la menor: el elemento no es un pilar "
                               "según 9.5.1(1) (véase 9.6, muros; fuera de alcance)")
    shape = RectangularShape(inp.b, inp.h)
    sec = ReinforcedSection(shape, inp.cover, inp.stirrup_diameter, inp.layers, inp.dg, p)
    N = kn_to_n(inp.N_Ed_kn)
    b, h, Ac = inp.b, inp.h, shape.area

    tr = CalcTrace("Pilar aislado — flexión compuesta recta y efectos de segundo orden",
                   "Esbeltez límite (5.8.3.1), imperfecciones (5.2), curvatura nominal (5.8.8) y "
                   "diagrama de interacción N–M por el método general (6.1)", VALIDATION_STATUS)
    tr.units = {"longitudes": "mm", "áreas": "mm²", "tensiones": "MPa", "axiles": "kN (compresión +)",
                "momentos": "kN·m", "curvaturas": "1/mm"}
    tr.inputs = {
        "elemento": inp.element_name, "b_mm": b, "h_mm (dirección de la flexión)": h, "recubrimiento_mm": inp.cover,
        "capas": [l.__dict__ for l in inp.layers], "hormigon": inp.concrete_class, "acero": inp.steel_grade,
        "N_Ed_kN": inp.N_Ed_kn, "M01_kNm": inp.M01_knm, "M02_kNm": inp.M02_knm, "longitud_mm": inp.length,
        "arriostrado": inp.braced, "modo_l0": inp.l0_mode, "beta": inp.beta, "k1": inp.k1, "k2": inp.k2,
        "cargas_transversales": inp.transverse_load, "M0_vano_kNm": inp.M0_span_knm, "phi_ef": inp.phi_ef,
        "phi_inf": inp.phi_inf, "M0Eqp/M0Ed": inp.m0eqp_ratio, "e_i_simplificada": inp.ei_simplified,
        "separacion_cercos_mm": inp.stirrup_spacing, "barras_intermedias_atadas": inp.intermediate_bars_tied,
    }
    tr.assume("Pilar aislado de sección rectangular constante y armadura constante en toda su longitud.")
    tr.assume("Flexión recta en el plano de la dimensión h; N_Ed constante en el pilar.")
    tr.assume("Los momentos de primer orden M01, M02 y N_Ed proceden del análisis estructural (no se combinan acciones).")
    tr.assume("Convenio de signos: M01 y M02 tienen el mismo signo si traccionan la misma cara (5.8.3.1, 5.8.8.2(2)).")
    tr.limit("Flexión esviada (5.8.9): debe comprobarse cada dirección principal por separado.")
    tr.limit("No se aplican el método general (5.8.6) ni el de rigidez nominal (5.8.7), ni los efectos globales "
             "de segundo orden de la estructura (5.8.3.3).")
    tr.limit("No se comprueban el cortante del pilar, los solapes (s_cl ≤ 0,6·s_cl,max y A_s ≤ 0,08·A_c en ellos) "
             "ni las zonas junto a vigas o losas (9.5.3(4)).")

    tr.use_param(p, "col_h_b_max")

    conc.trace_design_values(tr)
    steel.trace_design_values(tr)
    props = sec.geometric_properties()
    As = props["As_total"]
    omega = As * steel.fyd / (Ac * conc.fcd)
    n_red = N / (Ac * conc.fcd)
    tr.step("Cuantía mecánica", "Anejo 19, 5.8.3.1(1)", "ω = A_s·f_yd/(A_c·f_cd)",
            f"{fmt(As, 1)}·{fmt(steel.fyd)}/({fmt(Ac, 0)}·{fmt(conc.fcd)})", omega, "-", "ω")
    tr.step("Axil reducido", "Anejo 19, 5.8.3.1(1)", "n = N_Ed/(A_c·f_cd)",
            f"{fmt(inp.N_Ed_kn)}·10³/({fmt(Ac, 0)}·{fmt(conc.fcd)})", n_red, "-", "n")

    # --- signo y momentos de primer orden ---
    m01, m02 = inp.M01_knm, inp.M02_knm
    if abs(m01) > abs(m02):
        m01, m02 = m02, m01
        tr.warn("Se han intercambiado M01 y M02 para que |M02| ≥ |M01|.")
    sgn = 1 if m02 >= 0 else -1
    M02 = abs(knm_to_nmm(m02))
    M01r = knm_to_nmm(m01) * sgn          # positivo si tracciona la misma cara que M02

    # --- longitud efectiva y esbeltez ---
    l0 = _l0(inp, tr)
    i_g = math.sqrt(shape.inertia / Ac)
    lam = l0 / i_g
    tr.step("Radio de giro de la sección bruta", "Anejo 19, 5.8.3.2(1)", "i = √(I_c/A_c)",
            f"√({fmt(shape.inertia, 0)}/{fmt(Ac, 0)})", i_g, "mm", "i")
    tr.step("Esbeltez", "Anejo 19, 5.8.3.2(1), expresión (5.14) (BOE pág. 98341)", "λ = l_0/i",
            f"{fmt(l0, 1)}/{fmt(i_g, 2)}", lam, "-", "λ")

    # --- fluencia ---
    phi_ef = inp.phi_ef
    if phi_ef is None and inp.phi_inf is not None and inp.m0eqp_ratio is not None:
        phi_ef = inp.phi_inf * inp.m0eqp_ratio
        tr.step("Coeficiente de fluencia eficaz", "Anejo 19, 5.8.4(2), expresión (5.19) (BOE pág. 98343)",
                "φ_ef = φ(∞,t_0)·M_0Eqp/M_0Ed", f"{fmt(inp.phi_inf)}·{fmt(inp.m0eqp_ratio)}", phi_ef, "-", "φ_ef")
    elif phi_ef is not None:
        tr.step("Coeficiente de fluencia eficaz (dato)", "Anejo 19, 5.8.4", "φ_ef", "", phi_ef, "-", "φ_ef")

    # --- esbeltez límite ---
    tr.use_param(p, "lambda_lim_coef")
    A_ = 1.0 / (1.0 + 0.2 * phi_ef) if phi_ef is not None else 0.7
    B_ = math.sqrt(1.0 + 2.0 * omega)
    if inp.braced and not inp.transverse_load:
        rm = M01r / M02 if M02 > 0 else 1.0
        rm_txt = f"r_m = M01/M02 = {fmt(rm, 4)}"
    else:
        rm = 1.0
        rm_txt = "r_m = 1,0 (elemento no arriostrado o con cargas transversales, 5.8.3.1(1))"
    C_ = 1.7 - rm
    lam_lim = p["lambda_lim_coef"] * A_ * B_ * C_ / math.sqrt(n_red)
    tr.step("Coeficientes de la esbeltez límite", "Anejo 19, 5.8.3.1(1) (BOE pág. 98340)",
            "A = 1/(1 + 0,2·φ_ef) (0,7 si φ_ef no se conoce); B = √(1 + 2ω); C = 1,7 − r_m",
            f"A = {fmt(A_, 4)}; B = {fmt(B_, 4)}; {rm_txt}; C = {fmt(C_, 4)}", None, "",
            note="El texto oficial imprime B = 1 + √(1 + 2ω); se adopta B = √(1 + 2ω), coherente con el valor "
                 "por defecto B = 1,1 del mismo apartado (errata documentada en docs/normativa.md).")
    tr.step("Esbeltez límite", "Anejo 19, 5.8.3.1(1), expresión (5.13)", "λ_lim = 20·A·B·C/√n",
            f"20·{fmt(A_, 4)}·{fmt(B_, 4)}·{fmt(C_, 4)}/√{fmt(n_red, 4)}", lam_lim, "-", "λ_lim")
    second_order = lam > lam_lim

    # --- imperfecciones ---
    if inp.ei_simplified:
        div = tr.use_param(p, "ei_simplified_div")
        ei = l0 / div
        tr.step("Excentricidad por imperfecciones (simplificada)", "Anejo 19, 5.2(7) a) y 5.2(9) (BOE pág. 98331)",
                "e_i = l_0/400", f"{fmt(l0, 1)}/{fmt(div)}", ei, "mm", "e_i")
    else:
        th0 = tr.use_param(p, "theta0")
        l_m = inp.length / 1000.0
        ah = min(max(2.0 / math.sqrt(l_m), 2.0 / 3.0), 1.0)
        am = math.sqrt(0.5 * (1 + 1 / 1))
        thi = th0 * ah * am
        ei = thi * l0 / 2
        tr.step("Inclinación por imperfecciones", "Anejo 19, 5.2(5)-(6), expresión (5.1) (BOE pág. 98330)",
                "θ_i = θ_0·α_h·α_m; α_h = 2/√l (2/3 ≤ α_h ≤ 1); α_m = √(0,5·(1 + 1/m)), m = 1",
                f"θ_0 = 1/200; α_h = {fmt(ah, 4)}; α_m = {fmt(am, 4)}", thi, "rad", "θ_i")
        tr.step("Excentricidad por imperfecciones", "Anejo 19, 5.2(7) a), expresión (5.2)",
                "e_i = θ_i·l_0/2", f"{fmt(thi, 6)}·{fmt(l0, 1)}/2", ei, "mm", "e_i")

    # --- excentricidad mínima ---
    e0 = max(h / tr.use_param(p, "e0_h_div"), tr.use_param(p, "e0_min"))
    tr.step("Excentricidad mínima", "Anejo 19, 6.1(4) (BOE pág. 98357)", "e_0 = h/30 ≥ 20 mm",
            f"max({fmt(h)}/30; 20)", e0, "mm", "e_0")
    Mmin = N * e0

    # --- momento de primer orden en la sección crítica ---
    if inp.braced and not inp.transverse_load:
        M0e = max(0.6 * M02 + 0.4 * M01r, 0.4 * M02)
        tr.step("Momento de primer orden equivalente", "Anejo 19, 5.8.8.2(2), expresión (5.32) (BOE pág. 98347)",
                "M_0e = 0,6·M02 + 0,4·M01 ≥ 0,4·M02",
                f"0,6·{fmt(nmm_to_knm(M02))} + 0,4·{fmt(nmm_to_knm(M01r))}", nmm_to_knm(M0e), "kN·m", "M_0e")
        crit_label = "sección intermedia"
    elif inp.transverse_load:
        M0e = abs(knm_to_nmm(inp.M0_span_knm))
        tr.step("Momento de primer orden máximo en el vano (dato)", "Anejo 19, 5.8.8.2(1)", "M_0,vano", "",
                nmm_to_knm(M0e), "kN·m", "M_0")
        crit_label = "sección de momento máximo en el vano"
    else:
        M0e = M02
        crit_label = "extremo de máximo momento (no arriostrado)"
        tr.assume("Elemento no arriostrado: la sección crítica de segundo orden es el extremo con M02.")
    M0Ed = M0e + N * ei
    tr.step("Momento de primer orden con imperfecciones", "Anejo 19, 5.8.8.2(1); 5.2(7)",
            "M_0Ed = M_0 + N_Ed·e_i", f"{fmt(nmm_to_knm(M0e))} + {fmt(inp.N_Ed_kn)}·{fmt(ei, 2)}·10⁻³",
            nmm_to_knm(M0Ed), "kN·m", "M_0Ed")

    # --- segundo orden: curvatura nominal ---
    M2 = 0.0
    second_ok: bool | None = True
    if not second_order:
        tr.step("Efectos de segundo orden", "Anejo 19, 5.8.3.1(1)", "λ ≤ λ_lim ⇒ pueden despreciarse",
                f"λ = {fmt(lam, 2)} ≤ λ_lim = {fmt(lam_lim, 2)}", 0.0, "kN·m", "M_2")
    else:
        sym = _symmetric(inp.layers)
        if not sym:
            second_ok = None
            tr.warn("El método de la curvatura nominal (5.8.8.3(1)) exige sección simétrica incluida la armadura: "
                    "con armadura asimétrica no puede evaluarse el segundo orden con este método.")
        if phi_ef is None:
            second_ok = None
            tr.warn("Falta el coeficiente de fluencia eficaz φ_ef (5.8.4), necesario para K_φ (5.37): indique φ_ef "
                    "o φ(∞,t_0) y M_0Eqp/M_0Ed.")
        if second_ok:
            lat = [bb for bb in sec.bars if bb.face == "lateral"]
            if lat:
                ys = [bb.y for bb in sec.bars]
                As_all = [bb.area for bb in sec.bars]
                yc = sum(a * y for a, y in zip(As_all, ys)) / sum(As_all)
                i_s = math.sqrt(sum(a * (y - yc) ** 2 for a, y in zip(As_all, ys)) / sum(As_all))
                d = h / 2 + i_s
                tr.step("Canto útil con armadura distribuida", "Anejo 19, 5.8.8.3(2), expresión (5.35) (BOE pág. 98348)",
                        "d = h/2 + i_s", f"{fmt(h)}/2 + {fmt(i_s, 2)}", d, "mm", "d")
            else:
                d = sec.centroid_depth("inferior")
                tr.step("Canto útil", "Anejo 19, 5.8.8.3(1)", "d", "armadura en caras opuestas", d, "mm", "d")
            inv_r0 = steel.eps_yd / (0.45 * d)
            nu = 1 + omega
            nbal = tr.use_param(p, "n_bal")
            Kr = min((nu - n_red) / (nu - nbal), 1.0)
            beta = 0.35 + conc.fck / 200 - lam / 150
            Kphi = max(1 + beta * phi_ef, 1.0)
            inv_r = Kr * Kphi * inv_r0
            constant = (not inp.transverse_load) and abs(M01r - M02) < 1e-9 * max(M02, 1)
            c = 8.0 if constant else tr.use_param(p, "curvature_c")
            e2 = inv_r * l0 ** 2 / c
            M2 = N * e2
            tr.step("Curvatura de referencia", "Anejo 19, 5.8.8.3(1), (5.34) (BOE pág. 98348)",
                    "1/r_0 = ε_yd/(0,45·d)", f"{fmt(steel.eps_yd * 1000, 4)}·10⁻³/(0,45·{fmt(d, 1)})",
                    inv_r0, "1/mm", "1/r_0")
            tr.step("Corrección por axil", "Anejo 19, 5.8.8.3(3), (5.36)", "K_r = (n_u − n)/(n_u − n_bal) ≤ 1; n_u = 1 + ω",
                    f"({fmt(nu, 4)} − {fmt(n_red, 4)})/({fmt(nu, 4)} − {fmt(nbal)})", Kr, "-", "K_r")
            tr.step("Corrección por fluencia", "Anejo 19, 5.8.8.3(4), (5.37)",
                    "K_φ = 1 + β·φ_ef ≥ 1; β = 0,35 + f_ck/200 − λ/150",
                    f"β = {fmt(beta, 4)}; φ_ef = {fmt(phi_ef, 3)}", Kphi, "-", "K_φ")
            tr.step("Curvatura", "Anejo 19, 5.8.8.3(1), (5.34)", "1/r = K_r·K_φ·1/r_0", "", inv_r, "1/mm", "1/r")
            tr.step("Flecha de segundo orden", "Anejo 19, 5.8.8.2(3)-(4), (5.33)", "e_2 = (1/r)·l_0²/c",
                    f"c = {fmt(c)}{' (momento de primer orden constante)' if constant else ''}", e2, "mm", "e_2")
            tr.step("Momento nominal de segundo orden", "Anejo 19, 5.8.8.2(3), (5.33)", "M_2 = N_Ed·e_2",
                    f"{fmt(inp.N_Ed_kn)}·{fmt(e2, 2)}·10⁻³", nmm_to_knm(M2), "kN·m", "M_2")

    MEd_crit = max(M0Ed + M2, Mmin)
    tr.step(f"Momento de cálculo en la {crit_label}", "Anejo 19, 5.8.8.2(1), (5.31); 6.1(4)",
            "M_Ed = max(M_0Ed + M_2; N_Ed·e_0)",
            f"max({fmt(nmm_to_knm(M0Ed))} + {fmt(nmm_to_knm(M2))}; {fmt(nmm_to_knm(Mmin))})",
            nmm_to_knm(MEd_crit), "kN·m", "M_Ed")
    M_end = max(M02, Mmin)
    if inp.braced:
        tr.step("Momento de cálculo en el extremo", "Anejo 19, 5.8.7.3(3) nota; 6.1(4)",
                "M_Ed,ext = max(|M02|; N_Ed·e_0)", "", nmm_to_knm(M_end), "kN·m", "M_Ed,ext")

    # --- resistencia de la sección (N–M) ---
    S = NMSection(sec, conc, steel, sgn)
    n_min, n_max = S.N_range()
    tr.step("Axil resistente máximo (compresión centrada)", "Anejo 19, 6.1(3), pivote C (figura A19.6.1)",
            "N_Rd,max = ∫σ_c dA + Σ A_s·σ_s(ε_c2)", "", n_to_kn(n_max), "kN", "N_Rd,max")
    result: dict = {"l0": l0, "i": i_g, "lambda": lam, "lambda_lim": lam_lim, "second_order": second_order,
                    "omega": omega, "n": n_red, "phi_ef": phi_ef, "e_i": ei, "e_0": e0, "M0e": M0e, "M0Ed": M0Ed,
                    "M2": M2, "MEd_crit": MEd_crit, "MEd_end": M_end, "N_Rd_max": n_max, "N_Rd_min": n_min,
                    "sign": sgn, "geometry": props}
    tr.check("Axil de compresión", "Anejo 19, 6.1", f"N_Ed = {fmt(inp.N_Ed_kn)} kN",
             f"N_Rd,max = {fmt(n_to_kn(n_max))} kN", N <= n_max * (1 + 1e-9))
    if N <= n_max:
        pt = S.resistance_at(N)
        MRd = abs(pt.M)
        result["MRd"] = MRd
        result["MRd_domain"] = pt.domain
        tr.step("Momento resistente con el axil de cálculo", "Anejo 19, 6.1: equilibrio N(plano) = N_Ed",
                "M_Rd(N_Ed) sobre la envolvente N–M", f"dominio {pt.domain}; ε_sup = {fmt(pt.eps_top * 1000, 3)} ‰, "
                f"ε_inf = {fmt(pt.eps_bot * 1000, 3)} ‰", nmm_to_knm(MRd), "kN·m", "M_Rd")
        ok_crit = (MEd_crit <= MRd * (1 + 1e-9)) if second_ok else None
        tr.check(f"Flexocompresión en la {crit_label}", "Anejo 19, 6.1; 5.8.8",
                 f"M_Ed = {fmt(nmm_to_knm(MEd_crit))} kN·m", f"M_Rd = {fmt(nmm_to_knm(MRd))} kN·m", ok_crit,
                 "" if second_ok else "No evaluable: faltan datos para el segundo orden (ver advertencias).")
        if inp.braced:
            tr.check("Flexocompresión en el extremo", "Anejo 19, 6.1; 6.1(4)",
                     f"M_Ed,ext = {fmt(nmm_to_knm(M_end))} kN·m", f"M_Rd = {fmt(nmm_to_knm(MRd))} kN·m",
                     M_end <= MRd * (1 + 1e-9))

    _detailing(inp, tr, sec, steel, N, Ac, result)
    for msg in sec.issues:
        tr.warn(msg)
    diagram = interaction_diagram(sec, conc, steel)
    result["diagram"] = [{"N_kN": n_to_kn(q["N"]), "M_kNm": nmm_to_knm(q["M"]), "domain": q["domain"]}
                         for q in diagram]
    result["design_points"] = [
        {"label": "Sección crítica", "N_kN": inp.N_Ed_kn, "M_kNm": sgn * nmm_to_knm(MEd_crit)},
    ] + ([{"label": "Extremo", "N_kN": inp.N_Ed_kn, "M_kNm": sgn * nmm_to_knm(M_end)}] if inp.braced else [])
    return {"ok": tr.all_checks_ok, "trace": tr.to_dict(), "result": result,
            "materials": {"concrete": conc.properties(), "steel": steel.properties()}}


def _symmetric(layers: list[Layer]) -> bool:
    top = sorted((l.n, l.diameter, l.depth) for l in layers if l.face == "superior")
    bot = sorted((l.n, l.diameter, l.depth) for l in layers if l.face == "inferior")
    return top == bot and bool(top)


def _detailing(inp: ColumnInput, tr: CalcTrace, sec: ReinforcedSection, steel: ReinforcingSteel, N: float,
               Ac: float, result: dict) -> None:
    p = inp.params
    phis = [b.diameter for b in sec.bars]
    phmin = tr.use_param(p, "col_phi_long_min")
    tr.check("Diámetro mínimo de las barras longitudinales", "Anejo 19, 9.5.2(1)",
             f"φ_min = {fmt(min(phis))} mm", f"{fmt(phmin)} mm", min(phis) >= phmin - 1e-9)
    fycd = min(steel.fyd, tr.use_param(p, "col_fycd_max"))
    k = tr.use_param(p, "col_As_face_min_coef")
    As_face_min = k * N / fycd
    tr.step("Armadura mínima por cara", "Anejo 19, 9.5.2(2) (BOE pág. 98434)",
            "A′_s,min = 0,05·N_Ed/f_yc,d; f_yc,d = f_yd ≯ 400 MPa",
            f"0,05·{fmt(n_to_kn(N))}·10³/{fmt(fycd)}", As_face_min, "mm²", "A′_s,min")
    for face in ("superior", "inferior"):
        A = sec.area_on(face)
        tr.check(f"Armadura mínima en la cara {face}", "Anejo 19, 9.5.2(2)", f"A′_s = {fmt(A, 0)} mm²",
                 f"A′_s,min = {fmt(As_face_min, 0)} mm²", A >= As_face_min - 1e-6)
    As = sum(b.area for b in sec.bars)
    Asmax = tr.use_param(p, "As_max_coef") * Ac
    tr.check("Armadura longitudinal máxima", "Anejo 19, 9.5.2(3)", f"A_s = {fmt(As, 0)} mm²",
             f"A_s,max = 0,04·A_c = {fmt(Asmax, 0)} mm²", As <= Asmax + 1e-6)
    corner_bars = []
    for face in ("superior", "inferior"):
        fb = [b for b in sec.bars if b.face == face and b.layer == 1]
        if len(fb) >= 2:
            corner_bars += [min(fb, key=lambda b: b.x), max(fb, key=lambda b: b.x)]
    has_corners = len(corner_bars) == 4
    tr.check("Barra en cada esquina", "Anejo 19, 9.5.2(4)", f"{len(corner_bars)} barras de esquina", "4 (1 por esquina)",
             has_corners)
    # armadura transversal
    phmax = max(phis)
    phit_min = max(6.0, phmax / 4)
    tr.check("Diámetro de la armadura transversal", "Anejo 19, 9.5.3(1)", f"φ_t = {fmt(inp.stirrup_diameter)} mm",
             f"max(6; φ_max/4) = {fmt(phit_min)} mm", inp.stirrup_diameter >= phit_min - 1e-9)
    s_max = min(tr.use_param(p, "col_s_cl_phi") * min(phis), tr.use_param(p, "col_s_cl_abs"), inp.b, inp.h)
    red = tr.use_param(p, "col_s_cl_reduction")
    tr.step("Separación máxima de la armadura transversal", "Anejo 19, 9.5.3(3) (BOE pág. 98434)",
            "s_cl,max = min(15·φ_min; 300 mm; min(b, h))",
            f"min(15·{fmt(min(phis))}; 300; {fmt(min(inp.b, inp.h))})", s_max, "mm", "s_cl,max",
            note=f"Junto a vigas o losas (longitud ≥ mayor dimensión del pilar) y en solapes con φ > 14 mm: "
                 f"{fmt(red)}·s_cl,max = {fmt(red * s_max)} mm (9.5.3(4)).")
    result["s_cl_max"] = s_max
    if inp.stirrup_spacing is None:
        tr.check("Separación de la armadura transversal", "Anejo 19, 9.5.3(3)", "no indicada",
                 f"s_cl,max = {fmt(s_max)} mm", None, "Indique la separación de cercos.")
    else:
        tr.check("Separación de la armadura transversal", "Anejo 19, 9.5.3(3)", f"s = {fmt(inp.stirrup_spacing)} mm",
                 f"s_cl,max = {fmt(s_max)} mm", inp.stirrup_spacing <= s_max + 1e-9)
    # 9.5.3(6): barras a más de 150 mm de una barra sujeta (se consideran sujetas las de esquina)
    dist = tr.use_param(p, "col_tie_distance")
    corner_pts = [(b.x, b.y) for b in corner_bars] or [(b.x, b.y) for b in sec.bars]
    far = [b for b in sec.bars if min(math.hypot(b.x - x, b.y - y) for x, y in corner_pts) > dist + 1e-9]
    if not far:
        tr.check("Sujeción de las barras comprimidas", "Anejo 19, 9.5.3(6)", "todas a ≤ 150 mm de una barra de esquina",
                 f"{fmt(dist)} mm", True)
    else:
        tr.check("Sujeción de las barras comprimidas", "Anejo 19, 9.5.3(6)",
                 f"{len(far)} barra(s) a más de {fmt(dist)} mm de una barra de esquina",
                 "sujetas con horquillas o cercos interiores" if inp.intermediate_bars_tied else "deben sujetarse",
                 inp.intermediate_bars_tied,
                 "Se ha indicado que las barras intermedias están sujetas por armadura transversal."
                 if inp.intermediate_bars_tied else "Disponga horquillas o cercos interiores e indíquelo.")
