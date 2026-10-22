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


def test_as_min_manual():
    c, s = Concrete(25), ReinforcingSteel.from_grade("B500S")
    v = as_min(c, s, 300, 450, ParameterSet())
    assert v == pytest.approx(max(0.26 * 0.3 * 25 ** (2 / 3) / 500 * 300 * 450, 0.0013 * 300 * 450))


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
    r = design_flexure(FlexureInput(RectangularShape(300, 500), 30, 8, M))
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
