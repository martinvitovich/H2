"""Modelos Pydantic de entrada de la API (validación de datos recibidos)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from core.elu.cortante import ShearInput
from core.elu.pilares import ColumnInput
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
    face: Literal["inferior", "superior", "lateral"]
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
    secondary_element: bool = Field(False, description="Alternativa A_s,min = 1,2·A_s,nec de 9.2.1.1(1)")
    stirrup_spacing: float | None = Field(None, gt=0, le=1000, description="Separación de estribos (mm), 9.2.1.2(3)")

    def build(self) -> FlexureInput:
        return FlexureInput(
            shape=self.shape.build(), cover=self.cover, stirrup_diameter=self.stirrup_diameter,
            M_Ed_knm=self.M_Ed_kNm, concrete_class=self.concrete_class, steel_grade=self.steel_grade,
            steel_branch=self.steel_branch, situation=self.situation, dg=self.dg,
            assumed_bar_diameter=self.assumed_bar_diameter, layers=[l.build() for l in self.layers],
            params=ParameterSet(self.parameter_overrides), element_name=self.element_name,
            secondary_element=self.secondary_element, stirrup_spacing=self.stirrup_spacing,
        )


class ShearRequest(BaseModel):
    element_name: str = Field("Viga", max_length=120)
    mode: Literal["design", "check"] = "design"
    shape: ShapeIn
    cover: float = Field(30, gt=0, le=200, description="Recubrimiento nominal hasta el cerco (mm)")
    stirrup_diameter: float = Field(8, gt=0, le=20, description="Diámetro de los cercos (mm)")
    stirrup_legs: int = Field(2, ge=2, le=8)
    stirrup_spacing: float | None = Field(None, gt=0, le=1000, description="Separación de cercos (mm), comprobación")
    alpha_deg: float = Field(90, ge=45, le=90, description="Inclinación de los cercos (°)")
    dg: float = Field(20, ge=4, le=63)
    layers: list[LayerIn] = Field(default_factory=list)
    tension_face: Literal["inferior", "superior"] = "inferior"
    V_Ed_kN: float = Field(..., ge=0, le=1e5, description="Cortante de cálculo (kN), valor absoluto")
    N_Ed_kN: float = Field(0, ge=-1e5, le=1e5, description="Axil concomitante (kN), compresión positiva")
    concrete_class: str = "C25/30"
    stirrup_grade: str = "B500S"
    situation: Literal["persistente", "transitoria", "accidental"] = "persistente"
    cot_theta: float | None = Field(None, description="cot θ fijado por el usuario; vacío = automático")
    nu1_simplified: bool = False
    parameter_overrides: dict[str, Any] = Field(default_factory=dict)

    def build(self) -> ShearInput:
        return ShearInput(
            shape=self.shape.build(), cover=self.cover, stirrup_diameter=self.stirrup_diameter,
            layers=[l.build() for l in self.layers], V_Ed_kn=self.V_Ed_kN, tension_face=self.tension_face,
            N_Ed_kn=self.N_Ed_kN, concrete_class=self.concrete_class, stirrup_grade=self.stirrup_grade,
            situation=self.situation, dg=self.dg, stirrup_legs=self.stirrup_legs, alpha_deg=self.alpha_deg,
            stirrup_spacing=self.stirrup_spacing, mode=self.mode, cot_theta=self.cot_theta,
            nu1_simplified=self.nu1_simplified, params=ParameterSet(self.parameter_overrides),
            element_name=self.element_name,
        )


class ShearReportRequest(BaseModel):
    project_name: str = Field("Proyecto sin título", max_length=200)
    author: str = Field("", max_length=200)
    request: ShearRequest


class ColumnRequest(BaseModel):
    element_name: str = Field("P-1", max_length=120)
    b: float = Field(..., gt=0, le=5000, description="Dimensión perpendicular al plano de flexión (mm)")
    h: float = Field(..., gt=0, le=5000, description="Dimensión en el plano de flexión (mm)")
    cover: float = Field(30, gt=0, le=200)
    stirrup_diameter: float = Field(8, gt=0, le=20)
    stirrup_spacing: float | None = Field(None, gt=0, le=1000)
    dg: float = Field(20, ge=4, le=63)
    layers: list[LayerIn] = Field(default_factory=list)
    N_Ed_kN: float = Field(..., gt=0, le=1e6, description="Axil de compresión (kN)")
    M01_kNm: float = Field(0, ge=-1e5, le=1e5)
    M02_kNm: float = Field(0, ge=-1e5, le=1e5)
    length: float = Field(..., gt=0, le=1e5, description="Longitud libre l (mm)")
    braced: bool = True
    l0_mode: Literal["beta", "k"] = "beta"
    beta: float | None = Field(1.0, gt=0, le=10)
    k1: float | None = Field(None, ge=0)
    k2: float | None = Field(None, ge=0)
    transverse_load: bool = False
    M0_span_kNm: float | None = None
    phi_ef: float | None = Field(None, ge=0, le=10)
    phi_inf: float | None = Field(None, ge=0, le=10)
    m0eqp_ratio: float | None = Field(None, ge=0, le=1)
    ei_simplified: bool = False
    intermediate_bars_tied: bool = False
    concrete_class: str = "C25/30"
    steel_grade: str = "B500S"
    steel_branch: Literal["horizontal", "inclinada"] = "horizontal"
    situation: Literal["persistente", "transitoria", "accidental"] = "persistente"
    parameter_overrides: dict[str, Any] = Field(default_factory=dict)

    def build(self) -> ColumnInput:
        return ColumnInput(
            b=self.b, h=self.h, cover=self.cover, stirrup_diameter=self.stirrup_diameter,
            layers=[l.build() for l in self.layers], N_Ed_kn=self.N_Ed_kN, M01_knm=self.M01_kNm,
            M02_knm=self.M02_kNm, length=self.length, braced=self.braced, l0_mode=self.l0_mode, beta=self.beta,
            k1=self.k1, k2=self.k2, transverse_load=self.transverse_load, M0_span_knm=self.M0_span_kNm,
            phi_ef=self.phi_ef, phi_inf=self.phi_inf, m0eqp_ratio=self.m0eqp_ratio,
            ei_simplified=self.ei_simplified, stirrup_spacing=self.stirrup_spacing,
            intermediate_bars_tied=self.intermediate_bars_tied, concrete_class=self.concrete_class,
            steel_grade=self.steel_grade, steel_branch=self.steel_branch, situation=self.situation, dg=self.dg,
            params=ParameterSet(self.parameter_overrides), element_name=self.element_name,
        )


class ColumnReportRequest(BaseModel):
    project_name: str = Field("Proyecto sin título", max_length=200)
    author: str = Field("", max_length=200)
    request: ColumnRequest


class MaterialRequest(BaseModel):
    concrete_class: str = "C25/30"
    aggregate: Literal["cuarcitico", "calizo", "arenisca", "basaltico"] = "cuarcitico"
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
