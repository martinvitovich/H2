"""Flexión compuesta recta: resistencia de secciones a esfuerzo axil y momento (N–M).

Método general de Anejo 19, 6.1: secciones planas, adherencia perfecta, tracción del hormigón
despreciada, diagrama parábola-rectángulo (3.1.7(1)) y diagrama del acero de 3.2.7(2).
Los planos de deformación últimos recorren los dominios de la figura A19.6.1:

* Pivote A: deformación de la armadura más traccionada igual al límite ε_s,lím.
* Pivote B: deformación ε_cu2 en la fibra más comprimida.
* Pivote C: deformación ε_c2 a una profundidad (1 − ε_c2/ε_cu2)·h (6.1(3), figura A19.6.1).

ε_s,lím = ε_ud con la rama inclinada. Con la rama horizontal el Anejo no limita la deformación
del acero (3.2.7(2) b)); para recorrer numéricamente el dominio A se usa un límite numérico
alto (parámetro no normativo ``EPS_NUMERIC_HORIZONTAL``), cuyo efecto sobre la envolvente es
despreciable y del lado de la seguridad.

Convenio: N positivo = compresión; M positivo = compresión en la fibra superior (momento que
tracciona la cara inferior), respecto al centro de gravedad de la sección bruta de hormigón.
"""

from __future__ import annotations

from dataclasses import dataclass

from scipy.integrate import quad
from scipy.optimize import brentq

from ..materials import Concrete, ReinforcingSteel
from ..section import ReinforcedSection
from .analysis import oriented_geometry

EPS_NUMERIC_HORIZONTAL = 0.10  # 100 ‰: límite numérico para recorrer el dominio A (no normativo)


class NMError(ValueError):
    pass


@dataclass
class NMPoint:
    t: float
    eps_top: float
    eps_bot: float
    N: float       # N (compresión +)
    M: float       # N·mm
    domain: str


class NMSection:
    """Sección orientada (fibra comprimida arriba para sign = +1)."""

    def __init__(self, section: ReinforcedSection, conc: Concrete, steel: ReinforcingSteel, sign: int = 1):
        if sign not in (1, -1):
            raise NMError("sign debe ser ±1")
        self.sign = sign
        self.conc, self.steel = conc, steel
        self.segs, self.bars, self.h = oriented_geometry(section, sign)
        if not self.bars:
            raise NMError("La sección no tiene armadura")
        shape = section.shape
        self.yg = shape.centroid_y if sign > 0 else shape.h - shape.centroid_y
        self.y_deep = max(b.y for b in self.bars)
        self.eps_s_lim = steel.eps_ud if steel.eps_ud is not None else EPS_NUMERIC_HORIZONTAL
        self.yC = (1.0 - conc.eps_c2 / conc.eps_cu2) * self.h

    # --- integración de un plano de deformación ε(y) = ε_t + (ε_b − ε_t)·y/h (acortamiento +) ---
    def forces(self, eps_top: float, eps_bot: float) -> tuple[float, float]:
        c, h = self.conc, self.h

        def eps(y: float) -> float:
            return eps_top + (eps_bot - eps_top) * y / h

        def sig(y: float) -> float:
            e = eps(y)
            if e <= 0:
                return 0.0
            return c.sigma_parabola_rectangle(min(e, c.eps_cu2))

        breaks = {0.0, h}
        for s in self.segs:
            breaks.update((s.y_top, s.y_bot))
        de = eps_bot - eps_top
        if abs(de) > 1e-15:
            for target in (0.0, c.eps_c2):
                y = (target - eps_top) * h / de
                if 0 < y < h:
                    breaks.add(y)
        pts = sorted(breaks)
        N = M = 0.0
        for a, b in zip(pts[:-1], pts[1:]):
            if b - a < 1e-12:
                continue
            ym = (a + b) / 2
            if eps(ym) <= 0:
                continue
            w = next(s.width for s in self.segs if s.y_top - 1e-9 <= ym <= s.y_bot + 1e-9)
            N += w * quad(sig, a, b, epsabs=1e-6, epsrel=1e-10, limit=200)[0]
            M += w * quad(lambda y: sig(y) * (self.yg - y), a, b, epsabs=1e-6, epsrel=1e-10, limit=200)[0]
        for bar in self.bars:
            e = eps(bar.y)
            s_steel = -self.steel.sigma(-e)            # compresión + en MPa
            s_conc = sig(bar.y)                         # hormigón desplazado
            F = (s_steel - s_conc) * bar.area
            N += F
            M += F * (self.yg - bar.y)
        return N, M * self.sign

    # --- planos de deformación últimos parametrizados por t ∈ [0, 3] ---
    def plane(self, t: float) -> tuple[float, float, str]:
        c = self.conc
        es, h, yd = self.eps_s_lim, self.h, self.y_deep
        if t <= 1.0:
            # Pivote A: armadura más profunda a −ε_s,lím; ε_top de −ε_s,lím a ε_cu2
            et = -es + t * (c.eps_cu2 + es)
            eb = et + (-es - et) * h / yd
            return et, eb, "A"
        if t <= 2.0:
            # Pivote B: ε_top = ε_cu2; profundidad de la fibra neutra de x_AB a h
            x_ab = c.eps_cu2 / (c.eps_cu2 + es) * yd
            x = x_ab + (t - 1.0) * (h - x_ab)
            et = c.eps_cu2
            eb = et * (x - h) / x
            return et, eb, "B"
        # Pivote C: giro alrededor de (y_C, ε_c2), de x = h (ε_b = 0) a compresión uniforme ε_c2
        u = min(t - 2.0, 1.0)
        eb = u * c.eps_c2
        # recta por (y_C, ε_c2) y (h, eb)
        slope = (eb - c.eps_c2) / (h - self.yC)
        et = c.eps_c2 - slope * self.yC
        return et, eb, "C"

    def point(self, t: float) -> NMPoint:
        et, eb, dom = self.plane(t)
        N, M = self.forces(et, eb)
        return NMPoint(t, et, eb, N, M, dom)

    def N_range(self) -> tuple[float, float]:
        return self.point(0.0).N, self.point(3.0).N

    def resistance_at(self, N: float) -> NMPoint:
        """Plano último con axil N y su momento resistente (sentido de esta orientación)."""
        n0, n3 = self.N_range()
        if N < n0 - 1e-6 or N > n3 + 1e-6:
            raise NMError("El axil está fuera del rango resistente de la sección "
                          f"[{n0 / 1e3:.1f}; {n3 / 1e3:.1f}] kN")
        if abs(N - n3) < 1e-6:
            return self.point(3.0)
        if abs(N - n0) < 1e-6:
            return self.point(0.0)
        t = brentq(lambda t: self.point(t).N - N, 0.0, 3.0, xtol=1e-12, rtol=1e-14, maxiter=300)
        return self.point(t)

    def curve(self, n: int = 40) -> list[NMPoint]:
        ts = [3.0 * i / n for i in range(n + 1)]
        # refinar el dominio A (donde la fibra neutra cambia rápidamente)
        ts += [0.98 + 0.02 * i / 10 for i in range(10)]
        return [self.point(t) for t in sorted(set(ts))]


def interaction_diagram(section: ReinforcedSection, conc: Concrete, steel: ReinforcingSteel,
                        n: int = 40) -> list[dict]:
    """Envolvente N–M completa (ambos signos de M), ordenada para dibujarla como polígono."""
    pos = NMSection(section, conc, steel, 1).curve(n)
    neg = NMSection(section, conc, steel, -1).curve(n)
    pts = [{"N": p.N, "M": p.M, "domain": p.domain} for p in pos]
    pts += [{"N": p.N, "M": p.M, "domain": p.domain} for p in reversed(neg)]
    return pts
