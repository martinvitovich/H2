"""Materiales.

Referencia de contraste: valores tabulados (redondeados) de la tabla 3.1 de la
EN 1992-1-1:2004, que el Anejo 19 transpone. Los valores se han transcrito de
memoria técnica del autor del software y NO se han cotejado con el texto oficial
del Anejo 19 (no accesible desde el entorno de desarrollo): COTEJO PENDIENTE (ver
docs/normativa.md). Se omite la fila f_ctk,0,05 porque no se pudo confirmar su
transcripción; esa magnitud se comprueba mediante su relación analítica 0,7·f_ctm. Las tolerancias corresponden a medio dígito del redondeo de la
tabla (p. ej. 0,05 MPa para f_ctm tabulada con un decimal).
"""

import math

import pytest

from core.materials import CONCRETE_FCK_CLASSES, Concrete, MaterialError, ReinforcingSteel, stress_strain_curves
from core.parameters import ParameterSet

#            fck  fctm  (no usado)  Ecm(GPa) eps_c1 eps_cu1 eps_c2 eps_cu2  n    eps_c3
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


def test_invalid_steel():
    with pytest.raises(MaterialError):
        ReinforcingSteel(300, 0.05, 1.08)
    with pytest.raises(MaterialError):
        ReinforcingSteel.from_grade("B600X")
    with pytest.raises(MaterialError):
        ReinforcingSteel(500, 0.05, 1.08, branch="curva")  # type: ignore[arg-type]


def test_curves_are_monotonic_non_decreasing():
    cur = stress_strain_curves(Concrete(30), ReinforcingSteel.from_grade("B500S"))
    for key in ("concrete_design", "steel_design"):
        s = [p["sigma"] for p in cur[key]]
        assert all(b >= a - 1e-9 for a, b in zip(s, s[1:]))
