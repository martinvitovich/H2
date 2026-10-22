import math

import pytest

from core.parameters import ParameterSet
from core.section import Layer, RectangularShape, ReinforcedSection, SectionError, TShape, min_clear_spacing


def test_rectangular_properties():
    s = RectangularShape(300, 500)
    assert s.area == 150000
    assert s.centroid_y == 250
    assert s.inertia == pytest.approx(300 * 500 ** 3 / 12)


def test_t_properties_manual():
    s = TShape(800, 120, 300, 600)
    A = 800 * 120 + 300 * 480
    yg = (800 * 120 * 60 + 300 * 480 * 360) / A
    I = 800 * 120 ** 3 / 12 + 800 * 120 * (60 - yg) ** 2 + 300 * 480 ** 3 / 12 + 300 * 480 * (360 - yg) ** 2
    assert s.area == pytest.approx(A)
    assert s.centroid_y == pytest.approx(yg)
    assert s.inertia == pytest.approx(I)
    m = s.mirrored_segments()
    assert m[0].width == 300 and m[-1].width == 800


@pytest.mark.parametrize("args", [(0, 500), (300, -1)])
def test_invalid_rect(args):
    with pytest.raises(SectionError):
        RectangularShape(*args)


def test_invalid_t():
    with pytest.raises(SectionError):
        TShape(800, 600, 300, 600)
    with pytest.raises(SectionError):
        TShape(200, 100, 300, 600)


def test_min_spacing_8_2():
    p = ParameterSet()
    assert min_clear_spacing(16, 20, p) == 25      # d_g + 5
    assert min_clear_spacing(32, 20, p) == 32      # k1·φ
    assert min_clear_spacing(12, 10, p) == 20      # absoluto


def test_bar_positions_and_d():
    sec = ReinforcedSection(RectangularShape(300, 500), 30, 8, [Layer("inferior", 4, 16)])
    assert sec.d == pytest.approx(500 - 30 - 8 - 8)
    xs = sorted(b.x for b in sec.bars)
    assert xs[0] == pytest.approx(30 + 8 + 8)
    assert xs[-1] == pytest.approx(300 - 46)
    assert sec.area_on("inferior") == pytest.approx(4 * math.pi * 64)
    assert not sec.issues


def test_two_layers_d_is_centroid():
    sec = ReinforcedSection(RectangularShape(300, 600), 30, 8,
                            [Layer("inferior", 3, 20), Layer("inferior", 2, 20)])
    y1 = 600 - 48
    sv = min_clear_spacing(20, 20, ParameterSet())
    y2 = y1 - 20 - sv
    assert sec.d == pytest.approx((3 * y1 + 2 * y2) / 5)


def test_spacing_issue_reported():
    sec = ReinforcedSection(RectangularShape(200, 400), 30, 8, [Layer("inferior", 5, 20)])
    assert any("horizontal" in i for i in sec.issues)


def test_bars_not_fitting_raises():
    with pytest.raises(SectionError):
        ReinforcedSection(RectangularShape(80, 400), 30, 8, [Layer("inferior", 2, 20)])


def test_overlap_raises():
    with pytest.raises(SectionError):
        ReinforcedSection(RectangularShape(300, 100), 30, 8,
                          [Layer("inferior", 2, 20), Layer("superior", 2, 20)])


def test_layer_validation():
    with pytest.raises(SectionError):
        ReinforcedSection(RectangularShape(300, 500), 30, 8, [Layer("inferior", 1, 16)])
    with pytest.raises(SectionError):
        ReinforcedSection(RectangularShape(300, 500), 30, 8, [Layer("lateral", 2, 16)])  # type: ignore[arg-type]
    with pytest.raises(SectionError):
        ReinforcedSection(RectangularShape(300, 500), -5, 8, [Layer("inferior", 2, 16)])


def test_t_section_bars_inside_web():
    shape = TShape(800, 120, 300, 600)
    sec = ReinforcedSection(shape, 30, 8, [Layer("inferior", 3, 20)])
    x0 = (800 - 300) / 2
    assert all(x0 < b.x < x0 + 300 for b in sec.bars)
