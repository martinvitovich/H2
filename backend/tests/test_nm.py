"""Diagrama de interacción N–M (6.1): contrastes independientes.

* Compresión centrada y tracción pura: soluciones cerradas.
* N = 0: debe coincidir con el método de flexión simple (analysis.analyse_bending), que es una
  implementación independiente del equilibrio.
* Un plano de deformación arbitrario: integración independiente por fibras (5000 fibras,
  regla del punto medio). Tolerancia 1e-4 relativa, coherente con el error de la discretización.
"""

import math

import pytest

from core.elu.analysis import analyse_bending
from core.elu.nm import NMError, NMSection, interaction_diagram
from core.materials import Concrete, ReinforcingSteel
from core.section import Layer, RectangularShape, ReinforcedSection, TShape

C, S = Concrete(30), ReinforcingSteel.from_grade("B500S")
SEC = ReinforcedSection(RectangularShape(400, 400), 35, 8,
                        [Layer("inferior", 3, 16), Layer("superior", 3, 16), Layer("lateral", 1, 16)])
As = sum(b.area for b in SEC.bars)


def test_pure_compression_and_tension_closed_form():
    nm = NMSection(SEC, C, S, 1)
    n0, n3 = nm.N_range()
    assert n0 == pytest.approx(-As * S.fyd, rel=1e-9)
    sig_s = min(S.Es * C.eps_c2, S.fyd)
    assert n3 == pytest.approx(C.fcd * 160000 + As * (sig_s - C.fcd), rel=1e-9)
    assert abs(nm.point(3.0).M) < 1e-3 * 1e6  # simétrica: momento nulo


def test_zero_axial_matches_bending_module():
    for sign in (1, -1):
        mrd_nm = NMSection(SEC, C, S, sign).resistance_at(0.0).M
        mrd_b = analyse_bending(SEC, C, S, sign).M_Rd
        assert mrd_nm == pytest.approx(mrd_b, rel=1e-7)


def fiber_forces(sec, conc, steel, et, eb, nf=5000):
    h = sec.shape.h
    yg = sec.shape.centroid_y
    N = M = 0.0
    dy = h / nf
    for i in range(nf):
        y = (i + 0.5) * dy
        e = et + (eb - et) * y / h
        s = conc.sigma_parabola_rectangle(min(e, conc.eps_cu2)) if e > 0 else 0.0
        F = s * sec.shape.width_at(y) * dy
        N += F
        M += F * (yg - y)
    for b in sec.bars:
        e = et + (eb - et) * b.y / h
        sc = conc.sigma_parabola_rectangle(min(e, conc.eps_cu2)) if e > 0 else 0.0
        F = (-steel.sigma(-e) - sc) * b.area
        N += F
        M += F * (yg - b.y)
    return N, M


@pytest.mark.parametrize("t", [0.5, 1.0, 1.3, 1.8, 2.2, 2.7])
def test_planes_against_fiber_integration(t):
    nm = NMSection(SEC, C, S, 1)
    p = nm.point(t)
    N, M = fiber_forces(SEC, C, S, p.eps_top, p.eps_bot)
    assert p.N == pytest.approx(N, rel=1e-4, abs=50)
    assert p.M == pytest.approx(M, rel=1e-4, abs=5e3)


def test_t_section_fiber_integration():
    sec = ReinforcedSection(TShape(800, 120, 300, 600), 30, 8, [Layer("inferior", 3, 20), Layer("superior", 2, 16)])
    nm = NMSection(sec, C, S, 1)
    for t in (1.2, 1.7, 2.4):
        p = nm.point(t)
        N, M = fiber_forces(sec, C, S, p.eps_top, p.eps_bot)
        assert p.N == pytest.approx(N, rel=1e-4, abs=50)
        assert p.M == pytest.approx(M, rel=1e-4, abs=5e3)


def test_planes_respect_strain_limits_and_continuity():
    nm = NMSection(SEC, C, S, 1)
    prev = None
    for i in range(301):
        t = 3 * i / 300
        et, eb, dom = nm.plane(t)
        assert max(et, eb) <= C.eps_cu2 + 1e-12
        if dom == "C":  # en el punto C la deformación es ε_c2
            yc = nm.yC
            assert et + (eb - et) * yc / nm.h == pytest.approx(C.eps_c2)
        p = nm.point(t)
        if prev is not None:
            assert p.N >= prev - 1e-6  # N monótono a lo largo del recorrido
        prev = p.N


def test_symmetric_diagram():
    d = interaction_diagram(SEC, C, S, n=20)
    Mmax, Mmin = max(q["M"] for q in d), min(q["M"] for q in d)
    assert Mmax == pytest.approx(-Mmin, rel=1e-9)


def test_out_of_range_axial():
    nm = NMSection(SEC, C, S, 1)
    with pytest.raises(NMError):
        nm.resistance_at(nm.N_range()[1] * 1.01)


def test_inclined_branch_pivot_a_strain():
    s = ReinforcingSteel.from_grade("B500SD", branch="inclinada")
    nm = NMSection(SEC, C, s, 1)
    et, eb, dom = nm.plane(0.5)
    deep = nm.y_deep
    assert et + (eb - et) * deep / nm.h == pytest.approx(-s.eps_ud)
