"""Fluencia y retracción del hormigón (Anejo 19, 3.1.4 y Apéndice B).

* φ(t, t_0): expresiones (B.1)-(B.9) del Apéndice B («métodos recomendados»).
* ε_cs = ε_cd + ε_ca (3.8): retracción por secado (3.9)-(3.10) con ε_cd,0 de (B.11)-(B.12) y k_h de
  la tabla A19.3.3; retracción autógena (3.11)-(3.13).

Validez (3.1.4(5)): temperatura entre −40 °C y +40 °C y humedad relativa entre 40 % y 100 %;
tensión de compresión ≤ 0,45·f_ck(t_0) (fluencia lineal, 3.1.4(2) y (4)).
"""

from __future__ import annotations

import math

from ..materials import Concrete
from ..trace import CalcTrace, fmt

CEMENT_ALPHA = {"S": -1, "N": 0, "R": 1}          # (B.9)
CEMENT_ADS1 = {"S": 3, "N": 4, "R": 6}            # (B.11)
CEMENT_ADS2 = {"S": 0.13, "N": 0.12, "R": 0.11}   # (B.11)
KH_TABLE = [(100.0, 1.0), (200.0, 0.85), (300.0, 0.75), (500.0, 0.70)]  # tabla A19.3.3

REF_B = "Anejo 19, Apéndice B (BOE págs. 98470-98472)"


class CreepError(ValueError):
    pass


def notional_size(Ac: float, u: float) -> float:
    """h_0 = 2·A_c/u, (B.6)."""
    if u <= 0:
        raise CreepError("El perímetro expuesto u debe ser positivo")
    return 2.0 * Ac / u


def creep_coefficient(conc: Concrete, RH: float, h0: float, t0: float, cement: str = "N",
                      t: float | None = None, tr: CalcTrace | None = None) -> float:
    """φ(t, t_0) según (B.1)-(B.9). t = None ⇒ t → ∞ (β_c = 1)."""
    if not (40.0 <= RH <= 100.0):
        raise CreepError("HR fuera del intervalo de validez 40–100 % (3.1.4(5))")
    if t0 <= 0:
        raise CreepError("La edad de puesta en carga t_0 debe ser positiva")
    if cement not in CEMENT_ALPHA:
        raise CreepError("Clase de cemento: S, N o R")
    fcm = conc.fcm
    a1, a2, a3 = (35 / fcm) ** 0.7, (35 / fcm) ** 0.2, (35 / fcm) ** 0.5
    if fcm <= 35:
        phi_rh = 1 + (1 - RH / 100) / (0.1 * h0 ** (1 / 3))
        eq_rh = "(B.3a)"
    else:
        phi_rh = (1 + (1 - RH / 100) / (0.1 * h0 ** (1 / 3)) * a1) * a2
        eq_rh = "(B.3b)"
    b_fcm = 16.8 / math.sqrt(fcm)
    t0_adj = max(t0 * (9 / (2 + t0 ** 1.2) + 1) ** CEMENT_ALPHA[cement], 0.5)
    b_t0 = 1 / (0.1 + t0_adj ** 0.20)
    phi0 = phi_rh * b_fcm * b_t0
    if t is None:
        bc = 1.0
        bH = None
    else:
        if fcm <= 35:
            bH = min(1.5 * (1 + (0.012 * RH) ** 18) * h0 + 250, 1500)
        else:
            bH = min(1.5 * (1 + (0.012 * RH) ** 18) * h0 + 250 * a3, 1500 * a3)
        bc = ((t - t0) / (bH + t - t0)) ** 0.3
    phi = phi0 * bc
    if tr:
        tr.step("Coeficiente de humedad relativa", f"{REF_B}, {eq_rh}",
                "φ_HR = 1 + (1 − HR/100)/(0,1·∛h_0) [·α_1]·[α_2] (f_cm > 35)",
                f"HR = {fmt(RH)} %; h_0 = {fmt(h0, 1)} mm; f_cm = {fmt(fcm)}", phi_rh, "-", "φ_HR")
        tr.step("Efecto de la resistencia", f"{REF_B}, (B.4)", "β(f_cm) = 16,8/√f_cm", f"16,8/√{fmt(fcm)}",
                b_fcm, "-", "β(f_cm)")
        tr.step("Edad de puesta en carga corregida por el tipo de cemento", f"{REF_B}, (B.9)",
                "t_0 = t_0,T·(9/(2 + t_0,T^1,2) + 1)^α ≥ 0,5", f"t_0,T = {fmt(t0)} d; cemento {cement}",
                t0_adj, "días", "t_0")
        tr.step("Efecto de la edad de puesta en carga", f"{REF_B}, (B.5)", "β(t_0) = 1/(0,1 + t_0^0,20)", "",
                b_t0, "-", "β(t_0)")
        tr.step("Coeficiente básico de fluencia", f"{REF_B}, (B.2)", "φ_0 = φ_HR·β(f_cm)·β(t_0)", "", phi0, "-", "φ_0")
        tr.step("Coeficiente de fluencia", f"{REF_B}, (B.1), (B.7)",
                "φ(t, t_0) = φ_0·β_c(t, t_0); t → ∞ ⇒ β_c = 1" if t is None else "φ(t, t_0) = φ_0·β_c(t, t_0)",
                "" if t is None else f"β_H = {fmt(bH, 1)}; β_c = {fmt(bc, 4)}", phi, "-", "φ")
    return phi


def kh_factor(h0: float) -> float:
    """k_h de la tabla A19.3.3 con interpolación lineal (≥ 500 mm: 0,70; ≤ 100 mm: 1,0)."""
    if h0 <= KH_TABLE[0][0]:
        return KH_TABLE[0][1]
    for (x0, y0), (x1, y1) in zip(KH_TABLE, KH_TABLE[1:]):
        if h0 <= x1:
            return y0 + (y1 - y0) * (h0 - x0) / (x1 - x0)
    return KH_TABLE[-1][1]


def drying_shrinkage_basic(conc: Concrete, RH: float, cement: str = "N") -> float:
    """ε_cd,0 según (B.11)-(B.12)."""
    beta_rh = 1.55 * (1 - (RH / 100) ** 3)
    return 0.85 * ((220 + 110 * CEMENT_ADS1[cement]) * math.exp(-CEMENT_ADS2[cement] * conc.fcm / 10)) * 1e-6 * beta_rh


def shrinkage_strain(conc: Concrete, RH: float, h0: float, cement: str = "N", t: float | None = None,
                     ts: float = 7.0, tr: CalcTrace | None = None) -> float:
    """ε_cs = ε_cd + ε_ca (3.8). t = None ⇒ valores finales (t → ∞)."""
    if not (40.0 <= RH <= 100.0):
        raise CreepError("HR fuera del intervalo de validez 40–100 % (3.1.4(5))")
    ecd0 = drying_shrinkage_basic(conc, RH, cement)
    kh = kh_factor(h0)
    bds = 1.0 if t is None else (t - ts) / ((t - ts) + 0.04 * math.sqrt(h0 ** 3))
    ecd = bds * kh * ecd0
    eca_inf = 2.5 * (conc.fck - 10) * 1e-6
    bas = 1.0 if t is None else 1 - math.exp(-0.2 * t ** 0.5)
    eca = bas * eca_inf
    ecs = ecd + eca
    if tr:
        tr.step("Retracción básica por secado", f"{REF_B}, (B.11)-(B.12)",
                "ε_cd,0 = 0,85·[(220 + 110·α_ds1)·exp(−α_ds2·f_cm/f_cm0)]·10⁻⁶·β_HR; β_HR = 1,55·[1 − (HR/100)³]",
                f"cemento {cement}; HR = {fmt(RH)} %; f_cm = {fmt(conc.fcm)}", ecd0 * 1000, "‰", "ε_cd,0")
        tr.step("Coeficiente de espesor", "Anejo 19, 3.1.4(6), tabla A19.3.3 (BOE pág. 98311)",
                "k_h(h_0) (interpolación lineal)", f"h_0 = {fmt(h0, 1)} mm", kh, "-", "k_h")
        tr.step("Retracción por secado", "Anejo 19, 3.1.4(6), (3.9)-(3.10)", "ε_cd = β_ds·k_h·ε_cd,0",
                "t → ∞ ⇒ β_ds = 1" if t is None else f"β_ds = {fmt(bds, 4)}", ecd * 1000, "‰", "ε_cd")
        tr.step("Retracción autógena", "Anejo 19, 3.1.4(6), (3.11)-(3.13) (BOE pág. 98312)",
                "ε_ca = β_as·2,5·(f_ck − 10)·10⁻⁶", "t → ∞ ⇒ β_as = 1" if t is None else f"β_as = {fmt(bas, 4)}",
                eca * 1000, "‰", "ε_ca")
        tr.step("Retracción total", "Anejo 19, 3.1.4(6), (3.8)", "ε_cs = ε_cd + ε_ca", "", ecs * 1000, "‰", "ε_cs")
    return ecs
