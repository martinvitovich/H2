"""Cortante en ELU de vigas de hormigón armado (Anejo 19, 6.2 y 9.2.2).

Alcance implementado:

* Resistencia sin armadura de cortante V_Rd,c, expresiones (6.2.a), (6.2.b) y (6.3).
* Modelo de celosía con armadura de cortante de cercos (α entre 45° y 90°):
  V_Rd,s (6.8)/(6.13) y V_Rd,max (6.9)/(6.14), con 0,5 ≤ cot θ ≤ 2 (6.7) y α_cw = 1
  (estructuras sin pretensado).
* Dimensionado: se adopta el mayor cot θ admisible que cumple V_Ed ≤ V_Rd,max, lo que
  minimiza la armadura de cortante. Comprobación: θ que maximiza
  V_Rd = min(V_Rd,s; V_Rd,max) dentro del intervalo (6.7), o el θ fijado por el usuario.
* Cuantía mínima (9.5), separaciones máximas longitudinal (9.6) y transversal (9.8),
  tracción adicional en la armadura longitudinal ΔF_td (6.18).

Fuera de alcance (se declara como limitación): pretensado, cordones inclinados (V_ccd, V_td),
barras levantadas, reducción β por cargas próximas a los apoyos (6.2.2(6), 6.2.3(8)),
rasante ala-alma (6.2.4), juntas (6.2.5), torsión (6.3) e interacción con ella, secciones
no fisuradas (6.4), vainas (6.2.3(6)).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..materials import Concrete, ReinforcingSteel
from ..parameters import ParameterSet
from ..section import Layer, ReinforcedSection, Shape, min_clear_spacing
from ..trace import CalcTrace, fmt
from ..units import kn_to_n, n_to_kn

VALIDATION_STATUS = (
    "Implementado. Ecuaciones y parámetros cotejados con el texto oficial del Anejo 19 "
    "(BOE-A-2021-13681, apartados 6.2 y 9.2.2). Validación matemática interna superada. "
    "PENDIENTE: contraste con ejemplos resueltos de bibliografía independiente."
)

REF_62A = "Anejo 19, 6.2.2(1), expresión (6.2.a) (BOE págs. 98359-98360)"
REF_62B = "Anejo 19, 6.2.2(1), expresiones (6.2.b) y (6.3) (BOE págs. 98359-98360)"


class ShearInputError(ValueError):
    pass


@dataclass
class ShearInput:
    shape: Shape
    cover: float
    stirrup_diameter: float
    layers: list[Layer]
    V_Ed_kn: float
    tension_face: str = "inferior"
    N_Ed_kn: float = 0.0                 # compresión positiva
    concrete_class: str = "C25/30"
    stirrup_grade: str = "B500S"
    situation: str = "persistente"
    dg: float = 20.0
    stirrup_legs: int = 2
    alpha_deg: float = 90.0
    stirrup_spacing: float | None = None  # obligatoria en comprobación
    mode: str = "design"
    cot_theta: float | None = None        # None: elección automática
    nu1_simplified: bool = False          # (6.10) con f_ywd = 0,8·f_ywk
    params: ParameterSet = field(default_factory=ParameterSet)
    element_name: str = "Viga"

    def validate(self) -> None:
        if not math.isfinite(self.V_Ed_kn) or self.V_Ed_kn < 0:
            raise ShearInputError("V_Ed debe ser un valor finito y no negativo (valor absoluto del cortante)")
        if not math.isfinite(self.N_Ed_kn):
            raise ShearInputError("N_Ed no es un número finito")
        if self.tension_face not in ("inferior", "superior"):
            raise ShearInputError("La cara traccionada debe ser 'inferior' o 'superior'")
        if not (45.0 <= self.alpha_deg <= 90.0):
            raise ShearInputError("La armadura de cortante debe formar un ángulo α entre 45° y 90° "
                                  "con el eje del elemento (9.2.2(1))")
        if self.stirrup_diameter <= 0:
            raise ShearInputError("Indique el diámetro de los cercos")
        if not (2 <= self.stirrup_legs <= 8):
            raise ShearInputError("El número de ramas de los cercos debe estar entre 2 y 8")
        if self.mode not in ("design", "check"):
            raise ShearInputError("Modo no válido (design / check)")
        if self.mode == "check" and (self.stirrup_spacing is None or self.stirrup_spacing <= 0):
            raise ShearInputError("En la comprobación hay que indicar la separación de los cercos")
        p = self.params
        if self.cot_theta is not None and not (p["cot_theta_min"] - 1e-12 <= self.cot_theta <= p["cot_theta_max"] + 1e-12):
            raise ShearInputError(f"cot θ debe cumplir {p['cot_theta_min']} ≤ cot θ ≤ {p['cot_theta_max']} (6.7)")


# ----------------------------------------------------------------------------
# Funciones de cálculo (unidades internas N, mm, MPa)
# ----------------------------------------------------------------------------

def vrdc(conc: Concrete, bw: float, d: float, Asl: float, N: float, Ac: float, params: ParameterSet,
         tr: CalcTrace | None = None) -> dict:
    """Resistencia a cortante sin armadura de cortante, (6.2.a)-(6.2.b)."""
    k = min(1.0 + math.sqrt(200.0 / d), 2.0)
    rho_raw = Asl / (bw * d)
    rho = min(rho_raw, params["rho_l_max"])
    sig_raw = N / Ac
    sig_lim = params["sigma_cp_max_factor"] * conc.fcd
    sig = min(sig_raw, sig_lim)
    crdc = params["CRdc_num"] / conc.gamma_c
    k1 = params["k1_shear"]
    vmin = params["vmin_coef"] * k ** 1.5 * math.sqrt(conc.fck)
    va = (crdc * k * (100.0 * rho * conc.fck) ** (1.0 / 3.0) + k1 * sig) * bw * d
    vb = (vmin + k1 * sig) * bw * d
    V = max(va, vb, 0.0)
    if tr:
        for key in ("CRdc_num", "k1_shear", "vmin_coef", "rho_l_max", "sigma_cp_max_factor"):
            tr.use_param(params, key)
        tr.step("Factor de tamaño", REF_62A, "k = 1 + √(200/d) ≤ 2,0",
                f"k = 1 + √(200/{fmt(d, 1)})", k, "-", "k")
        tr.step("Cuantía de armadura longitudinal de tracción", REF_62A, "ρ_l = A_sl/(b_w·d) ≤ 0,02",
                f"ρ_l = {fmt(Asl, 1)}/({fmt(bw)}·{fmt(d, 1)}) = {fmt(rho_raw, 5)}", rho, "-", "ρ_l")
        tr.step("Tensión media de compresión por axil", REF_62A, "σ_cp = N_Ed/A_c < 0,2·f_cd",
                f"σ_cp = {fmt(N / 1e3)}·10³/{fmt(Ac, 0)}; límite {fmt(sig_lim)} MPa", sig, "MPa", "σ_cp")
        tr.step("Coeficiente C_Rd,c", REF_62A, "C_Rd,c = 0,18/γ_c", f"C_Rd,c = {fmt(params['CRdc_num'])}/{fmt(conc.gamma_c)}",
                crdc, "-", "C_Rd,c")
        tr.step("Resistencia a cortante (6.2.a)", REF_62A,
                "V_Rd,c = [C_Rd,c·k·(100·ρ_l·f_ck)^(1/3) + k_1·σ_cp]·b_w·d",
                f"V_Rd,c = [{fmt(crdc, 4)}·{fmt(k, 4)}·(100·{fmt(rho, 5)}·{fmt(conc.fck)})^(1/3) + "
                f"{fmt(k1)}·{fmt(sig, 4)}]·{fmt(bw)}·{fmt(d, 1)}", n_to_kn(va), "kN", "V_Rd,c(a)")
        tr.step("Valor mínimo v_min", REF_62B, "v_min = 0,035·k^(3/2)·f_ck^(1/2)",
                f"v_min = {fmt(params['vmin_coef'])}·{fmt(k, 4)}^1,5·{fmt(conc.fck)}^0,5", vmin, "MPa", "v_min")
        tr.step("Resistencia mínima (6.2.b)", REF_62B, "V_Rd,c,min = (v_min + k_1·σ_cp)·b_w·d",
                f"({fmt(vmin, 4)} + {fmt(k1)}·{fmt(sig, 4)})·{fmt(bw)}·{fmt(d, 1)}", n_to_kn(vb), "kN", "V_Rd,c(b)")
        tr.step("Resistencia a cortante sin armadura de cortante", REF_62A,
                "V_Rd,c = max(6.2.a; 6.2.b)", "", n_to_kn(V), "kN", "V_Rd,c")
        if sig_raw > sig_lim:
            tr.warn("σ_cp = N_Ed/A_c supera 0,2·f_cd: se ha limitado a 0,2·f_cd en (6.2.a/b).")
        if rho_raw > rho:
            tr.warn("ρ_l supera 0,02: se ha limitado a 0,02 en (6.2.a).")
    return {"k": k, "rho_l": rho, "rho_l_raw": rho_raw, "sigma_cp": sig, "CRdc": crdc, "vmin": vmin,
            "VRdc_a": va, "VRdc_b": vb, "VRdc": V}


def nu1_and_fywd(conc: Concrete, stir: ReinforcingSteel, simplified: bool) -> tuple[float, float, str]:
    if not simplified:
        return 0.6 * (1.0 - conc.fck / 250.0), stir.fyd, "ν_1 = 0,6·(1 − f_ck/250)"
    nu = 0.6 if conc.fck <= 60 else max(0.9 - conc.fck / 200.0, 0.5)
    return nu, 0.8 * stir.fyk, "ν_1 = 0,6 (f_ck ≤ 60) o 0,9 − f_ck/200 > 0,5 (6.10); f_ywd = 0,8·f_ywk"


def vrd_max(cot_t: float, cot_a: float, bw: float, z: float, nu1: float, fcd: float, acw: float) -> float:
    """(6.14); para α = 90° coincide con (6.9): (cot θ + cot α)/(1 + cot²θ) = 1/(cot θ + tan θ)."""
    return acw * bw * z * nu1 * fcd * (cot_t + cot_a) / (1.0 + cot_t ** 2)


def vrd_s(asw_s: float, cot_t: float, cot_a: float, sin_a: float, z: float, fywd: float) -> float:
    """(6.13); para α = 90° coincide con (6.8)."""
    return asw_s * z * fywd * (cot_t + cot_a) * sin_a


def cot_theta_max_vrdmax(cot_a: float, cmin: float, cmax: float) -> float:
    """cot θ que maximiza V_Rd,max en [cmin, cmax]: c* = −cot α + √(cot²α + 1)."""
    c = -cot_a + math.sqrt(cot_a ** 2 + 1.0)
    return min(max(c, cmin), cmax)


# ----------------------------------------------------------------------------
# Procedimiento principal
# ----------------------------------------------------------------------------

def shear_beam(inp: ShearInput) -> dict:
    inp.validate()
    p = inp.params
    conc = Concrete.from_class(inp.concrete_class, p, inp.situation)
    stir = ReinforcingSteel.from_grade(inp.stirrup_grade, p, inp.situation)
    sec = ReinforcedSection(inp.shape, inp.cover, inp.stirrup_diameter, inp.layers, inp.dg, p)
    tface = inp.tension_face
    d = sec.centroid_depth(tface)
    if d is None:
        raise ShearInputError(f"No hay armadura longitudinal en la cara traccionada ({tface}): "
                              "se requiere para el modelo de celosía y para V_Rd,c")
    Asl = sec.area_on(tface)
    bw = inp.shape.web_width
    Ac = inp.shape.area
    V = kn_to_n(inp.V_Ed_kn)
    N = kn_to_n(inp.N_Ed_kn)

    tr = CalcTrace("Cortante ELU — " + ("dimensionado de cercos" if inp.mode == "design" else
                                       "comprobación de cercos existentes"),
                   "Resistencia sin armadura de cortante (6.2.2) y modelo de celosía con ángulo de "
                   "bielas variable (6.2.3)", VALIDATION_STATUS)
    tr.units = {"longitudes": "mm", "áreas": "mm²", "tensiones": "MPa (N/mm²)", "esfuerzos": "kN",
                "cuantías por unidad de longitud": "mm²/m"}
    tr.inputs = {
        "elemento": inp.element_name, "seccion": inp.shape.to_dict(), "recubrimiento_nominal_mm": inp.cover,
        "cara_traccionada": tface, "capas": [l.__dict__ for l in inp.layers],
        "hormigon": inp.concrete_class, "acero_cercos": inp.stirrup_grade, "situacion_proyecto": inp.situation,
        "V_Ed_kN": inp.V_Ed_kn, "N_Ed_kN (compresión +)": inp.N_Ed_kn,
        "diametro_cerco_mm": inp.stirrup_diameter, "ramas": inp.stirrup_legs, "alfa_grados": inp.alpha_deg,
        "separacion_cercos_mm": inp.stirrup_spacing, "cot_theta": inp.cot_theta if inp.cot_theta else "automático",
        "nu1_simplificado_6_10": inp.nu1_simplified,
    }
    tr.assume("V_Ed es el cortante de cálculo en la sección analizada (valor absoluto), resultado del "
              "análisis estructural; el programa no combina acciones.")
    tr.assume("La armadura longitudinal de tracción A_sl se prolonga una longitud ≥ l_bd + d más allá de "
              "la sección considerada (figura A19.6.3); el usuario debe garantizarlo.")
    tr.assume("Elemento de hormigón armado sin pretensado: α_cw = 1 (6.2.3(3)).")
    tr.assume("Canto constante y cordones paralelos: V_ccd = V_td = 0 en (6.1).")
    tr.assume("Armadura de cortante formada exclusivamente por cercos, por lo que se cumple que al menos el "
              "50 % (β_3 = 0,5) de la armadura necesaria sea de cercos (9.2.2(4)).")
    tr.limit("No se aplica la reducción β = a_v/2d por cargas próximas a los apoyos (6.2.2(6), 6.2.3(8)) "
             "ni la simplificación de 6.2.1(8) para cargas uniformes: V_Ed se toma tal como se introduce.")
    tr.limit("No se comprueban el rasante ala-alma (6.2.4), las juntas (6.2.5), la torsión (6.3) ni el "
             "decalaje de la ley de momentos (9.2.1.3).")
    tr.limit("Se requiere armadura mínima de cortante (6.2.1(4)); el programa no aplica las excepciones "
             "(losas con redistribución transversal o elementos de importancia menor).")

    conc.trace_design_values(tr)
    stir.trace_design_values(tr)
    tr.step("Ancho mínimo del alma", "Anejo 19, 6.2.2(1) y figura A19.6.5", "b_w", inp.shape.kind, bw, "mm", "b_w")
    tr.step("Canto útil", "Definición geométrica", "d = profundidad del c.d.g. de la armadura traccionada",
            f"cara {tface}", d, "mm", "d")

    # --- V_Rd,c ---
    rc = vrdc(conc, bw, d, Asl, N, Ac, p, tr)

    # --- parámetros de la celosía ---
    zf = tr.use_param(p, "z_shear_factor")
    z = zf * d
    tr.step("Brazo mecánico", "Anejo 19, 6.2.3(1) (BOE pág. 98362)", "z = 0,9·d",
            f"z = {fmt(zf)}·{fmt(d, 1)}", z, "mm", "z")
    if inp.N_Ed_kn != 0:
        tr.warn("El Anejo indica z = 0,9·d como valor habitual para hormigón armado SIN esfuerzo axil; con "
                "N_Ed ≠ 0 conviene obtener z del análisis de flexión compuesta.")
    acw = tr.use_param(p, "alpha_cw")
    nu1, fywd, nu_txt = nu1_and_fywd(conc, stir, inp.nu1_simplified)
    tr.step("Coeficiente de reducción del hormigón fisurado", "Anejo 19, 6.2.3(3), (6.6)/(6.10) (BOE pág. 98363)",
            nu_txt, f"f_ck = {fmt(conc.fck)}", nu1, "-", "ν_1")
    if inp.nu1_simplified:
        tr.assume("Se usa ν_1 según (6.10): la tensión de cálculo de la armadura de cortante se limita a "
                  "0,8·f_ywk en (6.8) (nota de 6.2.3(3)).")
        tr.step("Límite elástico de cálculo de la armadura de cortante", "Anejo 19, 6.2.3(3), nota",
                "f_ywd = 0,8·f_ywk", f"0,8·{fmt(stir.fyk)}", fywd, "MPa", "f_ywd")
    else:
        tr.step("Límite elástico de cálculo de la armadura de cortante", "Anejo 19, 6.2.3(3); 3.2.7",
                "f_ywd = f_ywk/γ_s", f"{fmt(stir.fyk)}/{fmt(stir.gamma_s)}", fywd, "MPa", "f_ywd")
    alpha = math.radians(inp.alpha_deg)
    cot_a = 0.0 if inp.alpha_deg == 90 else 1.0 / math.tan(alpha)
    sin_a = math.sin(alpha)
    cmin, cmax = tr.use_param(p, "cot_theta_min"), tr.use_param(p, "cot_theta_max")
    ref_vmax = "Anejo 19, 6.2.3(3), expresión (6.9)" if inp.alpha_deg == 90 else "Anejo 19, 6.2.3(4), expresión (6.14)"
    ref_vs = "Anejo 19, 6.2.3(3), expresión (6.8)" if inp.alpha_deg == 90 else "Anejo 19, 6.2.3(4), expresión (6.13)"
    eq_vmax = ("V_Rd,max = α_cw·b_w·z·ν_1·f_cd/(cot θ + tan θ)" if inp.alpha_deg == 90 else
               "V_Rd,max = α_cw·b_w·z·ν_1·f_cd·(cot θ + cot α)/(1 + cot²θ)")
    eq_vs = ("V_Rd,s = (A_sw/s)·z·f_ywd·cot θ" if inp.alpha_deg == 90 else
             "V_Rd,s = (A_sw/s)·z·f_ywd·(cot θ + cot α)·sen α")
    K = acw * bw * z * nu1 * conc.fcd
    c_star = cot_theta_max_vrdmax(cot_a, cmin, cmax)
    vmax_peak = vrd_max(c_star, cot_a, bw, z, nu1, conc.fcd, acw)

    # --- armaduras mínimas y separaciones (9.2.2) ---
    rwmin = tr.use_param(p, "rho_w_min_coef") * math.sqrt(conc.fck) / stir.fyk
    tr.step("Cuantía mínima de armadura de cortante", "Anejo 19, 9.2.2(5), expresión (9.5) (BOE pág. 98428)",
            "ρ_w,min = 0,08·√f_ck/f_yk", f"0,08·√{fmt(conc.fck)}/{fmt(stir.fyk)}", rwmin * 1000, "‰", "ρ_w,min")
    asw_s_min = rwmin * bw * sin_a
    tr.step("Armadura mínima por unidad de longitud", "Anejo 19, 9.2.2(5), expresión (9.4)",
            "(A_sw/s)_min = ρ_w,min·b_w·sen α", f"{fmt(rwmin, 6)}·{fmt(bw)}·{fmt(sin_a, 4)}",
            asw_s_min * 1000, "mm²/m", "(A_sw/s)_min")
    slmax = tr.use_param(p, "s_l_max_coef") * d * (1.0 + cot_a)
    tr.step("Separación longitudinal máxima", "Anejo 19, 9.2.2(6), expresión (9.6)",
            "s_l,max = 0,75·d·(1 + cot α)", f"0,75·{fmt(d, 1)}·(1 + {fmt(cot_a, 4)})", slmax, "mm", "s_l,max")
    stmax = min(tr.use_param(p, "s_t_max_coef") * d, tr.use_param(p, "s_t_max_abs"))
    tr.step("Separación transversal máxima entre ramas", "Anejo 19, 9.2.2(8), expresión (9.8)",
            "s_t,max = 0,75·d ≤ 600 mm", f"min(0,75·{fmt(d, 1)}; 600)", stmax, "mm", "s_t,max")
    st_legs = (bw - 2 * inp.cover - inp.stirrup_diameter) / (inp.stirrup_legs - 1)
    asw = inp.stirrup_legs * math.pi * inp.stirrup_diameter ** 2 / 4.0
    tr.step("Área de una serie de cercos", "Geometría", "A_sw = n_ramas·π·φ_t²/4",
            f"{inp.stirrup_legs}·π·{fmt(inp.stirrup_diameter)}²/4", asw, "mm²", "A_sw")

    needs_calc = V > rc["VRdc"]
    result: dict = {"VRdc": rc, "z": z, "nu1": nu1, "fywd": fywd, "cot_alpha": cot_a, "rho_w_min": rwmin,
                    "s_l_max": slmax, "s_t_max": stmax, "s_t_legs": st_legs, "Asw": asw,
                    "needs_shear_reinforcement": needs_calc, "VRd_max_peak": vmax_peak}
    tr.step("Necesidad de armadura de cortante de cálculo", "Anejo 19, 6.2.1(3) y (5) (BOE pág. 98359)",
            "V_Ed ≤ V_Rd,c ⇒ solo armadura mínima (6.2.1(4)); V_Ed > V_Rd,c ⇒ armadura de cálculo",
            f"V_Ed = {fmt(inp.V_Ed_kn)} kN {'>' if needs_calc else '≤'} V_Rd,c = {fmt(n_to_kn(rc['VRdc']))} kN",
            None, "", note="Se requiere armadura de cortante de cálculo." if needs_calc else
            "No se requiere armadura de cortante de cálculo; se dispone la mínima.")
    if inp.mode == "design":
        _design(inp, tr, result, V, K, cot_a, sin_a, z, fywd, cmin, cmax, c_star, vmax_peak, asw, asw_s_min,
                slmax, needs_calc, ref_vmax, ref_vs, eq_vmax, eq_vs, bw, nu1, conc)
    else:
        _check(inp, tr, result, V, K, cot_a, sin_a, z, fywd, cmin, cmax, c_star, asw, asw_s_min, slmax,
               needs_calc, ref_vmax, ref_vs, eq_vmax, eq_vs, bw, nu1, conc, rc)

    tr.check("Separación transversal entre ramas de los cercos", "Anejo 19, 9.2.2(8), expresión (9.8)",
             f"s_t = {fmt(st_legs, 1)} mm ({inp.stirrup_legs} ramas)", f"s_t,max = {fmt(stmax, 1)} mm",
             st_legs <= stmax + 1e-9)
    cot_t = result.get("cot_theta")
    if cot_t is not None:
        dF = 0.5 * V * (cot_t - cot_a)
        result["Delta_Ftd"] = dF
        tr.step("Tracción adicional en la armadura longitudinal por cortante",
                "Anejo 19, 6.2.3(7), expresión (6.18) (BOE pág. 98364)",
                "ΔF_td = 0,5·V_Ed·(cot θ − cot α)", f"0,5·{fmt(inp.V_Ed_kn)}·({fmt(cot_t, 4)} − {fmt(cot_a, 4)})",
                n_to_kn(dF), "kN", "ΔF_td",
                note="La armadura longitudinal debe resistir M_Ed/z + ΔF_td ≤ M_Ed,max/z (no comprobado aquí).")
    for msg in sec.issues:
        tr.warn(msg)
    result["geometry"] = sec.geometric_properties()
    return {"mode": inp.mode, "ok": tr.all_checks_ok, "trace": tr.to_dict(), "result": result,
            "materials": {"concrete": conc.properties(), "stirrups": stir.properties()}}


def _design(inp, tr, result, V, K, cot_a, sin_a, z, fywd, cmin, cmax, c_star, vmax_peak, asw, asw_s_min,
            slmax, needs_calc, ref_vmax, ref_vs, eq_vmax, eq_vs, bw, nu1, conc):
    p = inp.params
    if inp.cot_theta is not None:
        cot_t = inp.cot_theta
        tr.step("Inclinación de las bielas (fijada por el usuario)", "Anejo 19, 6.2.3(2), expresión (6.7)",
                "0,5 ≤ cot θ ≤ 2", "", cot_t, "-", "cot θ")
    elif not needs_calc:
        cot_t = c_star
        tr.step("Inclinación de las bielas para la comprobación de V_Rd,max", "Anejo 19, 6.2.3(2), (6.7)",
                "cot θ que maximiza V_Rd,max: −cot α + √(cot²α + 1), limitado a [0,5; 2]", "", cot_t, "-", "cot θ")
    else:
        vmax_at_cmax = vrd_max(cmax, cot_a, bw, z, nu1, conc.fcd, 1.0) * p["alpha_cw"]
        if vmax_at_cmax >= V:
            cot_t = cmax
            sub = f"V_Rd,max(cot θ = {fmt(cmax)}) = {fmt(n_to_kn(vmax_at_cmax))} kN ≥ V_Ed"
        elif vmax_peak >= V:
            # mayor raíz de V·(1 + c²) = K·(c + cot α)
            disc = K * K - 4 * V * (V - K * cot_a)
            cot_t = (K + math.sqrt(disc)) / (2 * V)
            cot_t = min(max(cot_t, c_star), cmax)
            sub = f"V_Ed·(1 + c²) = K·(c + cot α), K = α_cw·b_w·z·ν_1·f_cd = {fmt(n_to_kn(K))} kN"
        else:
            cot_t = c_star
            sub = "V_Ed supera el máximo de V_Rd,max en el intervalo (6.7)"
        tr.step("Inclinación de las bielas adoptada", "Anejo 19, 6.2.3(2), expresión (6.7)",
                "mayor cot θ ∈ [0,5; 2] con V_Ed ≤ V_Rd,max (minimiza A_sw)", sub, cot_t, "-", "cot θ")
    result["cot_theta"] = cot_t
    result["theta_deg"] = math.degrees(math.atan(1.0 / cot_t))
    vmax = vrd_max(cot_t, cot_a, bw, z, nu1, conc.fcd, p["alpha_cw"])
    result["VRd_max"] = vmax
    tr.step("Resistencia de las bielas comprimidas", ref_vmax, eq_vmax,
            f"{fmt(p['alpha_cw'])}·{fmt(bw)}·{fmt(z, 1)}·{fmt(nu1, 4)}·{fmt(conc.fcd, 3)}, cot θ = {fmt(cot_t, 4)}",
            n_to_kn(vmax), "kN", "V_Rd,max")
    tr.check("Compresión oblicua en el alma (bielas)", "Anejo 19, 6.2.1(6); " + ref_vmax.split(", ", 1)[1],
             f"V_Ed = {fmt(n_to_kn(V))} kN", f"V_Rd,max = {fmt(n_to_kn(vmax))} kN", V <= vmax * (1 + 1e-9),
             "" if V <= vmax * (1 + 1e-9) else "Hay que aumentar la sección o la resistencia del hormigón.")
    if V > vmax * (1 + 1e-9):
        tr.warn("V_Ed supera la resistencia de las bielas comprimidas: no puede resolverse con armadura de "
                "cortante. Aumente b_w, el canto o la clase de hormigón.")
        result["proposal"] = None
        result["alternatives"] = []
        return
    if needs_calc:
        req = V / (z * fywd * (cot_t + cot_a) * sin_a)
        tr.step("Armadura de cortante necesaria", ref_vs, eq_vs.replace("V_Rd,s =", "V_Ed =") + " ⇒ A_sw/s",
                f"A_sw/s = {fmt(n_to_kn(V))}·10³/({fmt(z, 1)}·{fmt(fywd, 3)}·({fmt(cot_t, 4)} + {fmt(cot_a, 4)})·{fmt(sin_a, 4)})",
                req * 1000, "mm²/m", "(A_sw/s)_nec")
    else:
        req = 0.0
    need = max(req, asw_s_min)
    if asw_s_min >= req:
        tr.warn("La cuantía mínima de cortante (9.5) es determinante.")
    result["Asw_s_req"] = req
    result["Asw_s_design"] = need
    step = tr.use_param(p, "stirrup_spacing_step")

    def spacing_for(phi: float, legs: int) -> float:
        """Separación redondeada; 0 si no respeta la separación libre mínima de 8.2(2)."""
        a = legs * math.pi * phi ** 2 / 4.0
        s = math.floor(min(a / need, slmax) / step + 1e-9) * step
        return s if s - phi >= min_clear_spacing(phi, inp.dg, p) - 1e-9 else 0.0

    s_prop = spacing_for(inp.stirrup_diameter, inp.stirrup_legs)
    alternatives = []
    for phi in (6, 8, 10, 12):
        for legs in (2, 4):
            st = (bw - 2 * inp.cover - phi) / (legs - 1)
            if legs > 2 and st < 2 * phi:
                continue
            sp = spacing_for(phi, legs)
            if sp >= step:
                alternatives.append({"diameter": phi, "legs": legs, "spacing": sp,
                                     "Asw_s_mm2_m": legs * math.pi * phi ** 2 / 4 / sp * 1000,
                                     "s_t": st})
    result["proposal"] = {"diameter": inp.stirrup_diameter, "legs": inp.stirrup_legs, "spacing": s_prop}
    result["alternatives"] = alternatives
    if s_prop < step:
        tr.warn(f"Con cercos φ{fmt(inp.stirrup_diameter)} de {inp.stirrup_legs} ramas la separación necesaria "
                "no respeta la separación libre mínima entre barras (8.2(2)): aumente el diámetro o el "
                "número de ramas (ver alternativas).")
        tr.check("Disposición práctica de cercos", "9.2.2", f"(A_sw/s) = {fmt(need * 1000)} mm²/m",
                 "sin separación práctica", False)
        return
    asw_s_prov = asw / s_prop
    result["Asw_s_provided"] = asw_s_prov
    tr.step("Separación propuesta (redondeada hacia abajo)", "Criterio del programa; 9.2.2(6)",
            "s = min(A_sw/(A_sw/s)_nec; s_l,max)", f"A_sw = {fmt(asw, 1)} mm²", s_prop, "mm", "s")
    _provided_checks(inp, tr, result, V, asw_s_prov, s_prop, cot_t, cot_a, sin_a, z, fywd, slmax, bw, nu1, conc,
                     needs_calc, ref_vs, eq_vs)


def _check(inp, tr, result, V, K, cot_a, sin_a, z, fywd, cmin, cmax, c_star, asw, asw_s_min, slmax,
           needs_calc, ref_vmax, ref_vs, eq_vmax, eq_vs, bw, nu1, conc, rc):
    p = inp.params
    s = inp.stirrup_spacing
    asw_s = asw / s
    A = asw_s * z * fywd * sin_a  # V_Rd,s = A·(c + cot α)
    if inp.cot_theta is not None:
        cot_t = inp.cot_theta
        how = "fijado por el usuario"
    else:
        # máx de min(V_Rd,s, V_Rd,max): intersección 1 + c² = K/(A) si cae en [c*, cmax]
        if not needs_calc:
            cot_t, how = c_star, "máximo de V_Rd,max (no se requiere armadura de cálculo)"
        else:
            ratio = K / A if A > 0 else math.inf
            c_int = math.sqrt(ratio - 1.0) if ratio > 1.0 else -1.0
            if c_int >= cmax:
                cot_t, how = cmax, "límite superior de (6.7): V_Rd,s ≤ V_Rd,max"
            elif c_int <= c_star:
                cot_t, how = c_star, "máximo de V_Rd,max (V_Rd,s ≥ V_Rd,max)"
            else:
                cot_t, how = c_int, "igualdad V_Rd,s = V_Rd,max: cot θ = √(α_cw·b_w·ν_1·f_cd/((A_sw/s)·f_ywd·sen α) − 1)"
    tr.step("Inclinación de las bielas", "Anejo 19, 6.2.3(2), expresión (6.7)",
            "cot θ ∈ [0,5; 2] que maximiza V_Rd = min(V_Rd,s; V_Rd,max)" if inp.cot_theta is None else "cot θ",
            how, cot_t, "-", "cot θ")
    result["cot_theta"] = cot_t
    result["theta_deg"] = math.degrees(math.atan(1.0 / cot_t))
    vmax = vrd_max(cot_t, cot_a, bw, z, nu1, conc.fcd, p["alpha_cw"])
    result["VRd_max"] = vmax
    tr.step("Resistencia de las bielas comprimidas", ref_vmax, eq_vmax, f"cot θ = {fmt(cot_t, 4)}",
            n_to_kn(vmax), "kN", "V_Rd,max")
    tr.check("Compresión oblicua en el alma (bielas)", "Anejo 19, 6.2.1(6); " + ref_vmax.split(", ", 1)[1],
             f"V_Ed = {fmt(n_to_kn(V))} kN", f"V_Rd,max = {fmt(n_to_kn(vmax))} kN", V <= vmax * (1 + 1e-9))
    result["Asw_s_provided"] = asw_s
    _provided_checks(inp, tr, result, V, asw_s, s, cot_t, cot_a, sin_a, z, fywd, slmax, bw, nu1, conc,
                     needs_calc, ref_vs, eq_vs)


def _provided_checks(inp, tr, result, V, asw_s, s, cot_t, cot_a, sin_a, z, fywd, slmax, bw, nu1, conc,
                     needs_calc, ref_vs, eq_vs):
    p = inp.params
    vs = vrd_s(asw_s, cot_t, cot_a, sin_a, z, fywd)
    result["VRd_s"] = vs
    tr.step("Resistencia de la armadura de cortante", ref_vs, eq_vs,
            f"({fmt(asw_s * 1000)}·10⁻³)·{fmt(z, 1)}·{fmt(fywd, 3)}·({fmt(cot_t, 4)} + {fmt(cot_a, 4)})·{fmt(sin_a, 4)}",
            n_to_kn(vs), "kN", "V_Rd,s")
    if needs_calc:
        tr.check("Resistencia a cortante con armadura de cortante", "Anejo 19, 6.2.1(5), (6.1); " + ref_vs.split(", ", 1)[1],
                 f"V_Ed = {fmt(n_to_kn(V))} kN", f"V_Rd,s = {fmt(n_to_kn(vs))} kN", V <= vs * (1 + 1e-9))
    rho_w = asw_s / (bw * sin_a)
    result["rho_w"] = rho_w
    tr.check("Cuantía mínima de armadura de cortante", "Anejo 19, 9.2.2(5), (9.4)-(9.5)",
             f"ρ_w = {fmt(rho_w * 1000, 3)} ‰", f"ρ_w,min = {fmt(result['rho_w_min'] * 1000, 3)} ‰", rho_w >= result["rho_w_min"] * (1 - 1e-9))
    tr.check("Separación longitudinal de los cercos", "Anejo 19, 9.2.2(6), (9.6)",
             f"s = {fmt(s, 1)} mm", f"s_l,max = {fmt(slmax, 1)} mm", s <= slmax + 1e-9)
    smin = min_clear_spacing(inp.stirrup_diameter, inp.dg, p)
    tr.check("Separación libre mínima entre cercos", "Anejo 19, 8.2(2)",
             f"s − φ_t = {fmt(s - inp.stirrup_diameter, 1)} mm", f"s_min = {fmt(smin, 1)} mm",
             s - inp.stirrup_diameter >= smin - 1e-9)
    # Área máxima eficaz (nota de 6.2.3(3)/(4)), referida a cot θ = 1
    lim = 0.5 * p["alpha_cw"] * nu1 * conc.fcd / sin_a
    val = asw_s * fywd / bw
    result["Asw_max_ratio"] = val / lim
    if val > lim * (1 + 1e-9):
        tr.warn(f"A_sw·f_ywd/(b_w·s) = {fmt(val, 3)} MPa supera el valor máximo eficaz {fmt(lim, 3)} MPa "
                "(expresiones (6.12)/(6.15), referidas a cot θ = 1): el exceso de armadura no es eficaz.")
