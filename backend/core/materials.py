"""Materiales: hormigón (Anejo 19, 3.1) y acero para armaduras pasivas (3.2).

Convenio de signos de este módulo: las funciones de tensión-deformación del
hormigón reciben la deformación de acortamiento como valor POSITIVO y devuelven
la tensión de compresión como valor POSITIVO. Las del acero son simétricas:
deformación positiva = alargamiento, tensión positiva = tracción.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

from .parameters import ParameterSet, VerificationStatus
from .trace import CalcTrace, fmt
from .units import PERMIL

# Clases resistentes de la tabla 3.1 del Anejo 19 (f_ck en MPa).
CONCRETE_FCK_CLASSES: dict[str, float] = {
    "C12/15": 12, "C16/20": 16, "C20/25": 20, "C25/30": 25, "C30/37": 30,
    "C35/45": 35, "C40/50": 40, "C45/55": 45, "C50/60": 50, "C55/67": 55,
    "C60/75": 60, "C70/85": 70, "C80/95": 80, "C90/105": 90,
}

TABLE_3_1 = "Anejo 19, 3.1.2–3.1.3, tabla 3.1"


class MaterialError(ValueError):
    pass


@dataclass
class Concrete:
    """Hormigón definido por su resistencia característica f_ck (MPa)."""

    fck: float
    params: ParameterSet = field(default_factory=ParameterSet)
    situation: str = "persistente"
    name: str = ""

    def __post_init__(self) -> None:
        if not (12.0 <= self.fck <= 90.0):
            raise MaterialError(
                f"f_ck = {self.fck} MPa fuera del rango de la tabla 3.1 (12–90 MPa)"
            )
        if not self.name:
            self.name = next((k for k, v in CONCRETE_FCK_CLASSES.items() if v == self.fck),
                             f"f_ck = {self.fck:g} MPa")

    @classmethod
    def from_class(cls, cls_name: str, params: ParameterSet | None = None,
                   situation: str = "persistente") -> "Concrete":
        if cls_name not in CONCRETE_FCK_CLASSES:
            raise MaterialError(f"Clase de hormigón desconocida: {cls_name}")
        return cls(CONCRETE_FCK_CLASSES[cls_name], params or ParameterSet(), situation, cls_name)

    # --- Tabla 3.1: relaciones analíticas ---
    @property
    def high_strength(self) -> bool:
        return self.fck > 50.0

    @property
    def fcm(self) -> float:
        return self.fck + 8.0

    @property
    def fctm(self) -> float:
        if self.fck <= 50.0:
            return 0.30 * self.fck ** (2.0 / 3.0)
        return 2.12 * math.log(1.0 + self.fcm / 10.0)

    @property
    def fctk_005(self) -> float:
        return 0.7 * self.fctm

    @property
    def fctk_095(self) -> float:
        return 1.3 * self.fctm

    @property
    def Ecm(self) -> float:
        """Módulo de elasticidad secante (MPa): 22·(f_cm/10)^0,3 GPa."""
        return 22000.0 * (self.fcm / 10.0) ** 0.3

    @property
    def eps_c1(self) -> float:
        return min(0.7 * self.fcm ** 0.31, 2.8) * PERMIL

    @property
    def eps_cu1(self) -> float:
        if self.fck <= 50.0:
            return 3.5 * PERMIL
        return (2.8 + 27.0 * ((98.0 - self.fcm) / 100.0) ** 4) * PERMIL

    @property
    def eps_c2(self) -> float:
        if self.fck <= 50.0:
            return 2.0 * PERMIL
        return (2.0 + 0.085 * (self.fck - 50.0) ** 0.53) * PERMIL

    @property
    def eps_cu2(self) -> float:
        if self.fck <= 50.0:
            return 3.5 * PERMIL
        return (2.6 + 35.0 * ((90.0 - self.fck) / 100.0) ** 4) * PERMIL

    @property
    def n(self) -> float:
        if self.fck <= 50.0:
            return 2.0
        return 1.4 + 23.4 * ((90.0 - self.fck) / 100.0) ** 4

    @property
    def eps_c3(self) -> float:
        if self.fck <= 50.0:
            return 1.75 * PERMIL
        return (1.75 + 0.55 * (self.fck - 50.0) / 40.0) * PERMIL

    @property
    def eps_cu3(self) -> float:
        return self.eps_cu2

    # --- Resistencias de cálculo (3.1.6) ---
    @property
    def gamma_c(self) -> float:
        return self.params.gamma_c(self.situation)

    @property
    def alpha_cc(self) -> float:
        return self.params["alpha_cc"]

    @property
    def alpha_ct(self) -> float:
        return self.params["alpha_ct"]

    @property
    def fcd(self) -> float:
        return self.alpha_cc * self.fck / self.gamma_c

    @property
    def fctd(self) -> float:
        return self.alpha_ct * self.fctk_005 / self.gamma_c

    # --- Bloque rectangular (3.1.7(3)) ---
    @property
    def lam(self) -> float:
        if self.fck <= 50.0:
            return 0.8
        return 0.8 - (self.fck - 50.0) / 400.0

    @property
    def eta(self) -> float:
        if self.fck <= 50.0:
            return 1.0
        return 1.0 - (self.fck - 50.0) / 200.0

    # --- Diagramas tensión-deformación ---
    def sigma_parabola_rectangle(self, eps: float) -> float:
        """Diagrama parábola-rectángulo de cálculo, expresiones (3.17)-(3.18).

        ``eps`` es el acortamiento (positivo). Las tracciones se desprecian (6.1(2)).
        """
        if eps <= 0.0:
            return 0.0
        if eps > self.eps_cu2 * (1 + 1e-9):
            raise MaterialError("Deformación de compresión superior a ε_cu2")
        if eps < self.eps_c2:
            return self.fcd * (1.0 - (1.0 - eps / self.eps_c2) ** self.n)
        return self.fcd

    def sigma_nonlinear_analysis(self, eps: float) -> float:
        """Relación (3.14) para análisis estructural no lineal (valores medios).

        No se emplea para el dimensionado de secciones; se ofrece con fines
        ilustrativos en el módulo de materiales.
        """
        if eps <= 0.0:
            return 0.0
        if eps > self.eps_cu1 * (1 + 1e-9):
            raise MaterialError("Deformación superior a ε_cu1")
        k = 1.05 * self.Ecm * self.eps_c1 / self.fcm
        eta = eps / self.eps_c1
        return self.fcm * (k * eta - eta ** 2) / (1.0 + (k - 2.0) * eta)

    def properties(self) -> dict:
        return {
            "name": self.name, "fck": self.fck, "fcm": self.fcm, "fctm": self.fctm,
            "fctk_005": self.fctk_005, "fctk_095": self.fctk_095, "Ecm": self.Ecm,
            "eps_c1": self.eps_c1, "eps_cu1": self.eps_cu1, "eps_c2": self.eps_c2,
            "eps_cu2": self.eps_cu2, "n": self.n, "eps_c3": self.eps_c3,
            "eps_cu3": self.eps_cu3, "gamma_c": self.gamma_c, "alpha_cc": self.alpha_cc,
            "alpha_ct": self.alpha_ct, "fcd": self.fcd, "fctd": self.fctd,
            "lambda": self.lam, "eta": self.eta, "situation": self.situation,
        }

    def trace_design_values(self, tr: CalcTrace) -> None:
        g = tr.use_param(self.params, f"gamma_c_{'accidental' if self.situation == 'accidental' else 'persistente'}")
        a = tr.use_param(self.params, "alpha_cc")
        tr.step("Resistencia media a compresión", TABLE_3_1, "f_cm = f_ck + 8",
                f"f_cm = {fmt(self.fck)} + 8", self.fcm, "MPa", "f_cm")
        if self.fck <= 50:
            tr.step("Resistencia media a tracción", TABLE_3_1, "f_ctm = 0,30·f_ck^(2/3)",
                    f"f_ctm = 0,30·{fmt(self.fck)}^(2/3)", self.fctm, "MPa", "f_ctm")
        else:
            tr.step("Resistencia media a tracción", TABLE_3_1, "f_ctm = 2,12·ln(1 + f_cm/10)",
                    f"f_ctm = 2,12·ln(1 + {fmt(self.fcm)}/10)", self.fctm, "MPa", "f_ctm")
        tr.step("Resistencia de cálculo a compresión", "Anejo 19, 3.1.6(1), expresión (3.15)",
                "f_cd = α_cc·f_ck/γ_c", f"f_cd = {fmt(a)}·{fmt(self.fck)}/{fmt(g)}",
                self.fcd, "MPa", "f_cd")


# --- Acero para armaduras pasivas ---

# Designaciones habituales del Código Estructural. Las propiedades de ductilidad
# (ε_uk, k) se asocian a las clases B y C del apéndice C de la EN 1992-1-1 y deben
# verificarse contra el articulado del Código Estructural.
STEEL_GRADES: dict[str, dict] = {
    "B400S": {"fyk": 400.0, "eps_uk": 0.050, "k": 1.08},
    "B500S": {"fyk": 500.0, "eps_uk": 0.050, "k": 1.08},
    "B400SD": {"fyk": 400.0, "eps_uk": 0.075, "k": 1.15},
    "B500SD": {"fyk": 500.0, "eps_uk": 0.075, "k": 1.15},
}

SteelBranch = Literal["horizontal", "inclinada"]


@dataclass
class ReinforcingSteel:
    fyk: float
    eps_uk: float
    k: float
    params: ParameterSet = field(default_factory=ParameterSet)
    situation: str = "persistente"
    branch: SteelBranch = "horizontal"
    name: str = ""

    def __post_init__(self) -> None:
        if not (400.0 <= self.fyk <= 600.0):
            raise MaterialError("f_yk fuera del rango 400–600 MPa (Anejo 19, 3.2.2(3))")
        if not (0.01 <= self.eps_uk <= 0.2):
            raise MaterialError("ε_uk fuera de rango razonable (1–20 %)")
        if not (1.0 <= self.k <= 1.5):
            raise MaterialError("k = (f_t/f_y)_k fuera de rango (1,00–1,50)")
        if self.branch not in ("horizontal", "inclinada"):
            raise MaterialError("Rama superior del diagrama: 'horizontal' o 'inclinada'")
        if not self.name:
            self.name = f"f_yk = {self.fyk:g} MPa"

    @classmethod
    def from_grade(cls, grade: str, params: ParameterSet | None = None,
                   situation: str = "persistente", branch: SteelBranch = "horizontal") -> "ReinforcingSteel":
        if grade not in STEEL_GRADES:
            raise MaterialError(f"Acero desconocido: {grade}")
        g = STEEL_GRADES[grade]
        return cls(g["fyk"], g["eps_uk"], g["k"], params or ParameterSet(), situation, branch, grade)

    @property
    def Es(self) -> float:
        return self.params["Es"]

    @property
    def gamma_s(self) -> float:
        return self.params.gamma_s(self.situation)

    @property
    def fyd(self) -> float:
        return self.fyk / self.gamma_s

    @property
    def eps_yd(self) -> float:
        return self.fyd / self.Es

    @property
    def eps_ud(self) -> float | None:
        """Límite de deformación de cálculo; None si la rama es horizontal (sin límite)."""
        if self.branch == "horizontal":
            return None
        return self.params["eps_ud_factor"] * self.eps_uk

    @property
    def ftd_max(self) -> float:
        """Tensión de la rama inclinada para ε_uk: k·f_yk/γ_s (3.2.7(2) a)."""
        return self.k * self.fyk / self.gamma_s

    def sigma(self, eps: float) -> float:
        """Diagrama de cálculo (3.2.7(2), figura 3.8). Simétrico en tracción/compresión."""
        sgn = 1.0 if eps >= 0 else -1.0
        e = abs(eps)
        if e <= self.eps_yd:
            return eps * self.Es
        if self.branch == "horizontal":
            return sgn * self.fyd
        if e > self.eps_ud * (1 + 1e-9):
            raise MaterialError("Deformación del acero superior a ε_ud")
        slope = (self.ftd_max - self.fyd) / (self.eps_uk - self.eps_yd)
        return sgn * (self.fyd + slope * (e - self.eps_yd))

    def properties(self) -> dict:
        return {
            "name": self.name, "fyk": self.fyk, "eps_uk": self.eps_uk, "k": self.k,
            "Es": self.Es, "gamma_s": self.gamma_s, "fyd": self.fyd, "eps_yd": self.eps_yd,
            "eps_ud": self.eps_ud, "branch": self.branch, "situation": self.situation,
        }

    def trace_design_values(self, tr: CalcTrace) -> None:
        g = tr.use_param(self.params, f"gamma_s_{'accidental' if self.situation == 'accidental' else 'persistente'}")
        es = tr.use_param(self.params, "Es")
        tr.step("Límite elástico de cálculo", "Anejo 19, 3.2.7(2), figura 3.8",
                "f_yd = f_yk/γ_s", f"f_yd = {fmt(self.fyk)}/{fmt(g)}", self.fyd, "MPa", "f_yd")
        tr.step("Deformación de cedencia de cálculo", "Anejo 19, 3.2.7(2), figura 3.8",
                "ε_yd = f_yd/E_s", f"ε_yd = {fmt(self.fyd)}/{fmt(es, 0)}",
                self.eps_yd * 1000, "‰", "ε_yd")
        if self.branch == "inclinada":
            tr.use_param(self.params, "eps_ud_factor")
            tr.step("Deformación límite de cálculo", "Anejo 19, 3.2.7(2), nota",
                    "ε_ud = 0,9·ε_uk", f"ε_ud = {fmt(self.params['eps_ud_factor'])}·{fmt(self.eps_uk*1000)} ‰",
                    self.eps_ud * 1000, "‰", "ε_ud")


def stress_strain_curves(concrete: Concrete, steel: ReinforcingSteel, npts: int = 60) -> dict:
    """Puntos de los diagramas tensión-deformación para su representación gráfica."""
    pr = []
    for i in range(npts + 1):
        e = concrete.eps_cu2 * i / npts
        pr.append({"eps_permil": e * 1000, "sigma": concrete.sigma_parabola_rectangle(e)})
    nl = []
    for i in range(npts + 1):
        e = concrete.eps_cu1 * i / npts
        nl.append({"eps_permil": e * 1000, "sigma": concrete.sigma_nonlinear_analysis(e)})
    e_max = steel.eps_ud if steel.eps_ud is not None else max(10 * PERMIL, 5 * steel.eps_yd)
    st = []
    for i in range(npts + 1):
        e = e_max * i / npts
        st.append({"eps_permil": e * 1000, "sigma": steel.sigma(e)})
    # incluir explícitamente el punto de cedencia
    st.append({"eps_permil": steel.eps_yd * 1000, "sigma": steel.fyd})
    st.sort(key=lambda p: p["eps_permil"])
    return {"concrete_design": pr, "concrete_nonlinear": nl, "steel_design": st}
