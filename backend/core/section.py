"""Geometría de secciones de hormigón y disposición de armaduras longitudinales.

Sistema de coordenadas: ``y`` vertical medida desde la fibra SUPERIOR hacia
abajo (mm); ``x`` horizontal medida desde el borde izquierdo del rectángulo
envolvente (mm). Las secciones en T tienen el ala en la parte superior y el
alma centrada bajo ella.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

from .parameters import ParameterSet
from .trace import CalcTrace, fmt


class SectionError(ValueError):
    pass


Face = Literal["inferior", "superior", "lateral"]


@dataclass(frozen=True)
class Segment:
    """Franja horizontal de ancho constante entre y_top e y_bot."""

    y_top: float
    y_bot: float
    width: float


@dataclass
class Shape:
    kind: str
    h: float

    def segments(self) -> list[Segment]:  # pragma: no cover - abstracto
        raise NotImplementedError

    def width_at(self, y: float) -> float:
        for s in self.segments():
            if s.y_top <= y <= s.y_bot:
                return s.width
        return 0.0

    @property
    def bounding_width(self) -> float:
        return max(s.width for s in self.segments())

    @property
    def web_width(self) -> float:
        return min(s.width for s in self.segments())

    @property
    def area(self) -> float:
        return sum(s.width * (s.y_bot - s.y_top) for s in self.segments())

    @property
    def centroid_y(self) -> float:
        return sum(s.width * (s.y_bot - s.y_top) * (s.y_top + s.y_bot) / 2
                   for s in self.segments()) / self.area

    @property
    def inertia(self) -> float:
        """Momento de inercia bruto respecto al eje horizontal baricéntrico (mm⁴)."""
        yg = self.centroid_y
        tot = 0.0
        for s in self.segments():
            t = s.y_bot - s.y_top
            yc = (s.y_top + s.y_bot) / 2
            tot += s.width * t ** 3 / 12 + s.width * t * (yc - yg) ** 2
        return tot

    def mirrored_segments(self) -> list[Segment]:
        """Segmentos de la sección girada 180° (para momentos negativos)."""
        return sorted((Segment(self.h - s.y_bot, self.h - s.y_top, s.width) for s in self.segments()),
                      key=lambda s: s.y_top)

    def to_dict(self) -> dict:
        return {"kind": self.kind, "h": self.h}


@dataclass
class RectangularShape(Shape):
    b: float = 0.0

    def __init__(self, b: float, h: float) -> None:
        if b <= 0 or h <= 0:
            raise SectionError("Las dimensiones b y h deben ser positivas")
        super().__init__("rectangular", float(h))
        self.b = float(b)

    def segments(self) -> list[Segment]:
        return [Segment(0.0, self.h, self.b)]

    def to_dict(self) -> dict:
        return {"kind": self.kind, "b": self.b, "h": self.h}


@dataclass
class TShape(Shape):
    bf: float = 0.0
    hf: float = 0.0
    bw: float = 0.0

    def __init__(self, bf: float, hf: float, bw: float, h: float) -> None:
        if min(bf, hf, bw, h) <= 0:
            raise SectionError("Todas las dimensiones de la sección en T deben ser positivas")
        if hf >= h:
            raise SectionError("El espesor del ala h_f debe ser menor que el canto h")
        if bw > bf:
            raise SectionError("El ancho del alma b_w no puede superar el ancho del ala b_f")
        super().__init__("T", float(h))
        self.bf, self.hf, self.bw = float(bf), float(hf), float(bw)

    def segments(self) -> list[Segment]:
        return [Segment(0.0, self.hf, self.bf), Segment(self.hf, self.h, self.bw)]

    def to_dict(self) -> dict:
        return {"kind": self.kind, "bf": self.bf, "hf": self.hf, "bw": self.bw, "h": self.h}


@dataclass
class Bar:
    x: float
    y: float
    diameter: float
    layer: int
    face: Face

    @property
    def area(self) -> float:
        return math.pi * self.diameter ** 2 / 4.0


@dataclass
class Layer:
    face: Face
    n: int
    diameter: float
    depth: float | None = None  # distancia desde la cara al centro de las barras (opcional)

    def validate(self) -> None:
        if self.face not in ("inferior", "superior", "lateral"):
            raise SectionError("La cara de la capa debe ser 'inferior', 'superior' o 'lateral'")
        if self.face == "lateral" and self.depth is not None:
            raise SectionError("Las barras laterales se reparten automáticamente: no admiten profundidad")
        if self.n < 1 or self.n > 30:
            raise SectionError("El número de barras por capa debe estar entre 1 y 30")
        if self.face == "inferior" and self.n < 2:
            raise SectionError("Una capa de armadura principal requiere al menos 2 barras (esquinas de estribo)")
        if not (5.0 <= self.diameter <= 40.0):
            raise SectionError("Diámetro de barra fuera del rango 5–40 mm")
        if self.depth is not None and self.depth <= 0:
            raise SectionError("La profundidad de la capa debe ser positiva")

    @property
    def area(self) -> float:
        return self.n * math.pi * self.diameter ** 2 / 4.0


def min_clear_spacing(diameter: float, dg: float, params: ParameterSet) -> float:
    """Separación libre mínima entre barras paralelas, Anejo 19, 8.2(2)."""
    return max(params["spacing_k1"] * diameter, dg + params["spacing_k2"], params["spacing_abs_min"])


@dataclass
class ReinforcedSection:
    shape: Shape
    cover: float              # recubrimiento nominal hasta la superficie del estribo (mm)
    stirrup_diameter: float   # φ_t (mm); 0 si no hay estribos
    layers: list[Layer]
    dg: float = 20.0          # tamaño máximo del árido (mm)
    params: ParameterSet = field(default_factory=ParameterSet)
    bars: list[Bar] = field(init=False, default_factory=list)
    issues: list[str] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        if self.cover < 0:
            raise SectionError("El recubrimiento no puede ser negativo")
        if self.stirrup_diameter < 0 or self.stirrup_diameter > 20:
            raise SectionError("Diámetro de estribo fuera de rango (0–20 mm)")
        if not (4.0 <= self.dg <= 63.0):
            raise SectionError("Tamaño máximo del árido fuera de rango (4–63 mm)")
        for L in self.layers:
            L.validate()
        self._place_bars()

    # --- colocación de barras ---
    def _place_bars(self) -> None:
        self.bars = []
        self.issues = []
        bw = self.shape.web_width
        x0 = (self.shape.bounding_width - bw) / 2.0
        edge = self.cover + self.stirrup_diameter
        for face in ("inferior", "superior"):
            prev_depth = None
            first_xs: list[float] | None = None
            prev_diam = None
            for idx, L in enumerate([l for l in self.layers if l.face == face]):
                if L.depth is not None:
                    depth = L.depth
                elif prev_depth is None:
                    depth = edge + L.diameter / 2
                else:
                    sv = min_clear_spacing(max(L.diameter, prev_diam), self.dg, self.params)
                    depth = prev_depth + prev_diam / 2 + sv + L.diameter / 2
                if depth - L.diameter / 2 < edge - 1e-9:
                    self.issues.append(f"Capa {idx + 1} ({face}): las barras invaden el recubrimiento indicado")
                if prev_depth is not None:
                    clear_v = depth - prev_depth - (L.diameter + prev_diam) / 2
                    smin = min_clear_spacing(max(L.diameter, prev_diam), self.dg, self.params)
                    if clear_v < smin - 1e-9:
                        self.issues.append(
                            f"Capa {idx + 1} ({face}): separación libre vertical {clear_v:.1f} mm < s_min = {smin:.1f} mm (8.2(2))")
                y = self.shape.h - depth if face == "inferior" else depth
                xa = x0 + edge + L.diameter / 2
                xb = x0 + bw - edge - L.diameter / 2
                if xb < xa - 1e-9 or (L.n > 1 and xb - xa < 1e-9):
                    raise SectionError(f"Capa {idx + 1} ({face}): las barras no caben en el ancho disponible")
                xs = [(xa + xb) / 2] if L.n == 1 else [xa + i * (xb - xa) / (L.n - 1) for i in range(L.n)]
                if first_xs is None:
                    first_xs = xs
                else:
                    # 8.2(3): las barras de cada capa, en la misma vertical que las de la primera
                    N = len(first_xs)
                    cols = sorted({round(i * (N - 1) / (L.n - 1)) for i in range(L.n)}) if 2 <= L.n <= N else []
                    if len(cols) == L.n:
                        xs = [first_xs[c] for c in cols]
                        if min(xs) - L.diameter / 2 < x0 + edge - 1e-9 or \
                                max(xs) + L.diameter / 2 > x0 + bw - edge + 1e-9:
                            self.issues.append(
                                f"Capa {idx + 1} ({face}): al alinear las barras con la primera capa "
                                "invaden el recubrimiento lateral")
                    else:
                        self.issues.append(
                            f"Capa {idx + 1} ({face}) de {L.n}φ{L.diameter:g}: las barras no pueden quedar en "
                            "la misma vertical que las de la primera capa (8.2(3))")
                if L.n > 1:
                    clear_h = min(b - a for a, b in zip(xs, xs[1:])) - L.diameter
                    smin = min_clear_spacing(L.diameter, self.dg, self.params)
                    if clear_h < smin - 1e-9:
                        self.issues.append(
                            f"Capa {idx + 1} ({face}): separación libre horizontal {clear_h:.1f} mm < s_min = {smin:.1f} mm (8.2(2))")
                for x in xs:
                    self.bars.append(Bar(x, y, L.diameter, idx + 1, face))
                prev_depth, prev_diam = depth, L.diameter
        self._place_lateral(x0, bw, edge)
        for b in self.bars:
            if not (0 < b.y < self.shape.h):
                raise SectionError("Hay barras fuera del canto de la sección")
        bot = [b for b in self.bars if b.face == "inferior"]
        top = [b for b in self.bars if b.face == "superior"]
        if bot and top:
            if min(b.y - b.diameter / 2 for b in bot) <= max(b.y + b.diameter / 2 for b in top):
                raise SectionError("Las armaduras superior e inferior se solapan")

    def _place_lateral(self, x0: float, bw: float, edge: float) -> None:
        """Barras intermedias en cada cara lateral: n por cara, repartidas uniformemente entre la
        primera capa superior y la primera capa inferior (pilares, armadura de piel)."""
        lat = [l for l in self.layers if l.face == "lateral"]
        if not lat:
            return
        if len(lat) > 1:
            raise SectionError("Defina una sola capa lateral (n barras por cara lateral)")
        L = lat[0]
        top = [b for b in self.bars if b.face == "superior" and b.layer == 1]
        bot = [b for b in self.bars if b.face == "inferior" and b.layer == 1]
        if not top or not bot:
            raise SectionError("Las barras laterales requieren armadura en las caras superior e inferior")
        ya, yb = top[0].y, bot[0].y
        step = (yb - ya) / (L.n + 1)
        smin = min_clear_spacing(L.diameter, self.dg, self.params)
        dmax = max(L.diameter, top[0].diameter, bot[0].diameter)
        if step - (L.diameter + dmax) / 2 < smin - 1e-9:
            self.issues.append(f"Barras laterales: separación libre vertical {step - (L.diameter + dmax) / 2:.1f} mm "
                               f"< s_min = {smin:.1f} mm (8.2(2))")
        xl = x0 + edge + L.diameter / 2
        xr = x0 + bw - edge - L.diameter / 2
        for i in range(1, L.n + 1):
            y = ya + i * step
            self.bars.append(Bar(xl, y, L.diameter, 1, "lateral"))
            self.bars.append(Bar(xr, y, L.diameter, 1, "lateral"))

    # --- propiedades ---
    def bars_on(self, face: Face) -> list[Bar]:
        return [b for b in self.bars if b.face == face]

    def area_on(self, face: Face) -> float:
        return sum(b.area for b in self.bars_on(face))

    def centroid_depth(self, face: Face) -> float | None:
        """Profundidad del centro de gravedad de las barras de una cara medida desde la
        fibra opuesta (es decir, la profundidad útil ``d`` para la cara traccionada)."""
        bars = self.bars_on(face)
        if not bars:
            return None
        a = sum(b.area for b in bars)
        yc = sum(b.area * b.y for b in bars) / a
        return yc if face == "inferior" else self.shape.h - yc

    @property
    def d(self) -> float | None:
        """Canto útil para momento positivo (tracción en la cara inferior)."""
        return self.centroid_depth("inferior")

    def geometric_properties(self) -> dict:
        s = self.shape
        As_inf = self.area_on("inferior")
        As_sup = self.area_on("superior")
        return {
            "shape": s.to_dict(),
            "Ac": s.area,
            "yg": s.centroid_y,
            "Ig": s.inertia,
            "As_inferior": As_inf,
            "As_superior": As_sup,
            "As_lateral": self.area_on("lateral"),
            "As_total": sum(b.area for b in self.bars),
            "d_inferior": self.centroid_depth("inferior"),
            "d_superior": self.centroid_depth("superior"),
            "bars": [b.__dict__ for b in self.bars],
            "issues": list(self.issues),
            "min_clear_spacing": {str(int(L.diameter)): min_clear_spacing(L.diameter, self.dg, self.params)
                                  for L in self.layers},
        }

    def trace_geometry(self, tr: CalcTrace) -> None:
        tr.use_param(self.params, "spacing_k1")
        tr.use_param(self.params, "spacing_k2")
        tr.use_param(self.params, "spacing_abs_min")
        for L in self.layers:
            smin = min_clear_spacing(L.diameter, self.dg, self.params)
            tr.step(f"Separación libre mínima (φ{fmt(L.diameter)})", "Anejo 19, 8.2(2)",
                    "s_min = max(k1·φ; d_g + k2; 20 mm)",
                    f"s_min = max({fmt(self.params['spacing_k1'])}·{fmt(L.diameter)}; "
                    f"{fmt(self.dg)} + {fmt(self.params['spacing_k2'])}; {fmt(self.params['spacing_abs_min'])})",
                    smin, "mm", "s_min")
        for msg in self.issues:
            tr.warn(msg)
