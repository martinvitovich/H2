import pytest

from core.parameters import ParameterError, ParameterSet, VerificationStatus, norm_info


def test_defaults_and_references():
    p = ParameterSet()
    assert p["gamma_c_persistente"] == 1.5
    assert p["gamma_s_persistente"] == 1.15
    assert p["gamma_c_accidental"] == 1.3
    assert p["gamma_s_accidental"] == 1.0
    for par in p.all():
        assert par.reference, f"{par.key} sin referencia"
        assert isinstance(par.status, VerificationStatus)


def test_situations():
    p = ParameterSet()
    assert p.gamma_c("persistente") == p.gamma_c("transitoria") == 1.5
    assert p.gamma_s("accidental") == 1.0
    with pytest.raises(ParameterError):
        p.gamma_c("sismica")


def test_override_marks_user_status():
    p = ParameterSet({"alpha_cc": 0.85})
    assert p["alpha_cc"] == 0.85
    assert p.get("alpha_cc").status == VerificationStatus.DEFINIDO_POR_USUARIO
    assert p.overrides() == {"alpha_cc": 0.85}
    # el conjunto por defecto no se ve afectado
    assert ParameterSet()["alpha_cc"] == 1.0


@pytest.mark.parametrize("key,val", [("alpha_cc", 1.2), ("gamma_c_persistente", 0.9),
                                     ("As_max_coef", -0.1), ("alpha_cc", "abc"),
                                     ("alpha_ct", 0.9), ("delta_redistribucion", 0.6)])
def test_invalid_overrides(key, val):
    with pytest.raises(ParameterError):
        ParameterSet({key: val})


def test_verified_statuses():
    p = ParameterSet()
    for key in ("gamma_c_persistente", "alpha_cc", "Es", "z_factor_asmin", "As_max_coef", "spacing_k1"):
        assert p.get(key).status == VerificationStatus.VERIFICADO_TEXTO_OFICIAL
        assert "BOE pág." in p.get(key).reference
    assert p.get("bar_diameters").status == VerificationStatus.NO_NORMATIVO


def test_unknown_parameter():
    with pytest.raises(ParameterError):
        ParameterSet({"no_existe": 1})


def test_bar_diameters_validation():
    p = ParameterSet({"bar_diameters": [16, 12, 12]})
    assert p["bar_diameters"] == [12.0, 16.0]
    with pytest.raises(ParameterError):
        ParameterSet({"bar_diameters": []})
    with pytest.raises(ParameterError):
        ParameterSet({"bar_diameters": [50]})


def test_norm_info():
    info = norm_info()
    assert "Anejo 19" in info["name"]
    assert "470/2021" in info["edition"]
