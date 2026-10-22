"""Control de la fisuración (Anejo 19, 7.3) y limitación de tensiones (7.2) en flexión simple.

* Tensiones en sección fisurada elástica (α_e = E_s/E_cm, 7.3.4(2)).
* Abertura característica w_k = s_r,max·(ε_sm − ε_cm), (7.8)-(7.14).
* Armadura mínima (7.1)-(7.2) para secciones rectangulares y almas.
* Valores límite w_max de la tabla 27.2 del Código Estructural, reproducida en 7.3.1(5).

Fuera de alcance: esfuerzo axil (tracción o compresión), pretensado, elementos armados en dos
direcciones (7.15), muros (7.3.4(5)), armadura de piel (7.3.3(3)), alas traccionadas de secciones
en T para la armadura mínima (7.3).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..elu.analysis import oriented_geometry
from ..materials import Concrete, ReinforcingSteel
from ..parameters import ParameterSet
from ..section import Layer, ReinforcedSection, Shape, TShape
from ..trace import CalcTrace, fmt
from ..units import knm_to_nmm, nmm_to_knm
from .elastic import cracked, cracking_moment

VALIDATION_STATUS = (
    "Implementado. Ecuaciones y parámetros cotejados con el texto oficial del Anejo 19 "
    "(BOE-A-2021-13681, apartados 7.2 y 7.3). Validación matemática interna superada. "
    "PENDIENTE: contraste con ejemplos resueltos de bibliografía independiente."
)

# Tabla 27.2 (reproducida en 7.3.1(5), BOE pág. 98393): w_max (mm), hormigón armado, cuasi-permanente.
WMAX_RC = {
    "X0": 0.4, "XC1": 0.4,
    "XC2": 0.3, "XC3": 0.3, "XC4": 0.3, "XF1": 0.3, "XF3": 0.3,
    "XS1": 0.2, "XS2": 0.2, "XD1": 0.2, "XD2": 0.2, "XD3": 0.2, "XF2": 0.2, "XF4": 0.2, "XA1": 0.2,
    "XS3": 0.1, "XA2": 0.1, "XA3": 0.1,
}
STRESS_K1_CLASSES = ("XD", "XF", "XS")


class CrackInputError(ValueError):
    pass


@dataclass
class CrackInput:
    shape: Shape
    cover: float
    stirrup_diameter: float
    layers: list[Layer]
    M_qp_knm: float                    # combinación cuasi-permanente
    exposure: str = "XC1"
    M_char_knm: float | None = None    # combinación característica (para 7.2), opcional
    w_max: float | None = None         # límite del proyecto (si no, tabla 27.2)
    long_term: bool = True             # k_t = 0,4 (larga duración) / 0,6 (corta)
    concrete_class: str = "C25/30"
    steel_grade: str = "B500S"
    dg: float = 20.0
    params: ParameterSet = field(default_factory=ParameterSet)
    element_name: str = "Viga"

    def validate(self) -> None:
        if not math.isfinite(self.M_qp_knm):
            raise CrackInputError("M_qp no es un número finito")
        if self.exposure not in WMAX_RC:
            raise CrackInputError(f"Clase de exposición no admitida: {self.exposure}")
        if self.w_max is not None and self.w_max <= 0:
            raise CrackInputError("w_max debe ser positivo")
        if self.M_char_knm is not None and self.M_char_knm * self.M_qp_knm < 0:
            raise CrackInputError("M_qp y M_k deben tener el mismo signo")


def _act_and_tension_width(section: ReinforcedSection, sign: int, y_na: float) -> tuple[float, float]:
    """A_ct: área de hormigón traccionado (sección sin fisurar) y ancho en la fibra traccionada."""
    segs, _, h = oriented_geometry(section, sign)
    act = sum(s.width * max(s.y_bot - max(s.y_top, y_na), 0) for s in segs)
    return act, segs[-1].width


def _effective_area(section: ReinforcedSection, sign: int, hc: float) -> float:
    segs, _, h = oriented_geometry(section, sign)
    top = h - hc
    return sum(s.width * max(s.y_bot - max(s.y_top, top), 0) for s in segs)


def crack_check(inp: CrackInput) -> dict:
    inp.validate()
    p = inp.params
    conc = Concrete.from_class(inp.concrete_class, p)
    steel = ReinforcingSteel.from_grade(inp.steel_grade, p)
    sec = ReinforcedSection(inp.shape, inp.cover, inp.stirrup_diameter, inp.layers, inp.dg, p)
    sign = 1 if inp.M_qp_knm >= 0 else -1
    tface = "inferior" if sign > 0 else "superior"
    M = abs(knm_to_nmm(inp.M_qp_knm))
    h = inp.shape.h
    Es, Ecm = steel.Es, conc.Ecm
    alpha = Es / Ecm

    tr = CalcTrace("ELS — fisuración y limitación de tensiones (flexión simple)",
                   "Sección fisurada elástica; abertura característica de fisura (7.3.4); armadura mínima (7.3.2)",
                   VALIDATION_STATUS)
    tr.units = {"longitudes": "mm", "áreas": "mm²", "tensiones": "MPa", "momentos": "kN·m", "abertura": "mm"}
    tr.inputs = {"elemento": inp.element_name, "seccion": inp.shape.to_dict(), "recubrimiento_mm": inp.cover,
                 "capas": [l.__dict__ for l in inp.layers], "hormigon": inp.concrete_class, "acero": inp.steel_grade,
                 "M_qp_kNm (cuasi-permanente)": inp.M_qp_knm, "M_k_kNm (característica)": inp.M_char_knm,
                 "clase_exposicion": inp.exposure, "w_max_mm": inp.w_max, "larga_duracion": inp.long_term}
    tr.assume("Flexión simple (N = 0) de hormigón armado sin pretensado.")
    tr.assume("Comportamiento elástico lineal; hormigón traccionado despreciado en la sección fisurada.")
    tr.assume("α_e = E_s/E_cm (7.3.4(2)); f_ct,eff = f_ctm para la abertura de fisura (7.1(2)).")
    tr.assume("Los momentos M_qp y M_k proceden del análisis estructural para las combinaciones indicadas "
              "(el programa no combina acciones).")
    tr.assume("Se toma la tensión σ_s de la capa de armadura más traccionada (del lado de la seguridad).")
    tr.limit("No se consideran el esfuerzo axil, el pretensado, la armadura de piel (7.3.3(3)) ni los elementos "
             "armados en dos direcciones (7.15).")

    tr.step("Resistencia media a tracción", "Anejo 19, tabla A19.3.1", "f_ctm", f"{conc.name}", conc.fctm, "MPa", "f_ctm")
    tr.step("Coeficiente de equivalencia", "Anejo 19, 7.3.4(2)", "α_e = E_s/E_cm", f"{fmt(Es, 0)}/{fmt(Ecm, 0)}",
            alpha, "-", "α_e")

    # --- fisuración ---
    Mcr, un = cracking_moment(sec, alpha, conc.fctm, sign)
    tr.step("Momento de fisuración (sección homogeneizada sin fisurar)", "Anejo 19, 7.1(2); 7.4.3(4)",
            "M_cr = f_ctm·I_I/(h − y_I)", f"I_I = {fmt(un.I, 0)} mm⁴; y_I = {fmt(un.yc, 2)} mm",
            nmm_to_knm(Mcr), "kN·m", "M_cr")
    cr = cracked(sec, alpha, sign)
    tr.step("Profundidad de la fibra neutra (sección fisurada)", "Equilibrio de momentos estáticos (elasticidad)",
            "Σ S(x) = 0 con hormigón traccionado despreciado", "", cr.yc, "mm", "x")
    tr.step("Inercia de la sección fisurada", "Elasticidad", "I_II", "", cr.I, "mm⁴", "I_II")
    segs, bars, _ = oriented_geometry(sec, sign)
    tbars = [b for b in bars if b.tension_side]
    if not tbars:
        raise CrackInputError("No hay armadura en la cara traccionada")
    y_max = max(b.y for b in tbars)
    sigma_s = alpha * M * (y_max - cr.yc) / cr.I
    sigma_c = M * cr.yc / cr.I
    tr.step("Tensión en la armadura más traccionada (cuasi-permanente)", "Anejo 19, 7.3.4(2)",
            "σ_s = α_e·M·(y_s − x)/I_II", f"y_s = {fmt(y_max, 1)} mm", sigma_s, "MPa", "σ_s")
    tr.step("Tensión máxima de compresión en el hormigón (cuasi-permanente)", "Elasticidad",
            "σ_c = M·x/I_II", "", sigma_c, "MPa", "σ_c")
    result: dict = {"alpha_e": alpha, "Mcr": Mcr, "x": cr.yc, "I_II": cr.I, "I_I": un.I, "sigma_s": sigma_s,
                    "sigma_c": sigma_c, "cracked": M > Mcr}

    # 7.2(3): fluencia lineal
    k2 = tr.use_param(p, "sls_k2")
    if sigma_c > k2 * conc.fck:
        tr.warn(f"σ_c = {fmt(sigma_c)} MPa > 0,45·f_ck bajo cargas cuasi-permanentes: debe considerarse una "
                "fluencia no lineal (7.2(3), 3.1.4(4)).")

    wlim = inp.w_max if inp.w_max is not None else WMAX_RC[inp.exposure]
    tr.step("Abertura máxima de fisura", "Código Estructural, tabla 27.2 (Anejo 19, 7.3.1(5), BOE pág. 98393)"
            if inp.w_max is None else "Valor fijado por el proyecto (7.3.1(5))",
            "w_max (hormigón armado, combinación cuasi-permanente)", f"clase {inp.exposure}", wlim, "mm", "w_max")
    result["w_max"] = wlim

    if M <= Mcr:
        tr.step("Estado de la sección", "Anejo 19, 7.1(2)", "M_qp ≤ M_cr ⇒ sección no fisurada", "", 0.0, "mm", "w_k")
        result["w_k"] = 0.0
        tr.check("Abertura de fisura", "Anejo 19, 7.3.1(5); 7.3.4", "M_qp ≤ M_cr: w_k = 0", f"w_max = {fmt(wlim)} mm", True)
    else:
        d_t = y_max
        d_c = sum(b.area * b.y for b in tbars) / sum(b.area for b in tbars)
        hc = min(2.5 * (h - d_c), (h - cr.yc) / 3, h / 2)
        Aceff = _effective_area(sec, sign, hc)
        As = sum(b.area for b in tbars if b.y >= h - hc)
        if As <= 0:
            As = sum(b.area for b in tbars)
            tr.warn("Ninguna barra traccionada queda dentro de A_c,eff: se toma toda la armadura de la cara traccionada.")
        rho = As / Aceff
        tr.step("Altura del área eficaz traccionada", "Anejo 19, 7.3.2(3), figura A19.7.1 (BOE págs. 98395-98396)",
                "h_c,ef = min{2,5·(h − d); (h − x)/3; h/2}",
                f"min{{2,5·({fmt(h)} − {fmt(d_c, 1)}); ({fmt(h)} − {fmt(cr.yc, 1)})/3; {fmt(h)}/2}}", hc, "mm", "h_c,ef")
        tr.step("Área eficaz de hormigón traccionado", "Anejo 19, 7.3.2(3)", "A_c,eff", "", Aceff, "mm²", "A_c,eff")
        tr.step("Cuantía eficaz", "Anejo 19, 7.3.4(2), expresión (7.10)", "ρ_p,eff = A_s/A_c,eff",
                f"{fmt(As, 1)}/{fmt(Aceff, 0)}", rho, "-", "ρ_p,eff")
        kt = tr.use_param(p, "crack_kt_long" if inp.long_term else "crack_kt_short")
        rmin = tr.use_param(p, "crack_min_ratio")
        de = (sigma_s - kt * conc.fctm / rho * (1 + alpha * rho)) / Es
        de_min = rmin * sigma_s / Es
        de_use = max(de, de_min)
        tr.step("Diferencia de deformaciones medias", "Anejo 19, 7.3.4(2), expresión (7.9) (BOE pág. 98398)",
                "ε_sm − ε_cm = [σ_s − k_t·(f_ct,eff/ρ_p,eff)·(1 + α_e·ρ_p,eff)]/E_s ≥ 0,6·σ_s/E_s",
                f"k_t = {fmt(kt)}; valor = {fmt(de * 1000, 4)} ‰; mínimo = {fmt(de_min * 1000, 4)} ‰",
                de_use * 1000, "‰", "ε_sm − ε_cm")
        # separación de fisuras
        layer_bars = [b for b in tbars]
        n_by_phi: dict[float, int] = {}
        for b in layer_bars:
            n_by_phi[b.diameter] = n_by_phi.get(b.diameter, 0) + 1
        phi_eq = sum(n * f ** 2 for f, n in n_by_phi.items()) / sum(n * f for f, n in n_by_phi.items())
        c = inp.cover + inp.stirrup_diameter
        outer = sorted([b for b in sec.bars if b.face == tface and b.layer == 1], key=lambda b: b.x)
        spacing = max((b2.x - b1.x for b1, b2 in zip(outer, outer[1:])), default=0.0)
        lim_sp = 5 * (c + phi_eq / 2)
        tr.step("Diámetro equivalente", "Anejo 19, 7.3.4(3), expresión (7.12)", "φ_eq = Σn·φ²/Σn·φ",
                ", ".join(f"{n}φ{fmt(f)}" for f, n in n_by_phi.items()), phi_eq, "mm", "φ_eq")
        tr.step("Recubrimiento de la armadura longitudinal", "Anejo 19, 7.3.4(3)", "c = c_nom + φ_t",
                f"{fmt(inp.cover)} + {fmt(inp.stirrup_diameter)}", c, "mm", "c")
        if spacing <= lim_sp + 1e-9:
            k1, k2c, k3, k4 = (tr.use_param(p, k) for k in ("crack_k1", "crack_k2_flex", "crack_k3", "crack_k4"))
            srmax = k3 * c + k1 * k2c * k4 * phi_eq / rho
            tr.step("Separación máxima entre fisuras", "Anejo 19, 7.3.4(3), expresión (7.11) (BOE pág. 98399)",
                    "s_r,max = k_3·c + k_1·k_2·k_4·φ/ρ_p,eff",
                    f"separación entre barras {fmt(spacing, 1)} mm ≤ 5(c + φ/2) = {fmt(lim_sp, 1)} mm; "
                    f"{fmt(k3)}·{fmt(c)} + {fmt(k1)}·{fmt(k2c)}·{fmt(k4)}·{fmt(phi_eq, 2)}/{fmt(rho, 5)}",
                    srmax, "mm", "s_r,max")
        else:
            kk = tr.use_param(p, "crack_sr_alt")
            srmax = kk * (h - cr.yc)
            tr.step("Separación máxima entre fisuras (armadura separada)", "Anejo 19, 7.3.4(3), expresión (7.14)",
                    "s_r,max = 1,3·(h − x)", f"separación {fmt(spacing, 1)} mm > 5(c + φ/2) = {fmt(lim_sp, 1)} mm",
                    srmax, "mm", "s_r,max")
        wk = srmax * de_use
        tr.step("Abertura característica de fisura", "Anejo 19, 7.3.4(1), expresión (7.8) (BOE pág. 98398)",
                "w_k = s_r,max·(ε_sm − ε_cm)", f"{fmt(srmax, 1)}·{fmt(de_use * 1000, 4)}·10⁻³", wk, "mm", "w_k")
        result.update({"w_k": wk, "s_r_max": srmax, "rho_p_eff": rho, "h_c_ef": hc, "A_c_eff": Aceff,
                       "eps_diff": de_use, "phi_eq": phi_eq})
        tr.check("Abertura de fisura", "Anejo 19, 7.3.1(5); 7.3.4", f"w_k = {fmt(wk, 3)} mm", f"w_max = {fmt(wlim)} mm",
                 wk <= wlim + 1e-12)

    # --- armadura mínima (7.3.2) ---
    if isinstance(inp.shape, TShape) and sign < 0:
        tr.check("Armadura mínima de fisuración", "Anejo 19, 7.3.2(2)", "ala traccionada de sección en T",
                 "expresión (7.3)", None, "No implementado: el ala traccionada requiere k_c según (7.3).")
    else:
        bw = inp.shape.web_width
        hw = h
        if hw <= 300:
            kfac = 1.0
        elif hw >= 800:
            kfac = 0.65
        else:
            kfac = 1.0 + (0.65 - 1.0) * (hw - 300) / 500
        kc = tr.use_param(p, "crack_kc_flex")
        y_na_un = un.yc
        Act, _ = _act_and_tension_width(sec, sign, y_na_un)
        if isinstance(inp.shape, TShape):
            segs_o, _, _ = oriented_geometry(sec, sign)
            Act = sum(s.width * max(s.y_bot - max(s.y_top, y_na_un), 0) for s in segs_o if s.width == bw)
        As_min = kc * kfac * conc.fctm * Act / steel.fyk
        tr.step("Coeficiente de tensiones no uniformes", "Anejo 19, 7.3.2(2) (BOE pág. 98394)",
                "k = 1,0 (h ≤ 300 mm); 0,65 (h ≥ 800 mm); interpolación", f"h = {fmt(hw)} mm", kfac, "-", "k")
        tr.step("Área de hormigón traccionado antes de fisurar", "Anejo 19, 7.3.2(2)", "A_ct (sección sin fisurar)",
                f"fibra neutra a {fmt(y_na_un, 1)} mm", Act, "mm²", "A_ct")
        tr.step("Armadura mínima de fisuración", "Anejo 19, 7.3.2(2), expresiones (7.1)-(7.2)",
                "A_s,min = k_c·k·f_ct,eff·A_ct/σ_s; k_c = 0,4 (σ_c = 0); σ_s = f_yk",
                f"{fmt(kc)}·{fmt(kfac, 3)}·{fmt(conc.fctm)}·{fmt(Act, 0)}/{fmt(steel.fyk)}", As_min, "mm²", "A_s,min")
        As_t = sec.area_on(tface)
        result["As_min_crack"] = As_min
        tr.check("Armadura mínima de fisuración", "Anejo 19, 7.3.2(2)", f"A_s = {fmt(As_t, 0)} mm²",
                 f"A_s,min = {fmt(As_min, 0)} mm²", As_t >= As_min - 1e-6)

    # --- limitación de tensiones con la combinación característica (7.2) ---
    if inp.M_char_knm is not None:
        Mk = abs(knm_to_nmm(inp.M_char_knm))
        ss_k = alpha * Mk * (y_max - cr.yc) / cr.I
        sc_k = Mk * cr.yc / cr.I
        k3 = tr.use_param(p, "sls_k3")
        tr.step("Tensiones con la combinación característica", "Elasticidad (sección fisurada)",
                "σ_s = α_e·M_k·(y_s − x)/I_II; σ_c = M_k·x/I_II", f"M_k = {fmt(inp.M_char_knm)} kN·m", ss_k, "MPa", "σ_s")
        tr.check("Tensión en la armadura (característica)", "Anejo 19, 7.2(5) (BOE pág. 98392)",
                 f"σ_s = {fmt(ss_k)} MPa", f"k_3·f_yk = {fmt(k3 * steel.fyk)} MPa", ss_k <= k3 * steel.fyk + 1e-9)
        if inp.exposure.startswith(STRESS_K1_CLASSES):
            k1 = tr.use_param(p, "sls_k1")
            tr.check("Tensión de compresión en el hormigón (característica)", "Anejo 19, 7.2(2)",
                     f"σ_c = {fmt(sc_k)} MPa", f"k_1·f_ck = {fmt(k1 * conc.fck)} MPa", sc_k <= k1 * conc.fck + 1e-9,
                     "Aplicable a clases de exposición XD, XF y XS.")
        result.update({"sigma_s_char": ss_k, "sigma_c_char": sc_k})
    else:
        tr.limit("No se ha indicado M_k: no se comprueban las tensiones de 7.2(2) y 7.2(5) con la combinación "
                 "característica.")
    for msg in sec.issues:
        tr.warn(msg)
    result["geometry"] = sec.geometric_properties()
    return {"ok": tr.all_checks_ok, "trace": tr.to_dict(), "result": result,
            "materials": {"concrete": conc.properties(), "steel": steel.properties()}}
