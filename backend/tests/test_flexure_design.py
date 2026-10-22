"""Dimensionado a flexión: comprobaciones de consistencia matemática.

No se dispone (en el entorno de desarrollo) de un ejemplo resuelto verificable del
Anejo 19; los tests verifican el equilibrio de la solución y su coherencia con el
método general. Validación normativa independiente: PENDIENTE.
"""

import math

import pytest

from core.elu.flexion import (FlexureInput, FlexureInputError, as_min, block_design, check_flexure,
                              design_flexure, ductility_limit)
from core.materials import Concrete, ReinforcingSteel
from core.parameters import ParameterSet
from core.section import Layer, RectangularShape, TShape


def test_ductility_limit_default():
    p = ParameterSet()
    assert ductility_limit(Concrete(30), p) == pytest.approx((1 - 0.44) / 1.25)
    c = Concrete(70)
    k4 = 1.25 * (0.6 + 0.0014 / c.eps_cu2)
    assert ductility_limit(c, p) == pytest.approx((1 - 0.54) / k4)


def test_as_min_9_1_rectangular_manual():
    """(9.1): A_s,min = (W/z)·f_ctm,fl/f_yd, z = 0,8h, f_ctm,fl = max{(1,6 − h/1000)f_ctm; f_ctm}."""
    c, s = Concrete(25), ReinforcingSteel.from_grade("B500S")
    b, h = 300.0, 500.0
    W = b * h ** 2 / 6
    fctm_fl = (1.6 - 0.5) * 0.30 * 25 ** (2 / 3)
    expected = W / (0.8 * h) * fctm_fl / (500 / 1.15)
    v = as_min(c, s, RectangularShape(b, h), 1, ParameterSet())
    assert v == pytest.approx(expected, rel=1e-12)
    assert v == pytest.approx(202.8, abs=0.1)  # valor numérico del cálculo manual
    # simétrica: igual para momento negativo
    assert as_min(c, s, RectangularShape(b, h), -1, ParameterSet()) == pytest.approx(v)


def test_as_min_9_1_t_section_depends_on_sign():
    c, s = Concrete(25), ReinforcingSteel.from_grade("B500S")
    t = TShape(800, 120, 300, 600)
    yg, I = t.centroid_y, t.inertia
    fctm_fl = 1.0 * c.fctm  # h = 600 mm → 1,6 − 0,6 = 1,0
    pos = I / (600 - yg) / (0.8 * 600) * fctm_fl / s.fyd
    neg = I / yg / (0.8 * 600) * fctm_fl / s.fyd
    assert as_min(c, s, t, 1, ParameterSet()) == pytest.approx(pos)
    assert as_min(c, s, t, -1, ParameterSet()) == pytest.approx(neg)
    assert neg > pos  # el ala traccionada exige más armadura mínima


def test_as_min_secondary_element():
    c, s = Concrete(25), ReinforcingSteel.from_grade("B500S")
    assert as_min(c, s, RectangularShape(300, 500), 1, ParameterSet(), secondary=True, As_req=500) == \
        pytest.approx(600)
    with pytest.raises(FlexureInputError):
        as_min(c, s, RectangularShape(300, 500), 1, ParameterSet(), secondary=True)


def test_block_design_single_equilibrium():
    c, s = Concrete(25), ReinforcingSteel.from_grade("B500S")
    b, d, M = 300.0, 450.0, 150e6
    bd = block_design(b, d, 50, M, c, s, 0.448)
    assert not bd.compression_needed
    y = c.lam * bd.x
    assert bd.As1 * s.fyd == pytest.approx(c.fcd * b * y)          # ΣF = 0
    assert bd.As1 * s.fyd * (d - y / 2) == pytest.approx(M)        # ΣM = 0


def test_block_design_double_equilibrium():
    c, s = Concrete(25), ReinforcingSteel.from_grade("B500S")
    b, d, d2, M = 300.0, 450.0, 50.0, 400e6
    bd = block_design(b, d, d2, M, c, s, 0.448)
    assert bd.compression_needed
    assert bd.x == pytest.approx(0.448 * d)
    y = c.lam * bd.x
    sig2 = bd.sigma_s2 - c.fcd  # barra dentro del bloque
    assert bd.As1 * s.fyd == pytest.approx(c.fcd * b * y + bd.As2 * sig2)
    M_calc = c.fcd * b * y * (d - y / 2) + bd.As2 * sig2 * (d - d2)
    assert M_calc == pytest.approx(M)


def test_design_result_verified_by_general_method():
    r = design_flexure(FlexureInput(RectangularShape(300, 500), 30, 8, 150.0))
    assert r["ok"] is True
    assert r["verification"]["M_Rd"] / 1e6 >= 150.0
    assert r["proposal"]["As_tension"] >= r["design"]["As1"]


@pytest.mark.parametrize("M", [60, 150, 250, 350, 450, -180])
def test_design_proposals_satisfy_all_checks(M):
    r = design_flexure(FlexureInput(RectangularShape(300, 500), 30, 8, M, stirrup_spacing=150))
    assert r["proposal"] is not None
    assert r["ok"] is True
    assert abs(r["verification"]["M_Rd"]) / 1e6 >= abs(M)
    assert r["verification"]["xi"] <= r["design"]["xi_lim"] + 1e-9


def test_minimum_reinforcement_governs_small_moment():
    r = design_flexure(FlexureInput(RectangularShape(300, 500), 30, 8, 5.0))
    assert r["design"]["As1_req"] == pytest.approx(r["design"]["As_min"])
    assert any("mínima" in w for w in r["trace"]["warnings"])


def test_oversized_moment_has_no_practical_solution():
    r = design_flexure(FlexureInput(RectangularShape(200, 300), 30, 8, 500.0))
    assert r["ok"] is False
    assert r["proposal"] is None


def test_design_rejects_t_and_zero_moment():
    with pytest.raises(FlexureInputError):
        design_flexure(FlexureInput(TShape(800, 120, 300, 600), 30, 8, 100))
    with pytest.raises(FlexureInputError):
        design_flexure(FlexureInput(RectangularShape(300, 500), 30, 8, 0))


def test_invalid_cover():
    with pytest.raises(FlexureInputError):
        design_flexure(FlexureInput(RectangularShape(300, 500), 0, 8, 100))
    with pytest.raises(FlexureInputError):
        design_flexure(FlexureInput(RectangularShape(300, 100), 45, 8, 10))


def test_check_mode_trace_contents():
    r = check_flexure(FlexureInput(RectangularShape(300, 500), 30, 8, 120,
                                   layers=[Layer("inferior", 4, 16), Layer("superior", 2, 12)]))
    tr = r["trace"]
    assert "Anejo 19" in tr["norm"]["name"]
    assert tr["steps"] and tr["checks"] and tr["assumptions"] and tr["parameters_used"]
    for st in tr["steps"]:
        assert st["reference"]
    names = {c["name"] for c in tr["checks"]}
    assert {"Resistencia a flexión", "Armadura mínima de tracción", "Armadura máxima de tracción"} <= names
    assert r["comparison"] is not None


def test_check_insufficient_reinforcement_fails():
    r = check_flexure(FlexureInput(RectangularShape(300, 500), 30, 8, 300,
                                   layers=[Layer("inferior", 2, 12)]))
    assert r["ok"] is False
    flex = next(c for c in r["trace"]["checks"] if c["name"] == "Resistencia a flexión")
    assert flex["ok"] is False


def test_check_without_tension_bars():
    r = check_flexure(FlexureInput(RectangularShape(300, 500), 30, 8, -50,
                                   layers=[Layer("inferior", 3, 16)]))
    assert r["ok"] is False and r["verification"] is None


def test_parameter_override_changes_result():
    base = check_flexure(FlexureInput(RectangularShape(300, 500), 30, 8, 100,
                                      layers=[Layer("inferior", 3, 16)]))
    mod = check_flexure(FlexureInput(RectangularShape(300, 500), 30, 8, 100,
                                     layers=[Layer("inferior", 3, 16)],
                                     params=ParameterSet({"gamma_s_persistente": 1.0})))
    assert mod["verification"]["M_Rd"] > base["verification"]["M_Rd"]
    used = {p["key"]: p for p in mod["trace"]["parameters_used"]}
    assert used["gamma_s_persistente"]["status"] == "definido_por_usuario"


def test_compression_bar_tie_check_9_2_1_2():
    layers = [Layer("inferior", 4, 16), Layer("superior", 2, 12)]
    base = dict(shape=RectangularShape(300, 500), cover=30, stirrup_diameter=8, M_Ed_knm=120, layers=layers)
    get = lambda r: next(c for c in r["trace"]["checks"] if c["reference"].startswith("Anejo 19, 9.2.1.2(3)"))
    r = check_flexure(FlexureInput(**base))
    assert get(r)["ok"] is None and r["ok"] is None          # falta el dato: no se declara conforme
    assert get(check_flexure(FlexureInput(**base, stirrup_spacing=180)))["ok"] is True   # 15·12 = 180
    assert get(check_flexure(FlexureInput(**base, stirrup_spacing=200)))["ok"] is False
    nost = dict(base, stirrup_diameter=0)
    assert get(check_flexure(FlexureInput(**nost, stirrup_spacing=100)))["ok"] is False


def test_secondary_element_in_design_and_check():
    r = design_flexure(FlexureInput(RectangularShape(300, 500), 30, 8, 150, secondary_element=True))
    assert r["design"]["As_min"] == pytest.approx(1.2 * r["design"]["As1"])
    rc = check_flexure(FlexureInput(TShape(800, 120, 300, 600), 30, 8, 200, secondary_element=True,
                                    layers=[Layer("inferior", 3, 20)]))
    assert any("expresión (9.1)" in w for w in rc["trace"]["warnings"])
