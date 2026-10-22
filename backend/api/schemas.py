"""Modelos Pydantic de entrada de la API (validación de datos recibidos)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from core.elu.flexion import FlexureInput
from core.parameters import ParameterSet
from core.section import Layer, RectangularShape, ReinforcedSection, TShape


class ShapeIn(BaseModel):
    kind: Literal["rectangular", "T"] = "rectangular"
    b: float | None = Field(None, gt=0, le=10000, description="Ancho (mm), sección rectangular")
    h: float = Field(..., gt=0, le=10000, description="Canto total (mm)")
    bf: float | None = Field(None, gt=0, le=20000, description="Ancho eficaz del ala (mm)")
    hf: float | None = Field(None, gt=0, le=5000, description="Espesor del ala (mm)")
    bw: float | None = Field(None, gt=0, le=10000, description="Ancho del alma (mm)")

    @model_validator(mode="after")
    def _check(self) -> "ShapeIn":
        if self.kind == "rectangular" and self.b is None:
            raise ValueError("La sección rectangular requiere el ancho b")
        if self.kind == "T" and None in (self.bf, self.hf, self.bw):
            raise ValueError("La sección en T requiere b_f, h_f y b_w")
        return self

    def build(self):
        if self.kind == "rectangular":
            return RectangularShape(self.b, self.h)
        return TShape(self.bf, self.hf, self.bw, self.h)


class LayerIn(BaseModel):
    face: Literal["inferior", "superior"]
    n: int = Field(..., ge=1, le=30)
    diameter: float = Field(..., ge=5, le=40)
    depth: float | None = Field(None, gt=0)

    def build(self) -> Layer:
        return Layer(self.face, self.n, self.diameter, self.depth)


class SectionRequest(BaseModel):
    shape: ShapeIn
    cover: float = Field(30, ge=0, le=200)
    stirrup_diameter: float = Field(8, ge=0, le=20)
    dg: float = Field(20, ge=4, le=63)
    layers: list[LayerIn] = Field(default_factory=list)
    parameter_overrides: dict[str, Any] = Field(default_factory=dict)

    def build(self) -> ReinforcedSection:
        return ReinforcedSection(self.shape.build(), self.cover, self.stirrup_diameter,
                                 [l.build() for l in self.layers], self.dg,
                                 ParameterSet(self.parameter_overrides))


class FlexureRequest(BaseModel):
    element_name: str = Field("Viga", max_length=120)
    mode: Literal["design", "check"] = "design"
    shape: ShapeIn
    cover: float = Field(30, gt=0, le=200, description="Recubrimiento nominal hasta el estribo (mm)")
    stirrup_diameter: float = Field(8, ge=0, le=20)
    dg: float = Field(20, ge=4, le=63)
    concrete_class: str = "C25/30"
    steel_grade: str = "B500S"
    steel_branch: Literal["horizontal", "inclinada"] = "horizontal"
    situation: Literal["persistente", "transitoria", "accidental"] = "persistente"
    M_Ed_kNm: float = Field(..., ge=-1e5, le=1e5, description="Momento de cálculo (kN·m), + tracción inferior")
    assumed_bar_diameter: float = Field(16, ge=5, le=40)
    layers: list[LayerIn] = Field(default_factory=list)
    parameter_overrides: dict[str, Any] = Field(default_factory=dict)

    def build(self) -> FlexureInput:
        return FlexureInput(
            shape=self.shape.build(), cover=self.cover, stirrup_diameter=self.stirrup_diameter,
            M_Ed_knm=self.M_Ed_kNm, concrete_class=self.concrete_class, steel_grade=self.steel_grade,
            steel_branch=self.steel_branch, situation=self.situation, dg=self.dg,
            assumed_bar_diameter=self.assumed_bar_diameter, layers=[l.build() for l in self.layers],
            params=ParameterSet(self.parameter_overrides), element_name=self.element_name,
        )


class MaterialRequest(BaseModel):
    concrete_class: str = "C25/30"
    steel_grade: str = "B500S"
    steel_branch: Literal["horizontal", "inclinada"] = "horizontal"
    situation: Literal["persistente", "transitoria", "accidental"] = "persistente"
    parameter_overrides: dict[str, Any] = Field(default_factory=dict)


class ReportRequest(BaseModel):
    project_name: str = Field("Proyecto sin título", max_length=200)
    author: str = Field("", max_length=200)
    request: FlexureRequest


class ProjectIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field("", max_length=4000)
    parameter_overrides: dict[str, Any] = Field(default_factory=dict)
    elements: list[dict[str, Any]] = Field(default_factory=list)
