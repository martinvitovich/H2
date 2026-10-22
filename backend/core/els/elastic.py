"""Análisis elástico lineal de secciones para ELS (sección homogeneizada y fisurada).

Hipótesis: secciones planas, adherencia perfecta, materiales elásticos lineales. En la sección
fisurada se desprecia el hormigón traccionado. Las barras se homogeneizan con el coeficiente
α_e = E_s/E_c (con E_c = E_cm o E_c,eff según la duración de la carga, 7.3.4(2), 7.4.3(5)).
Orientación: fibra comprimida arriba para momento positivo (sign = +1); para momento negativo
se gira la sección (sign = −1). Profundidades y medidas desde la fibra comprimida.
"""

from __future__ import annotations

from dataclasses import dataclass

from scipy.optimize import brentq

from ..elu.analysis import oriented_geometry
from ..section import ReinforcedSection


@dataclass
class ElasticSection:
    yc: float        # profundidad del centro de gravedad (o de la fibra neutra si fisurada)
    I: float         # inercia homogeneizada respecto a yc (mm⁴, unidades de hormigón)
    A: float         # área homogeneizada (mm²)
    S_s: float       # momento estático de la armadura respecto a yc (mm³), para (7.21)
    h: float
    cracked: bool

    def stress_concrete_top(self, M: float, Ec: float) -> float:
        """Tensión en la fibra comprimida (MPa, compresión +) para M en N·mm (con M > 0)."""
        return M * self.yc / self.I

    def stress_steel(self, M: float, y: float, alpha: float) -> float:
        """Tensión en una barra a profundidad y (tracción +)."""
        return alpha * M * (y - self.yc) / self.I


def uncracked(section: ReinforcedSection, alpha: float, sign: int = 1) -> ElasticSection:
    segs, bars, h = oriented_geometry(section, sign)
    A = Sy = 0.0
    for s in segs:
        a = s.width * (s.y_bot - s.y_top)
        A += a
        Sy += a * (s.y_top + s.y_bot) / 2
    for b in bars:
        A += (alpha - 1.0) * b.area
        Sy += (alpha - 1.0) * b.area * b.y
    yc = Sy / A
    I = 0.0
    for s in segs:
        t = s.y_bot - s.y_top
        I += s.width * t ** 3 / 12 + s.width * t * ((s.y_top + s.y_bot) / 2 - yc) ** 2
    for b in bars:
        I += (alpha - 1.0) * b.area * (b.y - yc) ** 2
    S_s = sum(b.area * (b.y - yc) for b in bars)
    return ElasticSection(yc, I, A, S_s, h, False)


def cracked(section: ReinforcedSection, alpha: float, sign: int = 1) -> ElasticSection:
    """Sección totalmente fisurada en flexión simple: fibra neutra por equilibrio de momentos
    estáticos (Σ S = 0) con el hormigón traccionado despreciado."""
    segs, bars, h = oriented_geometry(section, sign)

    def static_moment(x: float) -> float:
        S = 0.0
        for s in segs:
            a, b_ = s.y_top, min(s.y_bot, x)
            if b_ > a:
                S += s.width * (b_ - a) * (x - (a + b_) / 2)
        for b in bars:
            k = (alpha - 1.0) if b.y < x else alpha
            S += k * b.area * (x - b.y)
        return S

    if not any(b.y > 0 for b in bars) or static_moment(h) <= 0:
        raise ValueError("La sección fisurada no tiene armadura traccionada suficiente")
    x = brentq(static_moment, 1e-9 * h, h, xtol=1e-10, rtol=1e-14)
    I = 0.0
    for s in segs:
        a, b_ = s.y_top, min(s.y_bot, x)
        if b_ > a:
            t = b_ - a
            I += s.width * t ** 3 / 12 + s.width * t * ((a + b_) / 2 - x) ** 2
    for b in bars:
        k = (alpha - 1.0) if b.y < x else alpha
        I += k * b.area * (b.y - x) ** 2
    A = sum(s.width * max(min(s.y_bot, x) - s.y_top, 0) for s in segs) + \
        sum(((alpha - 1.0) if b.y < x else alpha) * b.area for b in bars)
    S_s = sum(b.area * (b.y - x) for b in bars)
    return ElasticSection(x, I, A, S_s, h, True)


def cracking_moment(section: ReinforcedSection, alpha: float, fct: float, sign: int = 1) -> tuple[float, ElasticSection]:
    """Momento de fisuración M_cr = f_ct·I_I/(h − y_I) con la sección homogeneizada sin fisurar."""
    un = uncracked(section, alpha, sign)
    return fct * un.I / (un.h - un.yc), un
