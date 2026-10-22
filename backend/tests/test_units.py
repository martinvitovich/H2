import pytest

from core import units


def test_moment_conversion_roundtrip():
    assert units.knm_to_nmm(1.0) == 1.0e6
    assert units.nmm_to_knm(units.knm_to_nmm(123.456)) == pytest.approx(123.456, rel=1e-15)


def test_force_and_strain_conversions():
    assert units.kn_to_n(2.5) == 2500.0
    assert units.n_to_kn(2500.0) == 2.5
    assert units.permil_to_strain(3.5) == pytest.approx(0.0035)
    assert units.strain_to_permil(0.002) == pytest.approx(2.0)
    assert units.mm2_to_cm2(100.0) == 1.0
    assert units.gpa_to_mpa(200.0) == 200000.0


def test_dimensional_consistency_mpa_mm():
    # 1 MPa · 1 mm² = 1 N ; 1 N · 1 mm = 1e-6 kN·m
    assert units.nmm_to_knm(1.0 * 1.0 * 1.0) == pytest.approx(1e-6)
