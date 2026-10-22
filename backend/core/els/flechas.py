"""Control de deformaciones (Anejo 19, 7.4).

Dos procedimientos, que se presentan por separado:

1. **Estimación simplificada** (7.4.2): relación luz/canto límite (7.16.a/b) con K de la tabla
   A19.7.4 y las correcciones (7.17), secciones en T y luces > 7 m.
2. **Cálculo de flechas** (7.4.3): curvaturas de la sección sin fisurar y totalmente fisurada,
   interpolación (7.18)-(7.19), módulo efectivo por fluencia (7.20) y curvatura de retracción
   (7.21). Siguiendo 7.4.3(7) se calcula la deformación suponiendo el elemento sin fisurar y
   totalmente fisurado y se interpola; la flecha se obtiene de la curvatura en la sección de
   momento máximo con el coeficiente de forma de la ley de momentos (vigas biapoyadas o
   voladizos con carga uniforme, o coeficientes introducidos por el usuario).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..materials import Concrete, ReinforcingSteel
from ..parameters import ParameterSet
from ..section import Layer, ReinforcedSection, Shape, TShape
from ..trace import CalcTrace, fmt
from ..units import knm_to_nmm, nmm_to_knm
from .elastic import cracked, cracking_moment, uncracked
from .fluencia import creep_coefficient, notional_size, shrinkage_strain

VALIDATION_STATUS = (
    "Implementado. Ecuaciones y parámetros cotejados con el texto oficial del Anejo 19 "
    "(BOE-A-2021-13681, apartados 3.1.4, 7.4 y Apéndice B). Validación matemática interna superada. "
    "PENDIENTE: contraste con ejemplos resueltos de bibliografía independiente."
)

# Tabla A19.7.4 (BOE págs. 98402-98403): coeficiente K por sistema estructural.
K_SYSTEM = {
    "biapoyada": (1.0, "Viga simplemente apoyada; losa uni- o bidireccional simplemente apoyada"),
    "continua_extremo": (1.3, "Extremo de vano de viga continua o losa continua"),
    "continua_interior": (1.5, "Vano interior de viga o losa"),
    "losa_plana": (1.2, "Losa apoyada en pilares sin vigas (losa plana)"),
    "voladizo": (0.4, "Voladizo"),
}
# Coeficientes de forma de la flecha (resistencia de materiales; no normativos):
# δ = k_M·L²·(1/r)_máx para la carga; δ = k_cs·L²·(1/r_cs) para curvatura constante.
SHAPE_COEF = {"biapoyada": (5 / 48, 1 / 8), "voladizo": (1 / 4, 1 / 2)}


class DeflectionInputError(ValueError):
    pass


@dataclass
class DeflectionInput:
    shape: Shape
    cover: float
    stirrup_diameter: float
    layers: list[Layer]
    span: float                         # luz L (mm)
    system: str = "biapoyada"
    M_qp_knm: float = 0.0               # momento máximo cuasi-permanente (con signo)
    # fluencia y retracción
    RH: float = 60.0
    t0: float = 28.0
    cement: str = "N"
    perimeter: float | None = None      # perímetro expuesto u (mm); None = perímetro completo
    phi_override: float | None = None
    eps_cs_override: float | None = None   # en ‰
    camber: float = 0.0                 # contraflecha (mm)
    kM: float | None = None             # coeficientes de forma si el sistema no es biapoyada/voladizo
    kcs: float | None = None
    # método simplificado
    As_req: float | None = None         # armadura de tracción necesaria en ELU (mm²)
    As2_req: float = 0.0                # armadura de compresión necesaria en ELU (mm²)
    fragile_partitions: bool = False
    concrete_class: str = "C25/30"
    steel_grade: str = "B500S"
    dg: float = 20.0
    params: ParameterSet = field(default_factory=ParameterSet)
    element_name: str = "Viga"

    def validate(self) -> None:
        if self.span <= 0:
            raise DeflectionInputError("La luz debe ser positiva")
        if self.system not in K_SYSTEM:
            raise DeflectionInputError(f"Sistema estructural no válido: {self.system}")
        if not math.isfinite(self.M_qp_knm):
            raise DeflectionInputError("M_qp no es un número finito")
        if self.camber < 0:
            raise DeflectionInputError("La contraflecha debe ser ≥ 0")
        if self.As_req is not None and self.As_req <= 0:
            raise DeflectionInputError("A_s,req debe ser positiva")


def ld_limit(K: float, fck: float, rho: float, rho2: float) -> tuple[float, str]:
    """Relación luz/canto básica (7.16.a/b)."""
    rho0 = 1e-3 * math.sqrt(fck)
    if rho <= rho0:
        v = K * (11 + 1.5 * math.sqrt(fck) * rho0 / rho + 3.2 * math.sqrt(fck) * (rho0 / rho - 1) ** 1.5)
        return v, "(7.16.a)"
    v = K * (11 + 1.5 * math.sqrt(fck) * rho0 / (rho - rho2) + math.sqrt(fck) / 12 * math.sqrt(rho2 / rho0))
    return v, "(7.16.b)"


def deflection_check(inp: DeflectionInput) -> dict:
    inp.validate()
    p = inp.params
    conc = Concrete.from_class(inp.concrete_class, p)
    steel = ReinforcingSteel.from_grade(inp.steel_grade, p)
    sec = ReinforcedSection(inp.shape, inp.cover, inp.stirrup_diameter, inp.layers, inp.dg, p)
    sign = 1 if inp.M_qp_knm >= 0 else -1
    if inp.system == "voladizo" and inp.M_qp_knm > 0:
        raise DeflectionInputError("En un voladizo el momento cuasi-permanente es negativo (tracción superior)")
    tface = "inferior" if sign > 0 else "superior"
    L = inp.span
    d = sec.centroid_depth(tface)
    if d is None:
        raise DeflectionInputError(f"No hay armadura en la cara traccionada ({tface})")

    tr = CalcTrace("ELS — deformaciones",
                   "Relación luz/canto (7.4.2) y cálculo de flechas con interpolación entre estados sin fisurar y "
                   "fisurado (7.4.3), fluencia (7.20) y retracción (7.21)", VALIDATION_STATUS)
    tr.units = {"longitudes": "mm", "momentos": "kN·m", "curvaturas": "1/mm", "flechas": "mm", "deformaciones": "‰"}
    tr.inputs = {"elemento": inp.element_name, "seccion": inp.shape.to_dict(), "capas": [l.__dict__ for l in inp.layers],
                 "luz_mm": L, "sistema": inp.system, "M_qp_kNm": inp.M_qp_knm, "HR_%": inp.RH, "t0_dias": inp.t0,
                 "cemento": inp.cement, "perimetro_expuesto_mm": inp.perimeter, "phi_usuario": inp.phi_override,
                 "eps_cs_usuario_permil": inp.eps_cs_override, "contraflecha_mm": inp.camber,
                 "As_req_mm2": inp.As_req, "As2_req_mm2": inp.As2_req, "tabiques_fragiles": inp.fragile_partitions,
                 "hormigon": inp.concrete_class, "acero": inp.steel_grade}
    tr.assume("Elemento de hormigón armado en flexión simple bajo la combinación cuasi-permanente.")
    tr.assume("M_qp es el momento máximo en el vano (o en el arranque del voladizo) de la combinación "
              "cuasi-permanente, obtenido del análisis estructural.")
    result: dict = {"d": d}

    # ------------------------------------------------------------------ 1. Método simplificado
    K, desc = K_SYSTEM[inp.system]
    if inp.As_req is None:
        tr.limit("Método simplificado (7.4.2) no evaluado: indique la armadura de tracción necesaria en ELU, A_s,req.")
        result["ld"] = None
    else:
        bw = inp.shape.web_width
        rho = inp.As_req / (bw * d)
        rho2 = inp.As2_req / (bw * d)
        base, eq = ld_limit(K, conc.fck, rho, rho2)
        tr.step("Coeficiente del sistema estructural", "Anejo 19, 7.4.2(2), tabla A19.7.4 (BOE págs. 98402-98403)",
                "K", desc, K, "-", "K")
        tr.step("Cuantías de cálculo", "Anejo 19, 7.4.2(2)", "ρ = A_s,req/(b·d); ρ′ = A_s2,req/(b·d); ρ_0 = 10⁻³·√f_ck",
                f"b = {fmt(bw)} mm; d = {fmt(d, 1)} mm; ρ = {fmt(rho, 5)}; ρ′ = {fmt(rho2, 5)}; "
                f"ρ_0 = {fmt(1e-3 * math.sqrt(conc.fck), 5)}", None, "")
        tr.step("Relación luz/canto básica", f"Anejo 19, 7.4.2(2), expresión {eq} (BOE pág. 98401)",
                "l/d = K·[11 + 1,5√f_ck·ρ_0/ρ + 3,2√f_ck·(ρ_0/ρ − 1)^(3/2)]" if eq == "(7.16.a)" else
                "l/d = K·[11 + 1,5√f_ck·ρ_0/(ρ − ρ′) + (1/12)·√f_ck·√(ρ′/ρ_0)]", "", base, "-", "(l/d)_0")
        As_prov = sec.area_on(tface)
        f_sigma = 500.0 / (steel.fyk * inp.As_req / As_prov)
        tr.use_param(p, "ld_sigma_ref")
        tr.step("Corrección por tensión del acero", "Anejo 19, 7.4.2(2), expresión (7.17) (BOE pág. 98402)",
                "310/σ_s = 500/(f_yk·A_s,req/A_s,prov)",
                f"500/({fmt(steel.fyk)}·{fmt(inp.As_req, 0)}/{fmt(As_prov, 0)})", f_sigma, "-", "310/σ_s")
        factor = f_sigma
        if isinstance(inp.shape, TShape) and inp.shape.bf / inp.shape.bw > 3:
            factor *= 0.8
            tr.step("Corrección por sección en T", "Anejo 19, 7.4.2(2)", "× 0,8 si b_f/b_w > 3",
                    f"b_f/b_w = {fmt(inp.shape.bf / inp.shape.bw, 2)}", 0.8, "-", "")
        Lm = L / 1000
        if inp.fragile_partitions:
            lim_span = 8.5 if inp.system == "losa_plana" else 7.0
            if Lm > lim_span:
                f_span = lim_span / Lm
                factor *= f_span
                tr.step("Corrección por luz con tabiques frágiles", "Anejo 19, 7.4.2(2)",
                        f"× {fmt(lim_span)}/l_eff (l_eff > {fmt(lim_span)} m)", f"l_eff = {fmt(Lm, 2)} m",
                        f_span, "-", "")
        ld_lim = base * factor
        ld_act = L / d
        tr.step("Relación luz/canto límite", "Anejo 19, 7.4.2(2)", "(l/d)_lim = (l/d)_0 · correcciones",
                "", ld_lim, "-", "(l/d)_lim")
        tr.check("Relación luz/canto (método simplificado)", "Anejo 19, 7.4.2",
                 f"l/d = {fmt(ld_act, 2)}", f"(l/d)_lim = {fmt(ld_lim, 2)}", ld_act <= ld_lim + 1e-9,
                 "Si se cumple, puede considerarse que las flechas no superan los límites de 7.4.1(4) y (5) "
                 "(7.4.2(2)). Si no, la comprobación se remite al cálculo de flechas.")
        result["ld"] = {"actual": ld_act, "limit": ld_lim, "basic": base, "rho": rho, "rho2": rho2, "K": K}
        tr.assume("En el método simplificado ρ se refiere al ancho del alma b_w (del lado de la seguridad en secciones en T).")

    # ------------------------------------------------------------------ 2. Cálculo de flechas
    if inp.M_qp_knm == 0:
        tr.limit("M_qp = 0: no se calcula la flecha.")
        result["calc"] = None
        return _finish(tr, result, sec, conc, steel)
    if inp.system in SHAPE_COEF:
        kM, kcs = SHAPE_COEF[inp.system]
    elif inp.kM is not None and inp.kcs is not None:
        kM, kcs = inp.kM, inp.kcs
    else:
        tr.limit("Cálculo de flechas no evaluado: para este sistema estructural indique los coeficientes de forma "
                 "k_M y k_cs de la ley de momentos (solo se tabulan biapoyada y voladizo con carga uniforme).")
        result["calc"] = None
        return _finish(tr, result, sec, conc, steel)
    tr.assume(f"Flecha a partir de la curvatura en la sección de momento máximo: δ = k_M·L²·(1/r) con k_M = "
              f"{fmt(kM, 4)} y, para la retracción (curvatura constante), k_cs = {fmt(kcs, 4)} "
              "(coeficientes de resistencia de materiales, no normativos).")

    M = abs(knm_to_nmm(inp.M_qp_knm))
    Ac = inp.shape.area
    u = inp.perimeter if inp.perimeter is not None else _perimeter(inp.shape)
    h0 = notional_size(Ac, u)
    tr.step("Espesor medio", "Anejo 19, Apéndice B, (B.6); 3.1.4(5)", "h_0 = 2·A_c/u",
            f"2·{fmt(Ac, 0)}/{fmt(u, 0)}", h0, "mm", "h_0")
    if inp.phi_override is not None:
        phi = inp.phi_override
        tr.step("Coeficiente de fluencia (dato del usuario)", "Anejo 19, 3.1.4", "φ(∞, t_0)", "", phi, "-", "φ")
    else:
        phi = creep_coefficient(conc, inp.RH, h0, inp.t0, inp.cement, None, tr)
    if inp.eps_cs_override is not None:
        ecs = inp.eps_cs_override / 1000
        tr.step("Retracción total (dato del usuario)", "Anejo 19, 3.1.4(6)", "ε_cs", "", ecs * 1000, "‰", "ε_cs")
    else:
        ecs = shrinkage_strain(conc, inp.RH, h0, inp.cement, None, 7.0, tr)
    Ecm, Es = conc.Ecm, steel.Es
    Eeff = Ecm / (1 + phi)
    a_s, a_l = Es / Ecm, Es / Eeff
    tr.step("Módulo de elasticidad efectivo", "Anejo 19, 7.4.3(5), expresión (7.20) (BOE pág. 98404)",
            "E_c,eff = E_cm/(1 + φ(∞, t_0))", f"{fmt(Ecm, 0)}/(1 + {fmt(phi, 3)})", Eeff, "MPa", "E_c,eff")

    Mcr, unS = cracking_moment(sec, a_s, conc.fctm, sign)
    tr.step("Momento de fisuración", "Anejo 19, 7.4.3(3)-(4)", "M_cr = f_ctm·I_I/(h − y_I) (α_e = E_s/E_cm)",
            f"f_ctm = {fmt(conc.fctm)}", nmm_to_knm(Mcr), "kN·m", "M_cr")
    beta_long = tr.use_param(p, "defl_zeta_beta_long")

    def zeta(beta: float) -> float:
        return 0.0 if M <= Mcr else 1 - beta * (Mcr / M) ** 2

    # instantánea (corta duración, β = 1,0)
    uI_s, cII_s = unS, cracked(sec, a_s, sign)
    curvI_s, curvII_s = M / (Ecm * uI_s.I), M / (Ecm * cII_s.I)
    z_s = zeta(1.0)
    curv_inst = z_s * curvII_s + (1 - z_s) * curvI_s
    # largo plazo (β = 0,5, E_c,eff) + retracción
    uI_l, cII_l = uncracked(sec, a_l, sign), cracked(sec, a_l, sign)
    curvI_l, curvII_l = M / (Eeff * uI_l.I), M / (Eeff * cII_l.I)
    z_l = zeta(beta_long)
    curv_load = z_l * curvII_l + (1 - z_l) * curvI_l
    csI = ecs * a_l * uI_l.S_s / uI_l.I
    csII = ecs * a_l * cII_l.S_s / cII_l.I
    curv_cs = z_l * csII + (1 - z_l) * csI
    tr.step("Coeficiente de distribución (instantánea)", "Anejo 19, 7.4.3(3), (7.19)",
            "ζ = 1 − β·(M_cr/M)²; β = 1,0 (carga de corta duración); ζ = 0 si M ≤ M_cr",
            f"M = {fmt(nmm_to_knm(M))} kN·m", z_s, "-", "ζ_inst")
    tr.step("Curvatura instantánea", "Anejo 19, 7.4.3(3), (7.18)", "1/r = ζ·M/(E_cm·I_II) + (1 − ζ)·M/(E_cm·I_I)",
            f"I_I = {fmt(uI_s.I, 0)}; I_II = {fmt(cII_s.I, 0)} mm⁴", curv_inst, "1/mm", "1/r_inst")
    tr.step("Coeficiente de distribución (larga duración)", "Anejo 19, 7.4.3(3), (7.19)",
            "ζ = 1 − β·(M_cr/M)²; β = 0,5 (carga prolongada)", "", z_l, "-", "ζ")
    tr.step("Curvatura por cargas a largo plazo", "Anejo 19, 7.4.3(3), (5); (7.18), (7.20)",
            "1/r = ζ·M/(E_c,eff·I_II) + (1 − ζ)·M/(E_c,eff·I_I)",
            f"α_e = {fmt(a_l, 3)}; I_I = {fmt(uI_l.I, 0)}; I_II = {fmt(cII_l.I, 0)} mm⁴", curv_load, "1/mm", "1/r_M")
    tr.step("Curvatura de retracción", "Anejo 19, 7.4.3(6), expresión (7.21) (BOE pág. 98404)",
            "1/r_cs = ε_cs·α_e·S/I (sin fisurar y fisurada, interpoladas con (7.18))",
            f"S_I = {fmt(uI_l.S_s, 0)}; S_II = {fmt(cII_l.S_s, 0)} mm³", curv_cs, "1/mm", "1/r_cs")
    d_inst = kM * L ** 2 * curv_inst
    d_load = kM * L ** 2 * curv_load
    d_cs = kcs * L ** 2 * curv_cs
    d_total = d_load + d_cs
    d_def = d_total - d_inst
    tr.step("Flecha instantánea", "Resistencia de materiales", "δ_inst = k_M·L²·(1/r_inst)", "", d_inst, "mm", "δ_inst")
    tr.step("Flecha total a largo plazo", "Anejo 19, 7.4.3", "δ_tot = k_M·L²·(1/r_M) + k_cs·L²·(1/r_cs)",
            f"carga {fmt(d_load, 2)} mm + retracción {fmt(d_cs, 2)} mm", d_total, "mm", "δ_tot")
    tr.step("Flecha diferida", "Anejo 19, 7.4.1(5)", "δ_dif = δ_tot − δ_inst", "", d_def, "mm", "δ_dif")
    lim_tot = L / tr.use_param(p, "defl_total_div")
    lim_def = L / tr.use_param(p, "defl_deferred_div")
    tr.check("Flecha total (cuasi-permanente)", "Anejo 19, 7.4.1(4) (BOE pág. 98401)",
             f"δ_tot − contraflecha = {fmt(d_total - inp.camber, 2)} mm", f"L/250 = {fmt(lim_tot, 2)} mm",
             d_total - inp.camber <= lim_tot + 1e-9)
    if inp.camber > 0:
        tr.check("Contraflecha", "Anejo 19, 7.4.1(4)", f"{fmt(inp.camber)} mm", f"L/250 = {fmt(lim_tot, 2)} mm",
                 inp.camber <= lim_tot + 1e-9)
    tr.check("Flecha diferida (cuasi-permanente)", "Anejo 19, 7.4.1(5)", f"δ_dif = {fmt(d_def, 2)} mm",
             f"L/500 = {fmt(lim_def, 2)} mm", d_def <= lim_def + 1e-9,
             "Se aproxima por la diferencia entre la flecha total a largo plazo y la instantánea.")
    result["calc"] = {"phi": phi, "eps_cs": ecs, "h0": h0, "E_eff": Eeff, "Mcr": Mcr, "zeta_long": z_l,
                      "zeta_inst": z_s, "curv_inst": curv_inst, "curv_load": curv_load, "curv_cs": curv_cs,
                      "delta_inst": d_inst, "delta_load": d_load, "delta_cs": d_cs, "delta_total": d_total,
                      "delta_deferred": d_def, "limit_total": lim_tot, "limit_deferred": lim_def,
                      "kM": kM, "kcs": kcs}
    return _finish(tr, result, sec, conc, steel)


def _perimeter(shape: Shape) -> float:
    if isinstance(shape, TShape):
        return 2 * shape.bf + 2 * shape.h
    return 2 * (shape.b + shape.h)


def _finish(tr, result, sec, conc, steel) -> dict:
    for msg in sec.issues:
        tr.warn(msg)
    result["geometry"] = sec.geometric_properties()
    return {"ok": tr.all_checks_ok, "trace": tr.to_dict(), "result": result,
            "materials": {"concrete": conc.properties(), "steel": steel.properties()}}
