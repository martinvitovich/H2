"""Cortante (Anejo 19, 6.2 y 9.2.2): cálculos manuales independientes.

Las expresiones de referencia se han transcrito del texto oficial (BOE págs. 98359-98364 y
98428). No se dispone de un ejemplo resuelto bibliográfico verificable: los valores
esperados se calculan aquí a mano a partir de las expresiones del Anejo.
"""

import math

import pytest

from core.elu.cortante import (ShearInput, ShearInputError, cot_theta_max_vrdmax, shear_beam, vrd_max, vrd_s,
                               vrdc)
from core.materials import Concrete
from core.parameters import ParameterSet
from core.section import Layer, RectangularShape, TShape

L = [Layer("inferior", 3, 20), Layer("superior", 2, 12)]
RECT = RectangularShape(300, 500)


def inp(**kw):
    base = dict(shape=RECT, cover=30, stirrup_diameter=8, layers=L, V_Ed_kn=150)
    base.update(kw)
    return ShearInput(**base)


def test_vrdc_manual():
    c = Concrete(25)
    d, bw, Asl = 452.0, 300.0, 3 * math.pi * 100
    k = 1 + math.sqrt(200 / d)
    rho = Asl / (bw * d)
    expected = 0.18 / 1.5 * k * (100 * rho * 25) ** (1 / 3) * bw * d
    r = vrdc(c, bw, d, Asl, 0.0, 150000.0, ParameterSet())
    assert r["VRdc"] == pytest.approx(expected, rel=1e-12)
    assert r["VRdc"] / 1e3 == pytest.approx(70.18, abs=0.005)


def test_vrdc_minimum_governs_with_low_reinforcement():
    c = Concrete(30)
    d, bw = 200.0, 1000.0
    r = vrdc(c, bw, d, 100.0, 0.0, bw * 250, ParameterSet())
    k = 2.0  # 1 + √(200/200) = 2
    vmin = 0.035 * k ** 1.5 * math.sqrt(30)
    assert r["k"] == 2.0
    assert r["VRdc"] == pytest.approx(vmin * bw * d)


def test_vrdc_caps():
    c = Concrete(25)
    r = vrdc(c, 300, 450, 0.05 * 300 * 450, 1e7, 150000, ParameterSet())
    assert r["rho_l"] == 0.02
    assert r["sigma_cp"] == pytest.approx(0.2 * c.fcd)
    assert vrdc(c, 300, 50, 1000, 0, 1e5, ParameterSet())["k"] == 2.0


def test_axial_compression_increases_vrdc_and_tension_decreases():
    c = Concrete(25)
    base = vrdc(c, 300, 450, 942, 0.0, 150000, ParameterSet())["VRdc"]
    comp = vrdc(c, 300, 450, 942, 300e3, 150000, ParameterSet())["VRdc"]
    tens = vrdc(c, 300, 450, 942, -300e3, 150000, ParameterSet())["VRdc"]
    assert comp == pytest.approx(base + 0.15 * 2.0 * 300 * 450)
    assert tens < base


def test_vrdmax_alpha90_matches_6_9():
    bw, z, nu, fcd = 300, 400, 0.54, 16.67
    for c in (0.5, 1.0, 1.5, 2.0):
        t = 1 / c
        assert vrd_max(c, 0.0, bw, z, nu, fcd, 1.0) == pytest.approx(bw * z * nu * fcd / (c + t))


def test_cot_theta_star():
    assert cot_theta_max_vrdmax(0.0, 0.5, 2.0) == pytest.approx(1.0)
    ca = 1 / math.tan(math.radians(45))
    assert cot_theta_max_vrdmax(ca, 0.5, 2.0) == pytest.approx(max(-1 + math.sqrt(2), 0.5))


def test_design_uses_max_cot_theta_and_satisfies_equilibrium():
    r = shear_beam(inp(V_Ed_kn=150))
    R = r["result"]
    assert r["ok"] is True
    assert R["cot_theta"] == 2.0
    z = 0.9 * 452
    req = 150e3 / (z * 500 / 1.15 * 2.0)
    assert R["Asw_s_req"] == pytest.approx(req)
    s = R["proposal"]["spacing"]
    assert s % 25 == 0
    assert vrd_s(2 * math.pi * 16 / s, 2.0, 0, 1, z, 500 / 1.15) >= 150e3


def test_design_theta_from_vrdmax_when_needed():
    r = shear_beam(inp(V_Ed_kn=450))
    R = r["result"]
    assert 1.0 < R["cot_theta"] < 2.0
    assert R["VRd_max"] == pytest.approx(450e3, rel=1e-9)  # V_Ed = V_Rd,max con el θ adoptado


def test_design_crushing_fails():
    r = shear_beam(inp(V_Ed_kn=700))
    assert r["ok"] is False
    assert r["result"]["proposal"] is None
    crush = next(c for c in r["trace"]["checks"] if c["name"].startswith("Compresión oblicua"))
    assert crush["ok"] is False


def test_minimum_reinforcement_when_vrdc_suffices():
    r = shear_beam(inp(V_Ed_kn=40))
    R = r["result"]
    assert R["needs_shear_reinforcement"] is False
    rho_min = 0.08 * math.sqrt(25) / 500
    assert R["rho_w_min"] == pytest.approx(rho_min)
    assert R["Asw_s_design"] == pytest.approx(rho_min * 300)
    assert R["proposal"]["spacing"] <= R["s_l_max"]


def test_check_optimal_theta_and_failure():
    r = shear_beam(inp(V_Ed_kn=250, mode="check", stirrup_spacing=150))
    R = r["result"]
    assert R["cot_theta"] == 2.0
    z = 0.9 * 452
    assert R["VRd_s"] == pytest.approx(2 * math.pi * 16 / 150 * z * 500 / 1.15 * 2.0)
    assert r["ok"] is False
    r2 = shear_beam(inp(V_Ed_kn=200, mode="check", stirrup_spacing=150))
    assert r2["ok"] is True


def test_check_intersection_theta():
    # mucha armadura → el óptimo es la igualdad V_Rd,s = V_Rd,max con 1 < cot θ < 2
    r = shear_beam(inp(V_Ed_kn=300, mode="check", stirrup_spacing=60, stirrup_diameter=10))
    R = r["result"]
    assert 1.0 < R["cot_theta"] < 2.0
    assert R["VRd_s"] == pytest.approx(R["VRd_max"], rel=1e-9)


def test_inclined_stirrups_formulas():
    r = shear_beam(inp(V_Ed_kn=200, alpha_deg=60, mode="check", stirrup_spacing=150))
    R = r["result"]
    ca, sa = 1 / math.tan(math.radians(60)), math.sin(math.radians(60))
    z = 0.9 * 452
    exp_s = 2 * math.pi * 16 / 150 * z * 500 / 1.15 * (R["cot_theta"] + ca) * sa
    assert R["VRd_s"] == pytest.approx(exp_s)
    assert R["s_l_max"] == pytest.approx(0.75 * 452 * (1 + ca))


def test_nu1_simplified_6_10():
    r = shear_beam(inp(V_Ed_kn=200, nu1_simplified=True))
    assert r["result"]["nu1"] == 0.6
    assert r["result"]["fywd"] == pytest.approx(0.8 * 500)
    c80 = shear_beam(inp(V_Ed_kn=200, nu1_simplified=True, concrete_class="C80/95"))
    assert c80["result"]["nu1"] == pytest.approx(0.9 - 80 / 200)


def test_spacing_limits_and_legs():
    r = shear_beam(inp(V_Ed_kn=100, mode="check", stirrup_spacing=400))
    sl = next(c for c in r["trace"]["checks"] if c["name"].startswith("Separación longitudinal"))
    assert sl["ok"] is False  # 0,75·452 = 339 mm
    wide = shear_beam(inp(shape=RectangularShape(1200, 500), V_Ed_kn=100))
    st = next(c for c in wide["trace"]["checks"] if c["name"].startswith("Separación transversal"))
    assert st["ok"] is False  # (1200 − 68)/1 > 0,75·d


def test_t_section_uses_web_width():
    r = shear_beam(inp(shape=TShape(800, 120, 250, 600), V_Ed_kn=200))
    assert r["result"]["VRdc"]["rho_l"] == pytest.approx(3 * math.pi * 100 / (250 * r["result"]["geometry"]["d_inferior"]))


@pytest.mark.parametrize("kw", [dict(V_Ed_kn=-5), dict(alpha_deg=30), dict(stirrup_legs=1),
                                dict(mode="check"), dict(cot_theta=2.5), dict(tension_face="lateral"),
                                dict(layers=[Layer("superior", 2, 12)])])
def test_invalid_inputs(kw):
    with pytest.raises(ShearInputError):
        shear_beam(inp(**kw))


def test_trace_references_official():
    r = shear_beam(inp())
    tr = r["trace"]
    assert all(s["reference"] for s in tr["steps"])
    assert any("6.2.2(1)" in s["reference"] for s in tr["steps"])
    assert any(p["key"] == "cot_theta_min" and p["value"] == 0.5 for p in tr["parameters_used"])
