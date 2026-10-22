"""Registro de trazabilidad de los cálculos.

Cada función de cálculo recibe o crea un ``CalcTrace`` y anota en él las
hipótesis, los parámetros normativos empleados, las ecuaciones aplicadas con sus
valores sustituidos, los resultados intermedios, las verificaciones y las
advertencias. El registro es serializable a JSON y alimenta tanto la sección
«Normativa y procedimiento» de la interfaz como el informe PDF.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

from .parameters import NORM_EDITION, NORM_NAME, NORM_ID, ParameterSet


@dataclass
class Step:
    title: str
    reference: str
    equation: str
    substitution: str
    result: float | None
    unit: str
    symbol: str = ""
    note: str = ""


@dataclass
class Check:
    name: str
    reference: str
    demand: str
    capacity: str
    ok: bool | None  # None: no evaluable con los datos disponibles
    note: str = ""


@dataclass
class CalcTrace:
    calculation: str
    method: str
    validation_status: str
    inputs: dict[str, Any] = field(default_factory=dict)
    units: dict[str, str] = field(default_factory=dict)
    assumptions: list[str] = field(default_factory=list)
    parameters_used: list[dict[str, Any]] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)
    checks: list[Check] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    def assume(self, text: str) -> None:
        if text not in self.assumptions:
            self.assumptions.append(text)

    def warn(self, text: str) -> None:
        if text not in self.warnings:
            self.warnings.append(text)

    def limit(self, text: str) -> None:
        if text not in self.limitations:
            self.limitations.append(text)

    def use_param(self, params: ParameterSet, key: str) -> Any:
        """Devuelve el valor del parámetro y lo registra como utilizado."""
        p = params.get(key)
        if not any(d["key"] == key for d in self.parameters_used):
            self.parameters_used.append(p.to_dict())
        return p.value

    def step(self, title: str, reference: str, equation: str, substitution: str,
             result: float | None, unit: str, symbol: str = "", note: str = "") -> float | None:
        self.steps.append(Step(title, reference, equation, substitution, result, unit, symbol, note))
        return result

    def check(self, name: str, reference: str, demand: str, capacity: str,
              ok: bool | None, note: str = "") -> bool | None:
        self.checks.append(Check(name, reference, demand, capacity, ok, note))
        return ok

    @property
    def all_checks_ok(self) -> bool | None:
        if not self.checks:
            return None
        if any(c.ok is False for c in self.checks):
            return False
        if any(c.ok is None for c in self.checks):
            return None
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "norm": {"id": NORM_ID, "name": NORM_NAME, "edition": NORM_EDITION},
            "calculation": self.calculation,
            "method": self.method,
            "validation_status": self.validation_status,
            "inputs": self.inputs,
            "units": self.units,
            "assumptions": self.assumptions,
            "parameters_used": self.parameters_used,
            "steps": [asdict(s) for s in self.steps],
            "checks": [asdict(c) for c in self.checks],
            "warnings": self.warnings,
            "limitations": self.limitations,
            "all_checks_ok": self.all_checks_ok,
        }


def fmt(x: float, nd: int = 3) -> str:
    """Formato numérico compacto para sustituciones (separador decimal: coma)."""
    if x is None:
        return "—"
    if x == 0:
        return "0"
    ax = abs(x)
    if ax >= 1e7 or ax < 1e-3:
        s = f"{x:.{max(nd, 1)}e}"
    else:
        s = f"{x:.{nd}f}"
        if "." in s:
            s = s.rstrip("0").rstrip(".")
    return s.replace(".", ",")
