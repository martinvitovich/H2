"""Método general de flexión: contraste con soluciones cerradas independientes.

Las soluciones de referencia se obtienen aquí por integración analítica del
diagrama parábola-rectángulo (cálculo manual independiente), no a partir del
código del motor:

    k = ε_c2/ε_cu2 ;  α = 1 − k/(n+1)  (resultante: α·b·x·f_cd)
    para n = 2: β = 1 − [5k²/12 + (1 − k²)/2]/α  (profundidad de la resultante: β·x)

Para k = 2/3,5 se obtiene α = 17/21 ≈ 0,8095 y β = 99/238 ≈ 0,4160.
"""

import math

import pytest

from core.elu.analysis import AnalysisError, _concrete_pr, analyse_bending
from core.materials import Concrete, ReinforcingSteel
from core.section import Layer, RectangularShape, ReinforcedSection, TShape


def alpha_beta_n2(k):
    a = 1 - k / 3
    vbar = (5 * k * k / 12 + (1 - k * k) / 2) / a
    return a, 1 - vbar


def test_closed_form_constants():
    a, b = alpha_beta_n2(2 / 3.5)
    assert a == pytest.approx(17 / 21, rel=1e-12)
    assert b == pytest.approx(99 / 238, rel=1e-12)


@pytest.mark.parametrize("fck", [25, 50, 70, 90])
def test_concrete_resultant_vs_closed_form(fck):
    c = Concrete(fck)
    x, bw = 200.0, 300.0
    seg = RectangularShape(bw, 1000).segments()
    F, M = _concrete_pr(seg, c, x, c.eps_cu2, 1000)
    k = c.eps_c2 / c.eps_cu2
    alpha = 1 - k / (c.n + 1)
    assert F == pytest.approx(alpha * bw * x * c.fcd, rel=1e-9)
    if c.n == 2:
        _, beta = alpha_beta_n2(k)
        assert M / F == pytest.approx(beta * x, rel=1e-9)


def _rect(As_layers, b=300, h=500):
    return ReinforcedSection(RectangularShape(b, h), 30, 8, As_layers)


def test_single_reinforced_parabola_rectangle_manual():
    c, s = Concrete(25), ReinforcingSteel.from_grade("B500S")
    sec = _rect([Layer("inferior", 4, 16)])
    As, d = sec.area_on("inferior"), sec.d
    alpha, beta = alpha_beta_n2(2 / 3.5)
    x = As * s.fyd / (alpha * 300 * c.fcd)
    M = As * s.fyd * (d - beta * x)
    assert (d - x) / x * 0.0035 > s.eps_yd  # hipótesis de cedencia del cálculo manual
    r = analyse_bending(sec, c, s, 1, "parabola-rectangulo")
    assert r.x == pytest.approx(x, rel=1e-8)
    assert r.M_Rd == pytest.approx(M, rel=1e-8)
    assert abs(r.residual_N) < 1e-3  # N (tolerancia de equilibrio: 1 mN)
    assert r.pivot == "B"


def test_single_reinforced_block_manual():
    c, s = Concrete(25), ReinforcingSteel.from_grade("B500S")
    sec = _rect([Layer("inferior", 4, 16)])
    As, d = sec.area_on("inferior"), sec.d
    y = As * s.fyd / (300 * c.fcd)       # λx
    M = As * s.fyd * (d - y / 2)
    r = analyse_bending(sec, c, s, 1, "rectangular")
    assert r.x * c.lam == pytest.approx(y, rel=1e-8)
    assert r.M_Rd == pytest.approx(M, rel=1e-8)


def test_methods_agree_within_one_percent():
    c, s = Concrete(30), ReinforcingSteel.from_grade("B500S")
    sec = _rect([Layer("inferior", 3, 20), Layer("superior", 2, 12)])
    a = analyse_bending(sec, c, s, 1, "parabola-rectangulo").M_Rd
    b = analyse_bending(sec, c, s, 1, "rectangular").M_Rd
    assert a == pytest.approx(b, rel=0.01)


def test_symmetric_section_symmetric_capacity():
    c, s = Concrete(30), ReinforcingSteel.from_grade("B500S")
    sec = _rect([Layer("inferior", 3, 16), Layer("superior", 3, 16)])
    rp = analyse_bending(sec, c, s, 1)
    rn = analyse_bending(sec, c, s, -1)
    assert rp.M_Rd == pytest.approx(-rn.M_Rd, rel=1e-9)


def test_equilibrium_and_moment_independent_of_reference():
    c, s = Concrete(35), ReinforcingSteel.from_grade("B500S")
    sec = _rect([Layer("inferior", 4, 20), Layer("superior", 2, 16)])
    r = analyse_bending(sec, c, s, 1)
    total = r.Fc - sum(b.force for b in r.bars)
    assert abs(total) < 1e-3
    # momento respecto a la armadura inferior: debe coincidir con el de la fibra superior
    yref = max(b.y for b in r.bars)
    M_ref = r.Fc * (yref - r.zc) - sum(b.force * (yref - b.y) for b in r.bars)
    # (el desplazamiento de hormigón está incluido en b.force; residuo ~0)
    assert M_ref == pytest.approx(r.M_Rd, rel=1e-8)


def test_t_section_flange_only_equals_rectangle():
    c, s = Concrete(25), ReinforcingSteel.from_grade("B500S")
    t = ReinforcedSection(TShape(800, 150, 300, 600), 30, 8, [Layer("inferior", 3, 16)])
    r = ReinforcedSection(RectangularShape(800, 600), 30, 8, [Layer("inferior", 3, 16)])
    # mismas barras: en la T las barras están en el alma, en el rectángulo repartidas;
    # el canto útil coincide y solo importa la profundidad.
    rt, rr = analyse_bending(t, c, s, 1), analyse_bending(r, c, s, 1)
    assert rt.x < 150
    assert rt.M_Rd == pytest.approx(rr.M_Rd, rel=1e-9)


def test_t_section_neutral_axis_in_web_manual_block():
    c, s = Concrete(25), ReinforcingSteel.from_grade("B500S")
    sec = ReinforcedSection(TShape(500, 80, 300, 600), 30, 8, [Layer("inferior", 4, 25)])
    As, d = sec.area_on("inferior"), sec.d
    T = As * s.fyd
    Ff = c.fcd * (500 - 300) * 80          # vuelos del ala
    y = (T - Ff) / (c.fcd * 300)            # λx en el alma (λx > hf)
    assert y > 80
    x = y / c.lam
    assert 0.0035 * (d - x) / x > s.eps_yd  # hipótesis: la armadura plastifica
    M = Ff * (d - 40) + c.fcd * 300 * y * (d - y / 2)
    r = analyse_bending(sec, c, s, 1, "rectangular")
    assert not r.eta_reduction
    assert r.M_Rd == pytest.approx(M, rel=1e-8)


def test_eta_reduction_for_inverted_t():
    c, s = Concrete(25), ReinforcingSteel.from_grade("B500S")
    sec = ReinforcedSection(TShape(800, 120, 250, 600), 30, 8,
                            [Layer("inferior", 3, 16), Layer("superior", 6, 20)])
    # momento negativo: zona comprimida = alma (ancho constante) → sin reducción
    r = analyse_bending(sec, c, s, -1, "rectangular")
    assert r.eta_reduction is False


def test_inclined_branch_pivot_a():
    c = Concrete(30)
    s = ReinforcingSteel.from_grade("B500S", branch="inclinada")
    sec = _rect([Layer("inferior", 2, 10)], b=1000, h=300)
    r = analyse_bending(sec, c, s, 1)
    assert r.pivot == "A"
    deepest = max(r.bars, key=lambda b: b.y)
    assert deepest.strain == pytest.approx(s.eps_ud, rel=1e-6)
    with pytest.raises(AnalysisError):
        analyse_bending(sec, c, s, 1, "rectangular")


def test_inclined_branch_increases_capacity_when_pivot_b():
    c = Concrete(30)
    sec = _rect([Layer("inferior", 3, 16)])
    rh = analyse_bending(sec, c, ReinforcingSteel.from_grade("B500SD"), 1)
    ri = analyse_bending(sec, c, ReinforcingSteel.from_grade("B500SD", branch="inclinada"), 1)
    assert ri.M_Rd >= rh.M_Rd


def test_no_tension_steel_raises():
    c, s = Concrete(25), ReinforcingSteel.from_grade("B500S")
    sec = _rect([Layer("inferior", 2, 12)])
    with pytest.raises(AnalysisError):
        analyse_bending(sec, c, s, -1)


def test_capacity_monotonic_in_steel_area():
    c, s = Concrete(25), ReinforcingSteel.from_grade("B500S")
    m = [analyse_bending(_rect([Layer("inferior", n, 16)]), c, s, 1).M_Rd for n in (2, 3, 4, 5)]
    assert all(b > a for a, b in zip(m, m[1:]))
