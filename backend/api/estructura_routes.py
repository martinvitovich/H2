"""Rutas del proyecto estructural integral (``/api/estructuras``)."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from estructura import model as M
from estructura.repository import Repository
from estructura.servicio import StructuralService
from services.projects import ProjectStore, migrate, validate_documents

from . import routes

router = APIRouter(prefix="/api/estructuras")


def get_store() -> ProjectStore:
    return routes.get_store()


def repo_dep(store: ProjectStore = Depends(get_store)) -> Repository:
    return store.repo


def svc_dep(store: ProjectStore = Depends(get_store)) -> StructuralService:
    return store.service


class ProjectInfo(BaseModel):
    name: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=4000)
    location: str | None = Field(None, max_length=200)
    client: str | None = Field(None, max_length=200)
    project_date: str | None = Field(None, max_length=40)
    structural_system: str | None = Field(None, max_length=400)


class ProjectCreate(ProjectInfo):
    name: str = Field(..., min_length=1, max_length=200)
    settings: dict[str, Any] = Field(default_factory=dict)
    parameter_overrides: dict[str, Any] = Field(default_factory=dict)
    levels: list[dict[str, Any]] = Field(default_factory=list, description="Niveles iniciales {code, name, elevation_m, height_m}")


class ProjectPatch(ProjectInfo):
    settings: dict[str, Any] | None = None
    parameter_overrides: dict[str, Any] | None = None


class LevelIn(BaseModel):
    code: str | None = None
    name: str | None = None
    elevation_m: float | None = None
    height_m: float | None = None
    sort_order: int | None = None


class ElementIn(BaseModel):
    type: Literal["losa", "viga", "pilar", "zapata"]
    code: str | None = None
    level_id: str | None = None
    description: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


class ElementPatch(BaseModel):
    code: str | None = None
    level_id: str | None = "__keep__"
    description: str | None = None
    data: dict[str, Any] | None = None


class LinkIn(BaseModel):
    kind: Literal["losa_viga", "viga_apoyo", "pilar_pilar", "pilar_zapata"]
    source_id: str
    target_id: str
    data: dict[str, Any] = Field(default_factory=dict)


class CalcIn(BaseModel):
    element_ids: list[str] | None = None
    calc_types: list[str] | None = None
    only_stale: bool = True


def _project_summary(svc: StructuralService, p: dict) -> dict:
    ov = svc.overview(p["id"])
    return {**p, "summary": ov["summary"]}


@router.get("/esquema")
def schema() -> dict:
    return M.schema()


@router.get("")
def list_projects(svc: StructuralService = Depends(svc_dep)) -> list[dict]:
    return [_project_summary(svc, p) for p in svc.repo.list_projects()]


@router.post("", status_code=201)
def create_project(body: ProjectCreate, svc: StructuralService = Depends(svc_dep)) -> dict:
    info = body.model_dump(include={"name", "description", "location", "client", "project_date", "structural_system"})
    pid = svc.repo.create_project({k: v or "" for k, v in info.items()}, body.settings, body.parameter_overrides)
    try:
        for i, lv in enumerate(body.levels):
            svc.repo.create_level(pid, lv.get("code", ""), {**lv, "sort_order": lv.get("sort_order", i)})
    except ValueError:
        svc.repo.delete_project(pid)
        raise
    return svc.overview(pid)


@router.post("/importar", status_code=201)
def import_project(body: dict[str, Any], svc: StructuralService = Depends(svc_dep)) -> dict:
    pid = svc.repo.import_project(migrate(body), docs_validator=validate_documents)
    return svc.overview(pid)


@router.get("/{pid}")
def get_project(pid: str, svc: StructuralService = Depends(svc_dep)) -> dict:
    return svc.overview(pid)


@router.patch("/{pid}")
def patch_project(pid: str, body: ProjectPatch, svc: StructuralService = Depends(svc_dep)) -> dict:
    info = {k: v for k, v in body.model_dump(include={"name", "description", "location", "client", "project_date",
                                                      "structural_system"}).items() if v is not None}
    svc.repo.update_project(pid, info, body.settings, body.parameter_overrides)
    ov = svc.overview(pid)
    if body.settings is not None or body.parameter_overrides is not None:
        ov["affected"] = svc.affected_report(pid, None)
    return ov


@router.post("/{pid}/archivar")
def archive(pid: str, archived: bool = Body(True, embed=True), repo: Repository = Depends(repo_dep)) -> dict:
    return repo.set_archived(pid, archived)


@router.post("/{pid}/duplicar", status_code=201)
def duplicate(pid: str, name: str | None = Body(None, embed=True), svc: StructuralService = Depends(svc_dep)) -> dict:
    return svc.overview(svc.repo.duplicate_project(pid, name))


@router.delete("/{pid}", status_code=204)
def delete(pid: str, repo: Repository = Depends(repo_dep)) -> Response:
    repo.delete_project(pid)
    return Response(status_code=204)


@router.get("/{pid}/exportar")
def export(pid: str, repo: Repository = Depends(repo_dep)) -> dict:
    return repo.export_project(pid)


@router.get("/{pid}/historial")
def history(pid: str, element_id: str | None = None, limit: int = Query(300, ge=1, le=2000),
            repo: Repository = Depends(repo_dep)) -> list[dict]:
    repo.get_project(pid)
    return repo.history(pid, element_id, limit)


# --- niveles
@router.post("/{pid}/niveles", status_code=201)
def create_level(pid: str, body: LevelIn, repo: Repository = Depends(repo_dep)) -> dict:
    lid = repo.create_level(pid, body.code or "", body.model_dump(exclude_none=True))
    return next(l for l in repo.list_levels(pid) if l["id"] == lid)


@router.patch("/{pid}/niveles/{lid}")
def patch_level(pid: str, lid: str, body: LevelIn, svc: StructuralService = Depends(svc_dep)) -> dict:
    svc.repo.update_level(pid, lid, body.model_dump(exclude_unset=True))
    return {"levels": svc.repo.list_levels(pid), "affected": svc.affected_report(pid, None)}


@router.delete("/{pid}/niveles/{lid}", status_code=204)
def delete_level(pid: str, lid: str, repo: Repository = Depends(repo_dep)) -> Response:
    repo.delete_level(pid, lid)
    return Response(status_code=204)


# --- elementos
@router.post("/{pid}/elementos", status_code=201)
def create_element(pid: str, body: ElementIn, svc: StructuralService = Depends(svc_dep)) -> dict:
    eid = svc.repo.create_element(pid, body.type, body.code, body.level_id, body.description, body.data)
    return svc.element_detail(pid, eid)


@router.post("/{pid}/elementos/lote", status_code=201)
def create_elements(pid: str, rows: list[ElementIn], svc: StructuralService = Depends(svc_dep)) -> dict:
    """Alta en bloque (todas o ninguna)."""
    created: list[str] = []
    try:
        for r in rows:
            created.append(svc.repo.create_element(pid, r.type, r.code, r.level_id, r.description, r.data))
    except ValueError:
        for eid in created:
            svc.repo.delete_element(pid, eid)
        raise
    return {"created": created}


@router.get("/{pid}/elementos/{eid}")
def get_element(pid: str, eid: str, svc: StructuralService = Depends(svc_dep)) -> dict:
    return svc.element_detail(pid, eid)


@router.patch("/{pid}/elementos/{eid}")
def patch_element(pid: str, eid: str, body: ElementPatch, svc: StructuralService = Depends(svc_dep)) -> dict:
    lid = ... if body.level_id == "__keep__" else body.level_id
    svc.repo.update_element(pid, eid, body.code, lid, body.description, body.data)
    return {"element": svc.element_detail(pid, eid), "affected": svc.affected_report(pid, eid)}


@router.delete("/{pid}/elementos/{eid}")
def delete_element(pid: str, eid: str, svc: StructuralService = Depends(svc_dep)) -> dict:
    an = svc.analysis(pid)
    downstream = [an.code(x) for x in an.affected_by(eid) if x != eid] if eid in an.el else []
    linked = svc.repo.delete_element(pid, eid)
    return {"deleted": eid, "links_removed_with": linked, "affected": downstream}


@router.post("/{pid}/elementos/{eid}/duplicar", status_code=201)
def duplicate_element(pid: str, eid: str, code: str | None = Body(None, embed=True),
                      svc: StructuralService = Depends(svc_dep)) -> dict:
    return svc.element_detail(pid, svc.repo.duplicate_element(pid, eid, code))


@router.post("/{pid}/elementos/{eid}/adoptar-propuesta")
def adopt(pid: str, eid: str, svc: StructuralService = Depends(svc_dep)) -> dict:
    res = svc.adopt_proposal(pid, eid)
    return {**res, "element": svc.element_detail(pid, eid), "affected": svc.affected_report(pid, eid)}


# --- relaciones
@router.post("/{pid}/relaciones", status_code=201)
def create_link(pid: str, body: LinkIn, svc: StructuralService = Depends(svc_dep)) -> dict:
    lid = svc.repo.create_link(pid, body.kind, body.source_id, body.target_id, body.data)
    return {"id": lid, "affected": svc.affected_report(pid, body.target_id)}


@router.patch("/{pid}/relaciones/{lid}")
def patch_link(pid: str, lid: str, data: dict[str, Any] = Body(..., embed=True),
               svc: StructuralService = Depends(svc_dep)) -> dict:
    svc.repo.update_link(pid, lid, data)
    l = next(x for x in svc.repo.list_links(pid) if x["id"] == lid)
    return {"link": l, "affected": svc.affected_report(pid, l["target_id"])}


@router.delete("/{pid}/relaciones/{lid}")
def delete_link(pid: str, lid: str, svc: StructuralService = Depends(svc_dep)) -> dict:
    l = next((x for x in svc.repo.list_links(pid) if x["id"] == lid), None)
    svc.repo.delete_link(pid, lid)
    return {"affected": svc.affected_report(pid, l["target_id"]) if l else []}


# --- cálculo
@router.post("/{pid}/calcular")
def calculate(pid: str, body: CalcIn, svc: StructuralService = Depends(svc_dep)) -> dict:
    return svc.calculate(pid, body.element_ids, body.calc_types, body.only_stale)


# --- planillas e informes
def _file(content: bytes, media: str, name: str) -> Response:
    return Response(content, media_type=media, headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/{pid}/planillas")
def tables(pid: str, svc: StructuralService = Depends(svc_dep)) -> list[dict]:
    from estructura.informes import build_tables
    return build_tables(svc.overview(pid))


@router.get("/{pid}/planilla.xlsx")
def excel(pid: str, svc: StructuralService = Depends(svc_dep)) -> Response:
    from estructura.informes import build_excel
    ov = svc.overview(pid)
    return _file(build_excel(ov), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                 routes._safe_filename(f"planilla_{ov['project']['name']}") + ".xlsx")


@router.get("/{pid}/informe.pdf")
def project_pdf(pid: str, svc: StructuralService = Depends(svc_dep)) -> Response:
    from estructura.informes import build_project_pdf
    ov = svc.overview(pid)
    return _file(build_project_pdf(ov, svc.repo.history(pid, None, 60)), "application/pdf",
                 routes._safe_filename(f"memoria_{ov['project']['name']}") + ".pdf")


@router.get("/{pid}/elementos/{eid}/ficha.pdf")
def element_pdf(pid: str, eid: str, svc: StructuralService = Depends(svc_dep)) -> Response:
    from estructura.informes import build_element_pdf
    det = svc.element_detail(pid, eid)
    ov = svc.overview(pid)
    return _file(build_element_pdf(ov, det, det["history"]), "application/pdf",
                 routes._safe_filename(f"ficha_{det['code']}") + ".pdf")


@router.get("/{pid}/elementos/{eid}/informe.pdf")
def element_calc_pdf(pid: str, eid: str, calc: str, svc: StructuralService = Depends(svc_dep)) -> Response:
    """Informe de cálculo completo (mismo formato que las calculadoras) de un resultado vigente."""
    from fastapi import HTTPException
    from services import report_pdf as R
    det = svc.element_detail(pid, eid)
    c = next((x for x in det["calc_list"] if x["calc_type"] == calc), None)
    if c is None:
        raise HTTPException(404, f"El elemento no tiene el cálculo {calc}")
    if c["status"] != "actual":
        raise HTTPException(409, "El resultado no está vigente (" + c["status"].replace("_", " ") +
                            "): recalcule el elemento antes de emitir el informe")
    out = c["stored"]["output"]["result"]
    req = c["stored"]["input"]["request"]
    pname = svc.repo.get_project(pid)["name"]
    builders = {"viga_flexion": R.build_flexure_report, "viga_flexion_neg": R.build_flexure_report,
                "viga_cortante": R.build_shear_report, "pilar": R.build_column_report,
                "losa_flexion": R.build_slab_report, "losa_flexion_neg": R.build_slab_report,
                "viga_fisuracion": R.build_crack_report, "viga_flecha": R.build_deflection_report}
    if calc not in builders:
        raise HTTPException(422, "Este cálculo no tiene informe detallado propio; use la ficha del elemento")
    return _file(builders[calc](out, req, pname, ""), "application/pdf",
                 routes._safe_filename(f"informe_{det['code']}_{calc}") + ".pdf")
