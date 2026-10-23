"""Estática elemental de vigas isostáticas (equilibrio), usada para transmitir cargas en el
proyecto integral cuando el usuario elige el modelo «isostático».

No es un procedimiento del Anejo 19: es equilibrio estático de una viga biapoyada o de un voladizo
con carga uniforme y cargas puntuales. No considera continuidad, redistribución, alternancia de
sobrecargas ni rigidez de los apoyos. Unidades: m, kN/m, kN, kN·m.
"""

from __future__ import annotations

from dataclasses import dataclass, field

N_POINTS = 200  # puntos de evaluación a lo largo de la luz (además de los puntos de carga)


@dataclass
class BeamLoads:
    L: float                                                    # luz (m)
    w: float = 0.0                                              # carga uniforme (kN/m)
    points: list[tuple[float, float]] = field(default_factory=list)   # (posición desde el inicio (m), P (kN))


def _stations(L: float, points: list[tuple[float, float]]) -> list[float]:
    xs = {L * i / N_POINTS for i in range(N_POINTS + 1)}
    xs.update(a for a, _ in points if 0 <= a <= L)
    return sorted(xs)


def simply_supported(b: BeamLoads) -> dict:
    """Reacciones y leyes de esfuerzos de una viga biapoyada (apoyos en x = 0 y x = L)."""
    L = b.L
    Ri = b.w * L / 2 + sum(P * (L - a) / L for a, P in b.points)
    Rj = b.w * L / 2 + sum(P * a / L for a, P in b.points)
    xs = _stations(L, b.points)

    def M(x: float) -> float:
        return Ri * x - b.w * x * x / 2 - sum(P * (x - a) for a, P in b.points if a < x)

    return {"R_i": Ri, "R_j": Rj, "x": xs, "M": [M(x) for x in xs]}


def cantilever(b: BeamLoads) -> dict:
    """Voladizo empotrado en x = 0 y libre en x = L. Momento negativo (tracción superior)."""
    L = b.L
    R = b.w * L + sum(P for _, P in b.points)
    Mi = -(b.w * L * L / 2 + sum(P * a for a, P in b.points))
    xs = _stations(L, b.points)

    def M(x: float) -> float:
        return -(b.w * (L - x) ** 2 / 2 + sum(P * (a - x) for a, P in b.points if a > x))

    return {"R_i": R, "R_j": 0.0, "M_i": Mi, "x": xs, "M": [M(x) for x in xs]}
