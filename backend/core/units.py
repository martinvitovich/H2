"""Convenciones de unidades del motor de cálculo.

Unidades internas (coherentes entre sí):

* longitudes: mm
* áreas: mm²
* fuerzas: N
* tensiones y módulos: MPa = N/mm²
* momentos: N·mm
* deformaciones: adimensionales (no en ‰)

La API y la interfaz usan kN·m para momentos y kN para esfuerzos axiles; la
conversión se realiza únicamente mediante las funciones de este módulo.
"""

from __future__ import annotations

KN_TO_N = 1.0e3
KNM_TO_NMM = 1.0e6
PERMIL = 1.0e-3


def knm_to_nmm(m_knm: float) -> float:
    return m_knm * KNM_TO_NMM


def nmm_to_knm(m_nmm: float) -> float:
    return m_nmm / KNM_TO_NMM


def kn_to_n(f_kn: float) -> float:
    return f_kn * KN_TO_N


def n_to_kn(f_n: float) -> float:
    return f_n / KN_TO_N


def permil_to_strain(e_permil: float) -> float:
    return e_permil * PERMIL


def strain_to_permil(e: float) -> float:
    return e / PERMIL


def mm2_to_cm2(a_mm2: float) -> float:
    return a_mm2 / 100.0


def gpa_to_mpa(e_gpa: float) -> float:
    return e_gpa * 1.0e3
