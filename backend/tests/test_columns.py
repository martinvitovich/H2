"""Pilares (5.2, 5.8, 6.1(4), 9.5): cálculos manuales independientes con las expresiones del
texto oficial (BOE págs. 98330, 98340-98348, 98357, 98433-98435). Sin ejemplo bibliográfico
verificable: validación independiente pendiente."""

import math

import pytest

from core.elu.pilares import ColumnInput, ColumnInputError, column_check
from core.materials import Concrete, ReinforcingSteel
from core.section import Layer

L = [Layer("inferior", 3, 16), Layer("superior", 3, 16), Layer("lateral", 1, 16)]


def col(**kw):
    base = dict(b=400, h=400, cover=35, stirrup_diameter=8, layers=L, N_Ed_kn=1500, M01_knm=0.0, M02_knm=0.0,
                length=3000, phi_ef=1.0, stirrup_spacing=200)
    base.update(kw)
    return ColumnInput(**base)


def test_slenderness_and_limit_manual():
    r = column_check(col(M01_knm=20, M02_knm=40, N_Ed_kn=1200))
    R = r["result"]
    assert R["lambda"] == pytest.approx(3000 * math.sqrt(12) / 400)
    c, s = Concrete(25), ReinforcingSteel.from_grade("B500S")
    As = 8 * math.pi * 64
    w = As * s.fyd / (160000 * c.fcd)
    n = 1.2e6 / (160000 * c.fcd)
    lim = 20 * (1 / (1 + 0.2)) * math.sqrt(1 + 2 * w) * (1.7 - 0.5) / math.sqrt(n)
    assert R["lambda_lim"] == pytest.approx(lim)
    assert R["second_order"] is False and R["M2"] == 0


def test_imperfection_and_first_order_manual():
    r = column_check(col(M01_knm=20, M02_knm=40, N_Ed_kn=1200, length=5000))
    R = r["result"]
    ah = max(2 / math.sqrt(5.0), 2 / 3)
    ei = (1 / 200) * ah * 1.0 * 5000 / 2
    assert R["e_i"] == pytest.approx(ei)
    M0e = max(0.6 * 40e6 + 0.4 * 20e6, 0.4 * 40e6)
    assert R["M0e"] == pytest.approx(M0e)
    assert R["M0Ed"] == pytest.approx(M0e + 1.2e6 * ei)


def test_ei_simplified_and_e0():
    R = column_check(col(ei_simplified=True))["result"]
    assert R["e_i"] == pytest.approx(3000 / 400)
    assert R["e_0"] == 20.0
    R = column_check(col(b=700, h=700, ei_simplified=True))["result"]
    assert R["e_0"] == pytest.approx(700 / 30)


def test_nominal_curvature_chain_manual():
    r = column_check(col())  # M01 = M02 = 0 ⇒ momento de primer orden constante ⇒ c = 8
    R = r["result"]
    c, s = Concrete(25), ReinforcingSteel.from_grade("B500S")
    As = 8 * math.pi * 64
    w = As * s.fyd / (160000 * c.fcd)
    n = 1.5e6 / (160000 * c.fcd)
    lam = 3000 * math.sqrt(12) / 400
    ys = [400 - 51] * 3 + [51] * 3 + [200] * 2   # 35 + 8 + 8 = 51 mm al eje de las barras
    i_s = math.sqrt(sum((y - 200) ** 2 for y in ys) / 8)
    d = 200 + i_s
    inv_r0 = s.eps_yd / (0.45 * d)
    Kr = min((1 + w - n) / (1 + w - 0.4), 1)
    Kphi = max(1 + (0.35 + 25 / 200 - lam / 150) * 1.0, 1)
    e2 = Kr * Kphi * inv_r0 * 3000 ** 2 / 8
    assert R["M2"] == pytest.approx(1.5e6 * e2, rel=1e-9)
    assert R["MEd_crit"] == pytest.approx(max(1.5e6 * 3000 / 400 + 1.5e6 * e2, 1.5e6 * 20))


def test_l0_from_k_braced_and_unbraced():
    R = column_check(col(l0_mode="k", k1=0.2, k2=0.4, beta=None))["result"]
    exp = 0.5 * 3000 * math.sqrt((1 + 0.2 / 0.65) * (1 + 0.4 / 0.85))
    assert R["l0"] == pytest.approx(exp)
    R = column_check(col(l0_mode="k", k1=0.2, k2=0.4, beta=None, braced=False))["result"]
    exp = 3000 * max(math.sqrt(1 + 10 * 0.08 / 0.6), (1 + 0.2 / 1.2) * (1 + 0.4 / 1.4))
    assert R["l0"] == pytest.approx(exp)


def test_unbraced_rm_is_one():
    r = column_check(col(braced=False, M01_knm=-30, M02_knm=60, beta=2.0))
    step = next(s for s in r["trace"]["steps"] if s["title"] == "Coeficientes de la esbeltez límite")
    assert "r_m = 1,0" in step["substitution"]


def test_missing_creep_is_not_declared_ok():
    r = column_check(col(phi_ef=None, N_Ed_kn=2500, M01_knm=30, M02_knm=60, length=4000))
    assert r["result"]["second_order"] is True
    assert r["ok"] is None


def test_asymmetric_reinforcement_second_order_not_evaluable():
    lay = [Layer("inferior", 3, 20), Layer("superior", 3, 16)]
    r = column_check(col(layers=lay, length=5000))
    assert r["result"]["second_order"] is True
    assert r["ok"] is None


def test_capacity_failure_and_axial_failure():
    r = column_check(col(M01_knm=200, M02_knm=200))
    assert r["ok"] is False
    r = column_check(col(N_Ed_kn=5000))
    assert r["ok"] is False


def test_detailing_rules_9_5():
    r = column_check(col(layers=[Layer("inferior", 2, 10), Layer("superior", 2, 10)], N_Ed_kn=800, stirrup_spacing=200))
    names = {c["name"]: c for c in r["trace"]["checks"]}
    assert names["Diámetro mínimo de las barras longitudinales"]["ok"] is False
    assert names["Separación de la armadura transversal"]["ok"] is False  # 15·10 = 150 < 200
    face_min = 0.05 * 800e3 / 400  # f_yc,d = min(434,8; 400)
    assert names["Armadura mínima en la cara superior"]["capacity"].startswith("A′_s,min = 100")
    assert face_min == 100
    r = column_check(col(layers=[Layer("inferior", 3, 16), Layer("superior", 3, 16)], b=600, h=600))
    tie = next(c for c in r["trace"]["checks"] if c["name"] == "Sujeción de las barras comprimidas")
    assert tie["ok"] is False  # barra central a 249 mm de las de esquina
    r = column_check(col(layers=[Layer("inferior", 3, 16), Layer("superior", 3, 16)], b=600, h=600,
                         intermediate_bars_tied=True))
    tie = next(c for c in r["trace"]["checks"] if c["name"] == "Sujeción de las barras comprimidas")
    assert tie["ok"] is True


@pytest.mark.parametrize("kw", [dict(N_Ed_kn=0), dict(b=100, h=500), dict(l0_mode="k", k1=None),
                                dict(transverse_load=True), dict(ei_simplified=True, braced=False),
                                dict(beta=0), dict(length=-1)])
def test_invalid(kw):
    with pytest.raises(ColumnInputError):
        column_check(col(**kw))


def test_diagram_and_points_in_result():
    R = column_check(col(M01_knm=20, M02_knm=40))["result"]
    assert len(R["diagram"]) > 50
    assert R["design_points"][0]["N_kN"] == 1500
