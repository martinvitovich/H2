"""Materiales.

Referencia de contraste: tabla A19.3.1 del texto oficial del Anejo 19 (BOE n.º 190,
10/08/2021, pág. 98308), cotejada con el PDF del BOE. Las tolerancias corresponden a
medio dígito del redondeo de la tabla (p. ej. 0,05 MPa para valores con un decimal).

Nota sobre f_ctk,0,05: la tabla da 3,1 MPa para C60/75, mientras que 0,7·f_ctm (con f_ctm
sin redondear = 4,355) da 3,048. El valor tabulado se obtiene aplicando 0,7 a la f_ctm ya
redondeada (0,7·4,4 = 3,08). Por eso esa fila se contrasta con tolerancia de 0,06 MPa.
"""

import math

import pytest

from core.materials import CONCRETE_FCK_CLASSES, Concrete, MaterialError, ReinforcingSteel, stress_strain_curves
from core.parameters import ParameterSet

#            fck  fctm  fctk05  Ecm(GPa) eps_c1 eps_cu1 eps_c2 eps_cu2  n    eps_c3
TABLE_3_1 = [
    (12, 1.6, 1.1, 27, 1.8, 3.5, 2.0, 3.5, 2.0, 1.75),
    (16, 1.9, 1.3, 29, 1.9, 3.5, 2.0, 3.5, 2.0, 1.75),
    (20, 2.2, 1.5, 30, 2.0, 3.5, 2.0, 3.5, 2.0, 1.75),
    (25, 2.6, 1.8, 31, 2.1, 3.5, 2.0, 3.5, 2.0, 1.75),
    (30, 2.9, 2.0, 33, 2.2, 3.5, 2.0, 3.5, 2.0, 1.75),
    (35, 3.2, 2.2, 34, 2.25, 3.5, 2.0, 3.5, 2.0, 1.75),
    (40, 3.5, 2.5, 35, 2.3, 3.5, 2.0, 3.5, 2.0, 1.75),
    (45, 3.8, 2.7, 36, 2.4, 3.5, 2.0, 3.5, 2.0, 1.75),
    (50, 4.1, 2.9, 37, 2.45, 3.5, 2.0, 3.5, 2.0, 1.75),
    (55, 4.2, 3.0, 38, 2.5, 3.2, 2.2, 3.1, 1.75, 1.8),
    (60, 4.4, 3.1, 39, 2.6, 3.0, 2.3, 2.9, 1.6, 1.9),
    (70, 4.6, 3.2, 41, 2.7, 2.8, 2.4, 2.7, 1.45, 2.0),
    (80, 4.8, 3.4, 42, 2.8, 2.8, 2.5, 2.6, 1.4, 2.2),
    (90, 5.0, 3.5, 44, 2.8, 2.8, 2.6, 2.6, 1.4, 2.3),
]


@pytest.mark.parametrize("row", TABLE_3_1, ids=lambda r: f"fck{r[0]}")
def test_table_3_1_formulas_reproduce_tabulated_values(row):
    fck, fctm, fctk05, Ecm, ec1, ecu1, ec2, ecu2, n, ec3 = row
    c = Concrete(fck)
    assert c.fcm == fck + 8
    assert c.fctm == pytest.approx(fctm, abs=0.051)
    assert c.fctk_005 == pytest.approx(fctk05, abs=0.06)
    assert c.fctk_005 == pytest.approx(0.7 * c.fctm)
    assert c.fctk_095 == pytest.approx(1.3 * c.fctm)
    assert c.Ecm / 1000 == pytest.approx(Ecm, abs=0.51)
    assert c.eps_c1 * 1000 == pytest.approx(ec1, abs=0.051)
    assert c.eps_cu1 * 1000 == pytest.approx(ecu1, abs=0.051)
    assert c.eps_c2 * 1000 == pytest.approx(ec2, abs=0.051)
    assert c.eps_cu2 * 1000 == pytest.approx(ecu2, abs=0.051)
    assert c.n == pytest.approx(n, abs=0.051)
    assert c.eps_c3 * 1000 == pytest.approx(ec3, abs=0.051)
    assert c.eps_cu3 == c.eps_cu2


def test_all_classes_constructible():
    for name in CONCRETE_FCK_CLASSES:
        assert Concrete.from_class(name).name == name


def test_design_strengths_manual():
    c = Concrete.from_class("C25/30")
    assert c.fcd == pytest.approx(1.0 * 25 / 1.5)
    assert c.fctd == pytest.approx(0.7 * 0.30 * 25 ** (2 / 3) / 1.5)
    acc = Concrete(25, situation="accidental")
    assert acc.fcd == pytest.approx(25 / 1.3)
    c85 = Concrete(25, ParameterSet({"alpha_cc": 0.85}))
    assert c85.fcd == pytest.approx(0.85 * 25 / 1.5)


def test_rectangular_block_factors():
    assert Concrete(30).lam == 0.8 and Concrete(30).eta == 1.0
    assert Concrete(70).lam == pytest.approx(0.8 - 20 / 400)
    assert Concrete(70).eta == pytest.approx(1.0 - 20 / 200)


def test_parabola_rectangle_shape():
    c = Concrete(30)
    assert c.sigma_parabola_rectangle(-0.001) == 0.0
    assert c.sigma_parabola_rectangle(0.0) == 0.0
    # n = 2: σ(ε_c2/2) = f_cd·(1 − 0,25)
    assert c.sigma_parabola_rectangle(0.001) == pytest.approx(0.75 * c.fcd)
    assert c.sigma_parabola_rectangle(0.002) == pytest.approx(c.fcd)
    assert c.sigma_parabola_rectangle(0.0035) == pytest.approx(c.fcd)
    with pytest.raises(MaterialError):
        c.sigma_parabola_rectangle(0.004)


def test_nonlinear_curve_peak_at_eps_c1():
    c = Concrete(30)
    assert c.sigma_nonlinear_analysis(c.eps_c1) == pytest.approx(c.fcm)
    # pendiente inicial ≈ 1,05·E_cm (derivada en el origen de (3.14))
    e = 1e-7
    assert c.sigma_nonlinear_analysis(e) / e == pytest.approx(1.05 * c.Ecm, rel=1e-3)


@pytest.mark.parametrize("fck", [10, 95, -5])
def test_invalid_concrete(fck):
    with pytest.raises(MaterialError):
        Concrete(fck)


def test_unknown_class():
    with pytest.raises(MaterialError):
        Concrete.from_class("C27/33")


def test_steel_horizontal_branch():
    s = ReinforcingSteel.from_grade("B500S")
    assert s.fyd == pytest.approx(500 / 1.15)
    assert s.eps_yd == pytest.approx(500 / 1.15 / 200000)
    assert s.eps_ud is None
    assert s.sigma(0.001) == pytest.approx(200.0)
    assert s.sigma(0.05) == pytest.approx(s.fyd)
    assert s.sigma(-0.05) == pytest.approx(-s.fyd)
    # continuidad en ε_yd
    assert s.sigma(s.eps_yd) == pytest.approx(s.fyd)


def test_steel_inclined_branch():
    s = ReinforcingSteel.from_grade("B500SD", branch="inclinada")
    assert s.eps_ud == pytest.approx(0.9 * 0.075)
    assert s.sigma(s.eps_uk * 0.9) < s.ftd_max
    expected = s.fyd + (s.ftd_max - s.fyd) * (s.eps_ud - s.eps_yd) / (s.eps_uk - s.eps_yd)
    assert s.sigma(s.eps_ud) == pytest.approx(expected)
    with pytest.raises(MaterialError):
        s.sigma(s.eps_ud * 1.01)


def test_eps_c2_errata_in_official_formula():
    """La tabla A19.3.1 imprime 2,0 + 0,85·(f_ck − 50)^0,53, pero sus valores tabulados
    (2,2 / 2,3 / 2,4 / 2,5 / 2,6 ‰ para C55…C90) solo se reproducen con 0,085."""
    for fck, tab in [(55, 2.2), (60, 2.3), (70, 2.4), (80, 2.5), (90, 2.6)]:
        assert 2.0 + 0.085 * (fck - 50) ** 0.53 == pytest.approx(tab, abs=0.051)
        assert abs(2.0 + 0.85 * (fck - 50) ** 0.53 - tab) > 1.0
        assert Concrete(fck).eps_c2 * 1000 == pytest.approx(tab, abs=0.051)


def test_fctm_fl_expression_3_23():
    c = Concrete(25)
    assert c.fctm_fl(500) == pytest.approx(1.1 * c.fctm)
    assert c.fctm_fl(600) == pytest.approx(1.0 * c.fctm)
    assert c.fctm_fl(800) == pytest.approx(c.fctm)  # el máximo con f_ctm


def test_aggregate_factors_3_1_3():
    base = Concrete(30).Ecm
    assert Concrete(30, aggregate="calizo").Ecm == pytest.approx(0.9 * base)
    assert Concrete(30, aggregate="arenisca").Ecm == pytest.approx(0.7 * base)
    assert Concrete(30, aggregate="basaltico").Ecm == pytest.approx(1.2 * base)
    with pytest.raises(MaterialError):
        Concrete(30, aggregate="granito")


def test_alpha_ct_fixed_and_alpha_cc_range():
    from core.parameters import ParameterError
    with pytest.raises(ParameterError):
        ParameterSet({"alpha_ct": 0.9})
    with pytest.raises(ParameterError):
        ParameterSet({"alpha_cc": 0.8})
    assert Concrete(25, ParameterSet({"alpha_cc": 0.85})).fcd == pytest.approx(0.85 * 25 / 1.5)


def test_invalid_steel():
    with pytest.raises(MaterialError):
        ReinforcingSteel(300, 0.05, 1.08)
    with pytest.raises(MaterialError):
        ReinforcingSteel(600, 0.05, 1.08)  # 3.2.2(3): 400 ≤ f_yk ≤ 500
    with pytest.raises(MaterialError):
        ReinforcingSteel.from_grade("B600X")
    with pytest.raises(MaterialError):
        ReinforcingSteel(500, 0.05, 1.08, branch="curva")  # type: ignore[arg-type]


def test_curves_are_monotonic_non_decreasing():
    cur = stress_strain_curves(Concrete(30), ReinforcingSteel.from_grade("B500S"))
    for key in ("concrete_design", "steel_design"):
        s = [p["sigma"] for p in cur[key]]
        assert all(b >= a - 1e-9 for a, b in zip(s, s[1:]))
