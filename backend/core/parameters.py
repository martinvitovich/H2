"""Parámetros normativos centralizados.

Todos los coeficientes que intervienen en los cálculos se definen aquí, con su
referencia al Anejo 19 del Código Estructural y su estado de verificación.
Ningún otro módulo del motor debe contener constantes normativas propias.

Estado de verificación (``VerificationStatus``):

* ``VERIFICADO_TEXTO_OFICIAL``: valor cotejado con el texto oficial del Anejo 19
  publicado en el BOE n.º 190 de 10/08/2021 (BOE-A-2021-13681). La página del BOE
  se indica en la referencia.
* ``CONFIRMADO_FUENTE_SECUNDARIA``: valor contrastado solo con un extracto indirecto.
* ``PENDIENTE_VERIFICACION``: valor no contrastado con el texto oficial (p. ej.,
  porque el Anejo remite a otra disposición no consultada) o criterio no normativo.
* ``DEFINIDO_POR_USUARIO``: el usuario ha sobrescrito el valor por defecto.
* ``NO_NORMATIVO``: criterio propio del programa (no procede del Anejo).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any

NORM_ID = "CE-A19"
NORM_NAME = (
    "Código Estructural (Real Decreto 470/2021), Anejo 19: Proyecto de estructuras "
    "de hormigón. Reglas generales y reglas para edificación"
)
NORM_EDITION = "Real Decreto 470/2021, de 29 de junio (BOE-A-2021-13681, BOE n.º 190, 10/08/2021)"
NORM_SHORT = "Código Estructural, Anejo 19"


class VerificationStatus(str, Enum):
    VERIFICADO_TEXTO_OFICIAL = "verificado_texto_oficial"
    CONFIRMADO_FUENTE_SECUNDARIA = "confirmado_fuente_secundaria"
    PENDIENTE_VERIFICACION = "pendiente_verificacion"
    DEFINIDO_POR_USUARIO = "definido_por_usuario"
    NO_NORMATIVO = "no_normativo"


@dataclass
class Parameter:
    key: str
    symbol: str
    value: Any
    unit: str
    description: str
    reference: str
    status: VerificationStatus
    note: str = ""
    min_value: float | None = None
    max_value: float | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


class ParameterError(ValueError):
    """Valor de parámetro normativo no válido."""


_P = VerificationStatus.PENDIENTE_VERIFICACION
_V = VerificationStatus.VERIFICADO_TEXTO_OFICIAL

# Factores de E_cm según el tipo de árido, Anejo 19, 3.1.3(2) (BOE pág. 98307):
# los valores de la tabla A19.3.1 corresponden a áridos cuarcíticos; se reducen un 10 %
# con áridos calizos, un 30 % con arenisca y se incrementan un 20 % con áridos basálticos.
AGGREGATE_ECM_FACTORS: dict[str, float] = {
    "cuarcitico": 1.0, "calizo": 0.9, "arenisca": 0.7, "basaltico": 1.2,
}
AGGREGATE_REFERENCE = "Anejo 19, 3.1.3(2) (BOE pág. 98307)"


def _defaults() -> list[Parameter]:
    return [
        # --- Coeficientes parciales de los materiales (2.4.2.4, tabla A19.2.1) ---
        Parameter(
            "gamma_c_persistente", "γ_c", 1.5, "-",
            "Coeficiente parcial del hormigón, situación permanente o transitoria",
            "Anejo 19, 2.4.2.4(1), tabla A19.2.1 (BOE pág. 98304)", _V, min_value=1.0, max_value=2.0,
            note="Pueden usarse valores menores si se justifica la reducción de la incertidumbre "
            "(2.4.2.4(3) y Apéndice A).",
        ),
        Parameter(
            "gamma_c_accidental", "γ_c", 1.3, "-",
            "Coeficiente parcial del hormigón, situación accidental",
            "Anejo 19, 2.4.2.4(1), tabla A19.2.1 (BOE pág. 98304)", _V, min_value=1.0, max_value=2.0,
        ),
        Parameter(
            "gamma_s_persistente", "γ_s", 1.15, "-",
            "Coeficiente parcial del acero de armaduras pasivas, situación permanente o transitoria",
            "Anejo 19, 2.4.2.4(1), tabla A19.2.1 (BOE pág. 98304)", _V, min_value=1.0, max_value=1.5,
            note="Puede reducirse hasta 1,10 si se cumplen al menos dos de las condiciones de 2.4.2.6.",
        ),
        Parameter(
            "gamma_s_accidental", "γ_s", 1.0, "-",
            "Coeficiente parcial del acero de armaduras pasivas, situación accidental",
            "Anejo 19, 2.4.2.4(1), tabla A19.2.1 (BOE pág. 98304)", _V, min_value=1.0, max_value=1.5,
        ),
        # --- Resistencias de cálculo del hormigón (3.1.6) ---
        Parameter(
            "alpha_cc", "α_cc", 1.0, "-",
            "Coeficiente de efectos a largo plazo y de la forma de aplicación de la carga "
            "sobre la resistencia a compresión",
            "Anejo 19, 3.1.6(1), expresión (3.15) (BOE pág. 98313)", _V,
            note="Con carácter general α_cc = 1,00. Si la carga permanente supera el 80 % de la "
            "carga total, el autor del proyecto puede adoptar un valor entre 0,85 y 1,0.",
            min_value=0.85, max_value=1.0,
        ),
        Parameter(
            "alpha_ct", "α_ct", 1.0, "-",
            "Coeficiente de efectos a largo plazo sobre la resistencia a tracción",
            "Anejo 19, 3.1.6(2), expresión (3.16) (BOE pág. 98313)", _V,
            note="El Anejo fija α_ct = 1,00.",
            min_value=1.0, max_value=1.0,
        ),
        # --- Acero de armar (3.2.7) ---
        Parameter(
            "Es", "E_s", 200000.0, "MPa",
            "Módulo de elasticidad de cálculo del acero de armaduras pasivas",
            "Anejo 19, 3.2.7(4) (BOE pág. 98319)", _V, min_value=150000.0, max_value=220000.0,
        ),
        Parameter(
            "eps_ud_factor", "ε_ud/ε_uk", 0.9, "-",
            "Relación entre la deformación límite de cálculo y la deformación bajo carga máxima "
            "(solo para el diagrama con rama superior inclinada)",
            "Anejo 19, 3.2.7(2) a) (BOE pág. 98319)", _V,
            note="Con la rama horizontal (3.2.7(2) b) no es necesario comprobar el límite de deformación.",
            min_value=0.5, max_value=1.0,
        ),
        # --- Criterio de ductilidad (5.5(4)) ---
        Parameter(
            "delta_redistribucion", "δ", 1.0, "-",
            "Relación entre el momento redistribuido y el momento elástico (δ = 1: sin "
            "redistribución)",
            "Anejo 19, 5.5(4) (BOE págs. 98335-98336)", _V,
            note="Con redistribución, δ ≥ k5 = 0,7 para armaduras tipo S o SD y δ ≥ k6 = 0,8 para "
            "tipo T (5.5(4)).",
            min_value=0.7, max_value=1.0,
        ),
        Parameter("k1_redist", "k_1", 0.44, "-", "Coeficiente k1 de la expresión (5.10a)",
                  "Anejo 19, 5.5(4) (BOE pág. 98336)", _V, min_value=0.0, max_value=1.0),
        Parameter("k2_redist_base", "k_2", 1.25, "-",
                  "Factor de k2 = 1,25·(0,6 + 0,0014/ε_cu2) de la expresión (5.10a)",
                  "Anejo 19, 5.5(4) (BOE pág. 98336)", _V, min_value=0.0, max_value=5.0),
        Parameter("k3_redist", "k_3", 0.54, "-", "Coeficiente k3 de la expresión (5.10b)",
                  "Anejo 19, 5.5(4) (BOE pág. 98336)", _V, min_value=0.0, max_value=1.0),
        Parameter("k4_redist_base", "k_4", 1.25, "-",
                  "Factor de k4 = 1,25·(0,6 + 0,0014/ε_cu2) de la expresión (5.10b)",
                  "Anejo 19, 5.5(4) (BOE pág. 98336)", _V, min_value=0.0, max_value=5.0),
        # --- Armaduras mínima y máxima en vigas (9.2.1.1) ---
        Parameter("z_factor_asmin", "z/h", 0.8, "-",
                  "Brazo mecánico aproximado para la armadura mínima: z = 0,8·h",
                  "Anejo 19, 9.2.1.1(1), expresión (9.1) (BOE pág. 98424)", _V,
                  note="El Anejo indica que z «puede calcularse de forma aproximada como z = 0,8h».",
                  min_value=0.5, max_value=1.0),
        Parameter("As_min_secondary_factor", "-", 1.2, "-",
                  "Alternativa para elementos secundarios con riesgo de rotura frágil admisible: "
                  "A_s,min = 1,2·A_s,nec (ELU)",
                  "Anejo 19, 9.2.1.1(1) (BOE pág. 98424)", _V, min_value=1.0, max_value=2.0),
        Parameter("As_max_coef", "-", 0.04, "-",
                  "Cuantía máxima de armadura de tracción o de compresión, A_s,max = 0,04·A_c "
                  "(fuera de zonas de solape)",
                  "Anejo 19, 9.2.1.1(3) (BOE pág. 98424)", _V, min_value=0.0, max_value=0.1),
        Parameter("compression_bar_tie_factor", "-", 15.0, "-",
                  "Separación máxima de la armadura transversal que sujeta las barras comprimidas "
                  "consideradas en el cálculo: s_t ≤ 15·φ",
                  "Anejo 19, 9.2.1.2(3) (BOE pág. 98425)", _V, min_value=1.0, max_value=30.0),
        # --- Separación de barras (8.2) ---
        Parameter("spacing_k1", "k_1", 1.0, "-",
                  "Separación libre mínima: k1·φ", "Anejo 19, 8.2(2) (BOE pág. 98405)", _V,
                  min_value=0.5, max_value=3.0),
        Parameter("spacing_k2", "k_2", 5.0, "mm",
                  "Separación libre mínima: d_g + k2", "Anejo 19, 8.2(2) (BOE pág. 98405)", _V,
                  min_value=0.0, max_value=30.0),
        Parameter("spacing_abs_min", "-", 20.0, "mm",
                  "Separación libre mínima absoluta", "Anejo 19, 8.2(2) (BOE pág. 98405)", _V,
                  min_value=0.0, max_value=50.0),
        # --- Criterios de propuesta de armado (no normativos) ---
        Parameter("bar_diameters", "φ", [10, 12, 16, 20, 25, 32], "mm",
                  "Diámetros comerciales considerados en la propuesta de armado",
                  "Criterio del programa (no normativo)", VerificationStatus.NO_NORMATIVO,
                  note="Lista editable. No es un parámetro normativo."),
    ]


class ParameterSet:
    """Conjunto de parámetros normativos con valores por defecto y sobrescrituras."""

    def __init__(self, overrides: dict[str, Any] | None = None) -> None:
        self._params: dict[str, Parameter] = {p.key: p for p in _defaults()}
        if overrides:
            for k, v in overrides.items():
                self.set(k, v)

    def set(self, key: str, value: Any) -> None:
        if key not in self._params:
            raise ParameterError(f"Parámetro normativo desconocido: '{key}'")
        p = self._params[key]
        if key == "bar_diameters":
            if not isinstance(value, (list, tuple)) or not value:
                raise ParameterError("bar_diameters debe ser una lista no vacía de diámetros")
            vals = sorted({float(x) for x in value})
            if any(x < 6 or x > 40 for x in vals):
                raise ParameterError("Diámetros fuera del rango 6–40 mm")
            value = vals
        else:
            try:
                value = float(value)
            except (TypeError, ValueError) as exc:
                raise ParameterError(f"Valor no numérico para '{key}'") from exc
            if p.min_value is not None and value < p.min_value:
                raise ParameterError(f"{key} = {value} < mínimo admitido {p.min_value}")
            if p.max_value is not None and value > p.max_value:
                raise ParameterError(f"{key} = {value} > máximo admitido {p.max_value}")
        if value != p.value:
            p.value = value
            p.status = VerificationStatus.DEFINIDO_POR_USUARIO

    def __getitem__(self, key: str) -> Any:
        return self._params[key].value

    def get(self, key: str) -> Parameter:
        return self._params[key]

    def all(self) -> list[Parameter]:
        return list(self._params.values())

    def overrides(self) -> dict[str, Any]:
        base = {p.key: p.value for p in _defaults()}
        return {k: p.value for k, p in self._params.items() if p.value != base[k]}

    def to_list(self) -> list[dict[str, Any]]:
        return [p.to_dict() for p in self._params.values()]

    def copy(self) -> "ParameterSet":
        return copy.deepcopy(self)

    # --- valores dependientes de la situación de proyecto ---
    def gamma_c(self, situation: str) -> float:
        return self[f"gamma_c_{_situation_key(situation)}"]

    def gamma_s(self, situation: str) -> float:
        return self[f"gamma_s_{_situation_key(situation)}"]


def _situation_key(situation: str) -> str:
    if situation in ("persistente", "transitoria"):
        return "persistente"
    if situation == "accidental":
        return "accidental"
    raise ParameterError(
        f"Situación de proyecto no admitida: '{situation}' "
        "(persistente, transitoria o accidental)"
    )


def norm_info() -> dict[str, str]:
    return {"id": NORM_ID, "name": NORM_NAME, "edition": NORM_EDITION, "short": NORM_SHORT}
