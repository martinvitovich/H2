"""Losas macizas unidireccionales (9.3 con 9.2.1.1, 6.1, 6.2.2): cálculos manuales independientes."""

import math

import pytest

from core.elu.losas import SlabInput, SlabInputError, slab_check
from core.materials import Concrete, ReinforcingSteel


def test_as_min_per_metre_manual():
    R = slab_check(SlabInput(200, 25, 15, span=5000))["result"]
    c, s = Concrete(25), ReinforcingSteel.from_grade("B500S")
    W = 1000 * 200 ** 2 / 6
    exp = W / (0.8 * 200) * (1.6 - 0.2) * c.fctm / s.fyd
    assert R["As_min"] == pytest.approx(exp)


def test_design_proposal_and_resistance_manual():
    r = slab_check(SlabInput(220, 25, 40, span=5000))
    R = r["result"]
    assert r["ok"] is True
    phi, sp = R["proposal"]["diameter"], R["proposal"]["spacing"]
    assert sp < min(300, 3 * 220) and sp % 25 == 0
    As = math.pi * phi ** 2 / 4 * 1000 / sp
    c, s = Concrete(25), ReinforcingSteel.from_grade("B500S")
    d = 220 - 25 - phi / 2
    # comprobación independiente con parábola-rectángulo (α = 17/21, β = 99/238)
    x = As * s.fyd / (17 / 21 * 1000 * c.fcd)
    assert R["m_Rd"] == pytest.approx(As * s.fyd * (d - 99 / 238 * x), rel=1e-7)
    assert R["m_Rd"] >= 40e6


def test_spacing_strict_limits_and_secondary():
    r = slab_check(SlabInput(80, 20, 3, span=2000, mode="check", bar_spacing=250, bar_diameter=8,
                             secondary_spacing=240))
    names = {c["name"]: c for c in r["trace"]["checks"]}
    assert names["Separación máxima de la armadura principal"]["ok"] is False  # 3h = 240 mm (estricto)
    assert names["Separación de la armadura secundaria"]["ok"] is False
    R = slab_check(SlabInput(200, 25, 20, span=5000, mode="check", bar_spacing=150))["result"]
    assert R["As_secondary_min"] == pytest.approx(0.2 * math.pi * 36 * 1000 / 150)


def test_scope_and_shear():
    r = slab_check(SlabInput(200, 25, 20, v_Ed_kn=150, span=800))
    names = {c["name"]: c for c in r["trace"]["checks"]}
    assert names["Ámbito de losa (l_eff ≥ 5h)"]["ok"] is False
    assert names["Cortante sin armadura de cortante"]["ok"] is False
    assert slab_check(SlabInput(200, 25, 20))["ok"] is None  # falta l_eff


def test_low_brittle_risk_alternative():
    R = slab_check(SlabInput(200, 25, 10, span=5000, low_brittle_risk=True))["result"]
    assert R["As_min"] == pytest.approx(1.2 * R["As_req"])


@pytest.mark.parametrize("kw", [dict(m_Ed_knm=0), dict(mode="check"), dict(h=40), dict(v_Ed_kn=-1),
                                dict(mode="check", bar_spacing=10)])
def test_invalid(kw):
    base = dict(h=200, cover=25, m_Ed_knm=20)
    base.update(kw)
    with pytest.raises(SlabInputError):
        slab_check(SlabInput(**base))
