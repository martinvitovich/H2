"""Análisis seccional en ELU por compatibilidad de deformaciones y equilibrio.

Método general para flexión simple (N_Ed = 0) de secciones con ancho constante
por tramos (rectangulares y en T), según las hipótesis de Anejo 19, 6.1:

* secciones planas (6.1(2));
* adherencia perfecta entre acero y hormigón (6.1(2));
* resistencia a tracción del hormigón despreciada (6.1(2));
* hormigón: diagrama parábola-rectángulo (3.1.7(1), expresiones (3.17)-(3.18)) o
  bloque rectangular (3.1.7(3), expresiones (3.19)-(3.22));
* acero: diagrama bilineal de cálculo de 3.2.7(2) con rama superior horizontal
  (sin límite de deformación) o inclinada (limitada a ε_ud);
* deformaciones límite (6.1(3), figura A19.6.1): ε_cu2 (ε_cu3 con bloque rectangular)
  en la fibra más comprimida y ε_ud en la armadura más traccionada si la rama es inclinada.

Convenio: la fibra comprimida está arriba en el sistema orientado; los
acortamientos y las fuerzas de compresión son positivos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from scipy.integrate import quad
from scipy.optimize import brentq

from ..materials import Concrete, ReinforcingSteel
from ..section import ReinforcedSection, Segment

Diagram = Literal["parabola-rectangulo", "rectangular"]


class AnalysisError(ValueError):
    pass


@dataclass
class OrientedBar:
    y: float          # profundidad desde la fibra comprimida (mm)
    area: float
    diameter: float
    face: str         # cara en la sección original
    tension_side: bool


@dataclass
class BarState:
    y: float
    area: float
    diameter: float
    face: str
    strain: float      # alargamiento (+) / acortamiento (−)
    stress: float      # tracción (+) / compresión (−), MPa
    force: float       # tracción (+) / compresión (−), N
    yielded: bool


@dataclass
class BendingResult:
    diagram: Diagram
    sign: int
    x: float
    d: float
    eps_top: float
    pivot: str
    Fc: float
    zc: float              # profundidad de la resultante del hormigón
    M_Rd: float            # N·mm, con signo
    residual_N: float      # N, residuo de equilibrio
    eta_reduction: bool
    bars: list[BarState] = field(default_factory=list)

    @property
    def xi(self) -> float:
        return self.x / self.d

    def to_dict(self) -> dict:
        return {
            "diagram": self.diagram, "sign": self.sign, "x": self.x, "d": self.d,
            "xi": self.xi, "eps_top": self.eps_top, "pivot": self.pivot, "Fc": self.Fc,
            "zc": self.zc, "M_Rd": self.M_Rd, "residual_N": self.residual_N,
            "eta_reduction": self.eta_reduction,
            "bars": [b.__dict__ for b in self.bars],
        }


def oriented_geometry(section: ReinforcedSection, sign: int) -> tuple[list[Segment], list[OrientedBar], float]:
    """Devuelve los segmentos y las barras con la fibra comprimida arriba."""
    h = section.shape.h
    if sign > 0:
        segs = section.shape.segments()
        bars = [OrientedBar(b.y, b.area, b.diameter, b.face, b.face == "inferior") for b in section.bars]
    else:
        segs = section.shape.mirrored_segments()
        bars = [OrientedBar(h - b.y, b.area, b.diameter, b.face, b.face == "superior") for b in section.bars]
    return segs, bars, h


def width_decreases_towards_compressed_fibre(segs: list[Segment], depth: float) -> bool:
    """Nota de 3.1.7(3): reducción del 10 % de η·f_cd si el ancho de la zona comprimida
    disminuye hacia la fibra más comprimida."""
    inside = [s for s in segs if s.y_top < depth - 1e-9]
    return any(inside[i].width < inside[i + 1].width - 1e-9 for i in range(len(inside) - 1))


def _concrete_pr(segs, conc: Concrete, x: float, eps_top: float, h: float) -> tuple[float, float]:
    """Fuerza (N) y momento respecto a la fibra superior (N·mm) del hormigón comprimido,
    diagrama parábola-rectángulo, integrado por tramos con ``scipy.integrate.quad``."""
    depth = min(x, h)
    breaks = [0.0, depth]
    if eps_top > conc.eps_c2:
        yc2 = x * (1.0 - conc.eps_c2 / eps_top)
        if 0 < yc2 < depth:
            breaks.append(yc2)
    for s in segs:
        for yb in (s.y_top, s.y_bot):
            if 0 < yb < depth:
                breaks.append(yb)
    breaks = sorted(set(breaks))

    def sig(y: float) -> float:
        return conc.sigma_parabola_rectangle(min(eps_top * (1.0 - y / x), conc.eps_cu2))

    F = M = 0.0
    for a, b in zip(breaks[:-1], breaks[1:]):
        w = next(s.width for s in segs if s.y_top - 1e-9 <= (a + b) / 2 <= s.y_bot + 1e-9)
        F += w * quad(sig, a, b, epsabs=1e-10, epsrel=1e-12, limit=200)[0]
        M += w * quad(lambda y: sig(y) * y, a, b, epsabs=1e-10, epsrel=1e-12, limit=200)[0]
    return F, M


def _concrete_block(segs, conc: Concrete, x: float, h: float, eta_red: bool) -> tuple[float, float, float]:
    depth = min(conc.lam * x, h)
    stress = conc.eta * conc.fcd * (0.9 if eta_red else 1.0)
    F = M = 0.0
    for s in segs:
        a, b = s.y_top, min(s.y_bot, depth)
        if b > a:
            F += stress * s.width * (b - a)
            M += stress * s.width * (b * b - a * a) / 2
    return F, M, stress


def analyse_bending(section: ReinforcedSection, conc: Concrete, steel: ReinforcingSteel,
                    sign: int = 1, diagram: Diagram = "parabola-rectangulo") -> BendingResult:
    """Momento resistente último en flexión simple (N = 0)."""
    if sign not in (1, -1):
        raise AnalysisError("sign debe ser +1 (tracción inferior) o −1 (tracción superior)")
    segs, bars, h = oriented_geometry(section, sign)
    tens = [b for b in bars if b.tension_side]
    if not tens:
        raise AnalysisError("No hay armadura en la cara traccionada: la sección no puede "
                            "resistir el momento (resistencia a tracción del hormigón despreciada)")
    d = sum(b.area * b.y for b in tens) / sum(b.area for b in tens)
    y_max = max(b.y for b in bars)
    eps_cu = conc.eps_cu2 if diagram == "parabola-rectangulo" else conc.eps_cu3

    def eps_top_of(x: float) -> tuple[float, str]:
        if steel.eps_ud is not None and y_max > x:
            e = steel.eps_ud * x / (y_max - x)
            if e < eps_cu:
                return e, "A"   # agotamiento por deformación excesiva del acero
        return eps_cu, "B"      # agotamiento por compresión del hormigón

    def state(x: float, eta_red: bool):
        et, piv = eps_top_of(x)
        if diagram == "parabola-rectangulo":
            Fc, Mc = _concrete_pr(segs, conc, x, et, h)
            sigma_c = lambda y: conc.sigma_parabola_rectangle(min(et * (1 - y / x), conc.eps_cu2)) if y < x else 0.0
        else:
            Fc, Mc, sblk = _concrete_block(segs, conc, x, h, eta_red)
            sigma_c = lambda y: sblk if y <= conc.lam * x else 0.0
        st = []
        N = Fc
        Mtop = Mc
        for b in bars:
            eps_short = et * (1.0 - b.y / x)
            s = steel.sigma(-eps_short)
            F = s * b.area                      # tracción +
            Fcomp = -F - sigma_c(b.y) * b.area  # descuento del hormigón desplazado
            N += Fcomp
            Mtop += Fcomp * b.y
            st.append(BarState(b.y, b.area, b.diameter, b.face, -eps_short, s, -Fcomp,
                               abs(eps_short) >= steel.eps_yd * (1 - 1e-9)))
        return N, Mtop, Fc, Mc, et, piv, st

    eta_red = False
    for _ in range(2):
        f = lambda x: state(x, eta_red)[0]
        lo, hi = 1e-6 * h, h
        f_lo, f_hi = f(lo), f(hi)
        if f_lo > 0:
            raise AnalysisError("No se encontró equilibrio: armadura de tracción insuficiente")
        if f_hi < 0:
            raise AnalysisError("No se encontró equilibrio en flexión simple con la fibra neutra "
                                "dentro de la sección")
        x = brentq(f, lo, hi, xtol=1e-10, rtol=1e-13, maxiter=500)
        depth = conc.lam * x if diagram == "rectangular" else x
        need = diagram == "rectangular" and width_decreases_towards_compressed_fibre(segs, depth)
        if need == eta_red:
            break
        eta_red = need

    N, Mtop, Fc, Mc, et, piv, st = state(x, eta_red)
    if diagram == "rectangular" and piv == "A":
        raise AnalysisError("El bloque rectangular no es aplicable cuando el agotamiento lo "
                            "produce la deformación del acero (pivote A)")
    M_Rd = -Mtop * sign
    return BendingResult(diagram, sign, x, d, et, piv, Fc, Mc / Fc if Fc else 0.0, M_Rd, N,
                         eta_red, st)
