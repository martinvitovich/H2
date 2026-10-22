"""ELS (Anejo 19, 3.1.4, 7.2-7.4, Apéndice B): contrastes independientes.

* Tabla A19.3.2 (valores de ε_cd,0 tabulados en el texto oficial, BOE pág. 98311) frente a la
  expresión (B.11)-(B.12) del Apéndice B: dos partes independientes del Anejo.
* Tabla A19.7.4 (l/d tabulados para ρ = 0,5 % y 1,5 %) frente a (7.16.a/b) con f_ck = 30 MPa. Según
  su NOTA 1 los valores tabulados «se han seleccionado para quedar, en general, del lado de la
  seguridad» y no son la salida exacta de (7.16): se admite una diferencia de hasta una unidad.
  La resistencia con la que se elaboró la tabla no se indica en el Anejo (hipótesis f_ck = 30).
* Sección fisurada rectangular con armadura simple: solución cerrada clásica.
"""

import math

import pytest

from core.els.elastic import cracked, cracking_moment, uncracked
from core.els.fisuracion import CrackInput, CrackInputError, WMAX_RC, crack_check
from core.els.flechas import DeflectionInput, DeflectionInputError, deflection_check, ld_limit
from core.els.fluencia import CreepError, creep_coefficient, drying_shrinkage_basic, kh_factor, shrinkage_strain
from core.materials import Concrete
from core.section import Layer, RectangularShape, ReinforcedSection, TShape

TABLE_A19_3_2 = {  # f_ck: ε_cd,0 (‰) para HR = 20, 40, 60, 80, 90, 100 %
    20: [0.62, 0.58, 0.49, 0.30, 0.17, 0.00], 40: [0.48, 0.46, 0.38, 0.24, 0.13, 0.00],
    60: [0.38, 0.36, 0.30, 0.19, 0.10, 0.00], 80: [0.30, 0.28, 0.24, 0.15, 0.08, 0.00],
    90: [0.27, 0.25, 0.21, 0.13, 0.07, 0.00],
}


@pytest.mark.parametrize("fck", list(TABLE_A19_3_2))
def test_shrinkage_formula_reproduces_table_a19_3_2(fck):
    c = Concrete(fck)
    for rh, tab in zip((20, 40, 60, 80, 90, 100), TABLE_A19_3_2[fck]):
        assert drying_shrinkage_basic(c, rh, "N") * 1000 == pytest.approx(tab, abs=0.0051)


def test_kh_table_a19_3_3():
    assert kh_factor(50) == 1.0
    assert kh_factor(100) == 1.0
    assert kh_factor(200) == 0.85
    assert kh_factor(300) == 0.75
    assert kh_factor(400) == pytest.approx(0.725)
    assert kh_factor(800) == 0.70


def test_creep_manual_b_formulas():
    c = Concrete(30)  # f_cm = 38 > 35 ⇒ (B.3b)
    RH, h0, t0 = 50.0, 150.0, 28.0
    a1, a2 = (35 / 38) ** 0.7, (35 / 38) ** 0.2
    phi_rh = (1 + (1 - 0.5) / (0.1 * h0 ** (1 / 3)) * a1) * a2
    phi0 = phi_rh * 16.8 / math.sqrt(38) / (0.1 + 28 ** 0.2)
    assert creep_coefficient(c, RH, h0, t0, "N") == pytest.approx(phi0, rel=1e-12)
    c25 = Concrete(25)  # f_cm = 33 ≤ 35 ⇒ (B.3a)
    phi_rh = 1 + 0.5 / (0.1 * h0 ** (1 / 3))
    assert creep_coefficient(c25, RH, h0, t0, "N") == pytest.approx(phi_rh * 16.8 / math.sqrt(33) / (0.1 + 28 ** 0.2))
    # cemento R: t0 corregido (B.9) mayor ⇒ menor fluencia
    assert creep_coefficient(c, RH, h0, t0, "R") < creep_coefficient(c, RH, h0, t0, "N")
    # desarrollo en el tiempo: φ(t) < φ(∞)
    assert creep_coefficient(c, RH, h0, t0, "N", t=365) < creep_coefficient(c, RH, h0, t0, "N")
    with pytest.raises(CreepError):
        creep_coefficient(c, 30, h0, t0)


def test_shrinkage_total_manual():
    c = Concrete(25)
    h0 = 200.0
    exp = 0.85 * drying_shrinkage_basic(c, 60) + 2.5 * 15 * 1e-6
    assert shrinkage_strain(c, 60, h0) == pytest.approx(exp)


@pytest.mark.parametrize("K,rho,tab", [(1.0, 0.015, 14), (1.0, 0.005, 20), (1.3, 0.015, 18), (1.3, 0.005, 26),
                                       (1.5, 0.015, 20), (1.5, 0.005, 30), (1.2, 0.015, 17), (1.2, 0.005, 24),
                                       (0.4, 0.015, 6), (0.4, 0.005, 8)])
def test_ld_reproduces_table_a19_7_4(K, rho, tab):
    v, _ = ld_limit(K, 30.0, rho, 0.0)
    assert v == pytest.approx(tab, abs=1.0)


def test_cracked_rectangular_closed_form():
    sec = ReinforcedSection(RectangularShape(300, 500), 30, 8, [Layer("inferior", 3, 20)])
    a = 200000 / Concrete(25).Ecm
    As, d, b = sec.area_on("inferior"), sec.d, 300
    rho = As / (b * d)
    x = a * rho * d * (math.sqrt(1 + 2 / (a * rho)) - 1)
    I = b * x ** 3 / 3 + a * As * (d - x) ** 2
    cr = cracked(sec, a)
    assert cr.yc == pytest.approx(x, rel=1e-9)
    assert cr.I == pytest.approx(I, rel=1e-9)


def test_uncracked_homogenized_manual():
    sec = ReinforcedSection(RectangularShape(300, 500), 30, 8, [Layer("inferior", 3, 20)])
    a = 6.0
    As, d = sec.area_on("inferior"), sec.d
    A = 300 * 500 + (a - 1) * As
    y = (300 * 500 * 250 + (a - 1) * As * d) / A
    I = 300 * 500 ** 3 / 12 + 300 * 500 * (250 - y) ** 2 + (a - 1) * As * (d - y) ** 2
    un = uncracked(sec, a)
    assert un.yc == pytest.approx(y) and un.I == pytest.approx(I)
    Mcr, _ = cracking_moment(sec, a, 2.565)
    assert Mcr == pytest.approx(2.565 * I / (500 - y))


L = [Layer("inferior", 3, 20), Layer("superior", 2, 12)]


def test_crack_width_chain_manual():
    r = crack_check(CrackInput(RectangularShape(300, 500), 30, 8, L, 100, "XC3"))
    R = r["result"]
    c = Concrete(25)
    a = 200000 / c.Ecm
    hc = min(2.5 * (500 - 452), (500 - R["x"]) / 3, 250)
    rho = 3 * math.pi * 100 / (300 * hc)
    de = max((R["sigma_s"] - 0.4 * c.fctm / rho * (1 + a * rho)) / 200000, 0.6 * R["sigma_s"] / 200000)
    sr = 3.4 * 38 + 0.8 * 0.5 * 0.425 * 20 / rho
    assert R["h_c_ef"] == pytest.approx(hc)
    assert R["w_k"] == pytest.approx(sr * de, rel=1e-9)
    assert R["w_max"] == 0.3
    assert r["ok"] is True


def test_uncracked_gives_zero_width_and_large_spacing_uses_7_14():
    r = crack_check(CrackInput(RectangularShape(300, 500), 30, 8, L, 20, "XC1"))
    assert r["result"]["w_k"] == 0.0
    wide = crack_check(CrackInput(RectangularShape(1000, 500), 30, 8, [Layer("inferior", 2, 25)], 150, "XC1"))
    step = next(s for s in wide["trace"]["steps"] if s["symbol"] == "s_r,max")
    assert "7.14" in step["reference"]


def test_wmax_table_and_stress_limits():
    assert WMAX_RC["XC1"] == 0.4 and WMAX_RC["XD2"] == 0.2 and WMAX_RC["XS3"] == 0.1
    r = crack_check(CrackInput(RectangularShape(300, 500), 30, 8, L, 100, "XD1", M_char_knm=220))
    names = {c["name"]: c for c in r["trace"]["checks"]}
    assert names["Tensión en la armadura (característica)"]["ok"] is False  # > 0,8·f_yk
    assert "Tensión de compresión en el hormigón (característica)" in names
    with pytest.raises(CrackInputError):
        crack_check(CrackInput(RectangularShape(300, 500), 30, 8, L, 100, "XZ9"))


def test_min_crack_reinforcement_7_1():
    r = crack_check(CrackInput(RectangularShape(300, 500), 30, 8, L, 100, "XC3"))
    c = Concrete(25)
    un = uncracked(ReinforcedSection(RectangularShape(300, 500), 30, 8, L), 200000 / c.Ecm)
    Act = 300 * (500 - un.yc)
    k = 1.0 + (0.65 - 1.0) * (500 - 300) / 500
    assert r["result"]["As_min_crack"] == pytest.approx(0.4 * k * c.fctm * Act / 500)
    t = crack_check(CrackInput(TShape(800, 120, 300, 600), 30, 8, L, -80, "XC3"))
    mn = next(c for c in t["trace"]["checks"] if c["name"] == "Armadura mínima de fisuración")
    assert mn["ok"] is None


def test_deflection_uncracked_closed_form_and_deferred():
    sec_layers = [Layer("inferior", 3, 20)]
    r = deflection_check(DeflectionInput(RectangularShape(300, 500), 30, 8, sec_layers, 5000, "biapoyada", 20,
                                         phi_override=2.0, eps_cs_override=0.0))
    C = r["result"]["calc"]
    assert C["zeta_long"] == 0 and C["zeta_inst"] == 0
    c = Concrete(25)
    sec = ReinforcedSection(RectangularShape(300, 500), 30, 8, sec_layers)
    I_s = uncracked(sec, 200000 / c.Ecm).I
    I_l = uncracked(sec, 200000 / (c.Ecm / 3)).I
    assert C["delta_inst"] == pytest.approx(5 / 48 * 5000 ** 2 * 20e6 / (c.Ecm * I_s))
    assert C["delta_total"] == pytest.approx(5 / 48 * 5000 ** 2 * 20e6 / (c.Ecm / 3 * I_l))
    assert C["delta_deferred"] == pytest.approx(C["delta_total"] - C["delta_inst"])


def test_deflection_cracked_and_limits():
    r = deflection_check(DeflectionInput(RectangularShape(300, 500), 30, 8, L, 6000, "biapoyada", 90, As_req=800))
    C = r["result"]["calc"]
    assert 0 < C["zeta_inst"] < C["zeta_long"] < 1  # β = 1,0 (instantánea) frente a β = 0,5
    assert C["limit_total"] == 24 and C["limit_deferred"] == 12
    assert C["delta_total"] > C["delta_inst"] > 0 and C["delta_cs"] > 0
    big = deflection_check(DeflectionInput(RectangularShape(300, 400), 30, 8, L, 9000, "biapoyada", 110, As_req=900))
    assert big["ok"] is False


def test_cantilever_and_custom_system():
    lay = [Layer("inferior", 2, 12), Layer("superior", 3, 16)]
    r = deflection_check(DeflectionInput(RectangularShape(300, 450), 30, 8, lay, 2000, "voladizo", -40))
    assert r["result"]["calc"]["kM"] == 0.25
    with pytest.raises(DeflectionInputError):
        deflection_check(DeflectionInput(RectangularShape(300, 450), 30, 8, lay, 2000, "voladizo", 40))
    r = deflection_check(DeflectionInput(RectangularShape(300, 500), 30, 8, L, 6000, "continua_interior", 60))
    assert r["result"]["calc"] is None
    r = deflection_check(DeflectionInput(RectangularShape(300, 500), 30, 8, L, 6000, "continua_interior", 60,
                                         kM=0.06, kcs=0.0625))
    assert r["result"]["calc"]["kM"] == 0.06


def test_ld_corrections_t_and_long_span():
    lay = [Layer("inferior", 4, 20)]
    base = deflection_check(DeflectionInput(TShape(1200, 120, 300, 600), 30, 8, lay, 8000, "biapoyada", 0, As_req=1000))
    frag = deflection_check(DeflectionInput(TShape(1200, 120, 300, 600), 30, 8, lay, 8000, "biapoyada", 0, As_req=1000,
                                            fragile_partitions=True))
    assert frag["result"]["ld"]["limit"] == pytest.approx(base["result"]["ld"]["limit"] * 7 / 8)
    steps = [s for s in base["trace"]["steps"] if s["title"] == "Corrección por sección en T"]
    assert steps and steps[0]["result"] == 0.8
