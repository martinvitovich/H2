"""Rutas de la API REST. Solo validan, delegan en el motor/servicios y serializan."""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from core.elu.cortante import shear_beam
from core.elu.losas import slab_check
from core.elu.pilares import column_check
from core.els.fisuracion import WMAX_RC, crack_check
from core.els.flechas import K_SYSTEM, deflection_check
from core.elu.flexion import check_flexure, design_flexure
from core.materials import CONCRETE_FCK_CLASSES, STEEL_GRADES, Concrete, ReinforcingSteel, stress_strain_curves
from core.parameters import ParameterSet, norm_info
from core.status import MODULES
from services.projects import ProjectStore
from services.report_pdf import (build_column_report, build_crack_report, build_deflection_report,
                                 build_flexure_report, build_shear_report, build_slab_report)
from version import SOFTWARE_NAME, __version__

from .schemas import (ColumnReportRequest, ColumnRequest, CrackRequest, DeflectionRequest, ElsReportRequest,
                      FlexureRequest, SlabRequest, MaterialRequest, ProjectIn, ReportRequest, SectionRequest, ShearReportRequest,
                      ShearRequest)

router = APIRouter(prefix="/api")
_store: ProjectStore | None = None


def get_store() -> ProjectStore:
    global _store
    if _store is None:
        _store = ProjectStore()
    return _store


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "software": SOFTWARE_NAME, "version": __version__}


@router.get("/info")
def info() -> dict:
    return {"software": SOFTWARE_NAME, "version": __version__, "norm": norm_info(), "modules": MODULES}


@router.get("/norma/parametros")
def parameters_default() -> dict:
    return {"norm": norm_info(), "parameters": ParameterSet().to_list()}


@router.post("/norma/parametros")
def parameters_validate(overrides: dict[str, Any]) -> dict:
    p = ParameterSet(overrides)
    return {"norm": norm_info(), "parameters": p.to_list(), "overrides": p.overrides()}


@router.get("/materiales/catalogo")
def catalog() -> dict:
    return {"concrete_classes": list(CONCRETE_FCK_CLASSES), "steel_grades": list(STEEL_GRADES)}


@router.post("/materiales")
def materials(req: MaterialRequest) -> dict:
    p = ParameterSet(req.parameter_overrides)
    c = Concrete.from_class(req.concrete_class, p, req.situation, req.aggregate)
    s = ReinforcingSteel.from_grade(req.steel_grade, p, req.situation, req.steel_branch)
    return {"concrete": c.properties(), "steel": s.properties(), "curves": stress_strain_curves(c, s),
            "references": {
                "concrete": "Anejo 19, tabla A19.3.1; 3.1.3(2); 3.1.6 (3.15)-(3.16); 3.1.7 (3.17)-(3.22); "
                            "3.1.5 (3.14); 3.1.8 (3.23)",
                "steel": "Anejo 19, 3.2.2(3); 3.2.7, figura A19.3.8",
            },
            "notes": ["Las propiedades de ductilidad (ε_uk, k) de cada designación de acero: el Apéndice C "
                      "del Anejo 19 remite a los Artículos 34 y 35 del Código Estructural, no consultados; "
                      "valores pendientes de verificación (solo intervienen con la rama inclinada).",
                      "ε_c2 para f_ck > 50: se usa 2,0 + 0,085·(f_ck − 50)^0,53, coherente con los valores "
                      "tabulados; la expresión impresa en la tabla A19.3.1 (0,85) contiene una errata."]}


@router.post("/secciones/propiedades")
def section_properties(req: SectionRequest) -> dict:
    return req.build().geometric_properties()


@router.post("/vigas/flexion")
def beam_flexure(req: FlexureRequest) -> dict:
    inp = req.build()
    res = design_flexure(inp) if req.mode == "design" else check_flexure(inp)
    res["request"] = req.model_dump()
    return res


def _safe_filename(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", s).strip("_") or "informe"


@router.post("/informes/vigas/flexion")
def beam_flexure_report(req: ReportRequest) -> Response:
    inp = req.request.build()
    res = design_flexure(inp) if req.request.mode == "design" else check_flexure(inp)
    pdf = build_flexure_report(res, req.request.model_dump(), req.project_name, req.author)
    fn = _safe_filename(f"informe_{req.request.element_name}") + ".pdf"
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{fn}"'})


@router.post("/vigas/cortante")
def beam_shear(req: ShearRequest) -> dict:
    res = shear_beam(req.build())
    res["request"] = req.model_dump()
    return res


@router.post("/informes/vigas/cortante")
def beam_shear_report(req: ShearReportRequest) -> Response:
    res = shear_beam(req.request.build())
    pdf = build_shear_report(res, req.request.model_dump(), req.project_name, req.author)
    fn = _safe_filename(f"informe_cortante_{req.request.element_name}") + ".pdf"
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{fn}"'})


@router.post("/pilares")
def column(req: ColumnRequest) -> dict:
    res = column_check(req.build())
    res["request"] = req.model_dump()
    return res


@router.post("/informes/pilares")
def column_report(req: ColumnReportRequest) -> Response:
    res = column_check(req.request.build())
    pdf = build_column_report(res, req.request.model_dump(), req.project_name, req.author)
    fn = _safe_filename(f"informe_pilar_{req.request.element_name}") + ".pdf"
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{fn}"'})


@router.post("/losas")
def slab(req: SlabRequest) -> dict:
    res = slab_check(req.build())
    res["request"] = req.model_dump()
    return res


@router.post("/informes/losas")
def slab_report(body: ElsReportRequest) -> Response:
    req = SlabRequest.model_validate(body.request)
    res = slab_check(req.build())
    pdf = build_slab_report(res, req.model_dump(), body.project_name, body.author)
    fn = _safe_filename(f"informe_losa_{req.element_name}") + ".pdf"
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{fn}"'})


@router.get("/els/catalogo")
def els_catalog() -> dict:
    return {"exposure_wmax": WMAX_RC, "systems": {k: {"K": v[0], "description": v[1]} for k, v in K_SYSTEM.items()},
            "reference_wmax": "Código Estructural, tabla 27.2 (reproducida en Anejo 19, 7.3.1(5))"}


@router.post("/els/fisuracion")
def els_crack(req: CrackRequest) -> dict:
    res = crack_check(req.build())
    res["request"] = req.model_dump()
    return res


@router.post("/els/deformaciones")
def els_deflection(req: DeflectionRequest) -> dict:
    res = deflection_check(req.build())
    res["request"] = req.model_dump()
    return res


@router.post("/informes/els/fisuracion")
def els_crack_report(body: ElsReportRequest) -> Response:
    req = CrackRequest.model_validate(body.request)
    res = crack_check(req.build())
    pdf = build_crack_report(res, req.model_dump(), body.project_name, body.author)
    fn = _safe_filename(f"informe_fisuracion_{req.element_name}") + ".pdf"
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{fn}"'})


@router.post("/informes/els/deformaciones")
def els_deflection_report(body: ElsReportRequest) -> Response:
    req = DeflectionRequest.model_validate(body.request)
    res = deflection_check(req.build())
    pdf = build_deflection_report(res, req.model_dump(), body.project_name, body.author)
    fn = _safe_filename(f"informe_flechas_{req.element_name}") + ".pdf"
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{fn}"'})


# --- Proyectos ---
@router.get("/proyectos")
def list_projects(store: ProjectStore = Depends(get_store)) -> list[dict]:
    return store.list()


@router.post("/proyectos", status_code=201)
def create_project(body: ProjectIn, store: ProjectStore = Depends(get_store)) -> dict:
    return store.create(body.name, body.description, body.parameter_overrides, body.elements)


@router.post("/proyectos/importar", status_code=201)
def import_project(body: dict[str, Any], store: ProjectStore = Depends(get_store)) -> dict:
    return store.import_json(body)


@router.get("/proyectos/{pid}")
def get_project(pid: str, store: ProjectStore = Depends(get_store)) -> dict:
    return store.get(pid)


@router.put("/proyectos/{pid}")
def update_project(pid: str, body: ProjectIn, store: ProjectStore = Depends(get_store)) -> dict:
    return store.update(pid, body.name, body.description, body.parameter_overrides, body.elements)


@router.delete("/proyectos/{pid}", status_code=204)
def delete_project(pid: str, store: ProjectStore = Depends(get_store)) -> Response:
    store.delete(pid)
    return Response(status_code=204)
