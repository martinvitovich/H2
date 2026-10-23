"""Servicio del proyecto integral: vistas agregadas (resumen, ficha de elemento), cálculo selectivo
con control de cambios y adopción explícita de propuestas de armado."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from version import __version__

from . import calculos
from .analisis import CALC_LABEL, CALCS_BY_TYPE, ProjectAnalysis, element_status, input_hash
from .model import TYPE_LABEL, ModelError
from .repository import Repository

STATUS_LABEL = {"actual": "Actualizado", "desactualizado": "Desactualizado", "sin_calcular": "Sin calcular",
                "faltan_datos": "Faltan datos", "error": "Error de cálculo", "error_datos": "Error en los datos",
                "no_aplica": "No aplica"}


class StructuralService:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    def analysis(self, pid: str, with_results: bool = True) -> ProjectAnalysis:
        return ProjectAnalysis(self.repo.get_project(pid), self.repo.list_levels(pid), self.repo.list_elements(pid),
                               self.repo.list_links(pid), self.repo.list_results(pid) if with_results else None)

    # ------------------------------------------------------------------ vistas
    def _element_row(self, an: ProjectAnalysis, eid: str) -> dict:
        e = an.el[eid]
        calcs = an.calc_status(eid)
        st = element_status(calcs)
        ld = an.loads(eid)
        ldd = ld.to_dict()
        res = an.results.get(eid, {})
        lv = an.levels.get(e["level_id"] or "")
        missing = sorted({m for c in calcs.values() for m in c.get("missing", [])})
        return {**{k: e[k] for k in ("id", "type", "code", "level_id", "description", "data", "modified")},
                "level_code": lv["code"] if lv else None, **st,
                "calcs": {ct: {"status": c["status"], "ok": c.get("ok"),
                               "texto": ((res.get(ct) or {}).get("output") or {}).get("summary", {}).get("texto")
                               if c["status"] in ("actual", "desactualizado") and res.get(ct) else None,
                               "summary": ((res.get(ct) or {}).get("output") or {}).get("summary")
                               if c["status"] == "actual" else None}
                          for ct, c in calcs.items()},
                "loads": {k: ldd[k] for k in ("g", "q", "efforts", "reactions", "N_G", "N_Q")},
                "missing": missing, "errors": ld.errors, "warnings": ld.warnings,
                "upstream": [an.code(x) for x in an.upstream(eid)], "downstream": [an.code(x) for x in an.downstream(eid)]}

    def overview(self, pid: str) -> dict:
        an = self.analysis(pid)
        rows = [self._element_row(an, eid) for eid in sorted(an.el, key=lambda x: (an.el[x]["type"], an.el[x]["code"]))]
        counts: dict[str, int] = {}
        comp: dict[str, int] = {}
        calc_counts: dict[str, int] = {}
        for r in rows:
            counts[r["status"]] = counts.get(r["status"], 0) + 1
            if r["compliance"]:
                comp[r["compliance"]] = comp.get(r["compliance"], 0) + 1
            for c in r["calcs"].values():
                calc_counts[c["status"]] = calc_counts.get(c["status"], 0) + 1
        return {"project": an.p, "levels": list(an.levels.values()), "elements": rows, "links": an.links,
                "summary": {"by_status": counts, "by_compliance": comp, "calcs": calc_counts,
                            "n_elements": len(rows), "verification": self._verification_text(rows)},
                "engine_version": __version__}

    @staticmethod
    def _verification_text(rows: list[dict]) -> dict:
        n = len(rows)
        pending = [r["code"] for r in rows if r["status"] not in ("actual", "no_aplica")]
        failing = [r["code"] for r in rows if r["compliance"] == "no_cumple"]
        noeval = [r["code"] for r in rows if r["compliance"] == "no_evaluable"]
        if n == 0:
            text, level = "El proyecto no tiene elementos.", "pendiente"
        elif pending:
            text, level = (f"{len(pending)} de {n} elementos con cálculos pendientes, desactualizados, con datos "
                           "incompletos o con errores. El proyecto no está completamente comprobado."), "pendiente"
        elif failing:
            text, level = f"{len(failing)} elementos no cumplen alguna comprobación.", "no_cumple"
        elif noeval:
            text, level = (f"Todos los cálculos están actualizados; {len(noeval)} elementos tienen comprobaciones "
                           "no evaluables con los datos disponibles."), "no_evaluable"
        else:
            text, level = ("Todos los cálculos disponibles están actualizados y cumplen. Quedan fuera del alcance "
                           "del programa las comprobaciones no implementadas (p. ej., dimensionado estructural de "
                           "zapatas, punzonamiento, losas bidireccionales)."), "cumple_alcance"
        return {"level": level, "text": text, "pending": pending, "failing": failing, "not_evaluable": noeval,
                "disclaimer": "Software con validación normativa pendiente: los resultados deben ser revisados por "
                              "un ingeniero estructural responsable."}

    def element_detail(self, pid: str, eid: str) -> dict:
        an = self.analysis(pid)
        if eid not in an.el:
            self.repo.get_element(pid, eid)  # lanza NotFound
        row = self._element_row(an, eid)
        calcs = an.calc_status(eid)
        inputs = an.calc_inputs(eid)
        res = an.results.get(eid, {})
        calc_list = []
        for ct, c in calcs.items():
            r = res.get(ct)
            calc_list.append({**c, "request": inputs[ct].get("request"),
                              "stored": None if r is None else {
                                  "status": r["status"], "computed_at": r["computed_at"],
                                  "engine_version": r["engine_version"], "error": r["error"],
                                  "input": r["input"], "output": r["output"]}})
        rel = []
        for l in an.inc.get(eid, []):
            rel.append({**l, "direction": "entrada", "other_id": l["source_id"], "other_code": an.code(l["source_id"]),
                        "other_type": an.el[l["source_id"]]["type"]})
        for l in an.out.get(eid, []):
            rel.append({**l, "direction": "salida", "other_id": l["target_id"], "other_code": an.code(l["target_id"]),
                        "other_type": an.el[l["target_id"]]["type"]})
        affected = [an.code(x) for x in an.affected_by(eid) if x != eid]
        return {**row, "loads_detail": an.loads(eid).to_dict(), "calc_list": calc_list, "relations": rel,
                "affects": affected, "history": self.repo.history(pid, eid, 100)}

    def affected_report(self, pid: str, eid: str | None) -> list[dict]:
        """Elementos afectados por un cambio y su estado actual (tras guardar)."""
        an = self.analysis(pid)
        ids = an.affected_by(eid) if eid else list(an.el)
        out = []
        for x in ids:
            st = element_status(an.calc_status(x))
            out.append({"id": x, "code": an.code(x), "type": an.el[x]["type"], "status": st["status"]})
        return out

    # ------------------------------------------------------------------ cálculo
    def calculate(self, pid: str, element_ids: list[str] | None = None, calc_types: list[str] | None = None,
                  only_stale: bool = True) -> dict:
        an = self.analysis(pid)
        if element_ids:
            for x in element_ids:
                if x not in an.el:
                    self.repo.get_element(pid, x)
        order = [e for e in an.topological() if not element_ids or e in element_ids]
        report = []
        for eid in order:
            code = an.code(eid)
            calcs = an.calc_status(eid)
            inputs = an.calc_inputs(eid)
            for ct, st in calcs.items():
                if calc_types and ct not in calc_types:
                    continue
                if "request" not in inputs[ct]:
                    if st["status"] in ("faltan_datos", "error_datos"):
                        report.append({"element_id": eid, "code": code, "calc_type": ct, "result": st["status"],
                                       "detail": "; ".join(st.get("missing", [])) or st.get("reason")})
                    continue
                if only_stale and st["status"] == "actual":
                    continue
                req = inputs[ct]["request"]
                h = input_hash(ct, req)
                prov = {"request": req, "procedencia": an.loads(eid).to_dict(), "configuracion": an.s}
                try:
                    out = calculos.run(ct, req)
                    full = {"ok": out.get("ok"), "summary": calculos.summary(ct, req, out), "result": out}
                    self.repo.save_result(pid, eid, ct, "ok", h, prov, full, None, code)
                    report.append({"element_id": eid, "code": code, "calc_type": ct, "result": "calculado",
                                   "ok": out.get("ok")})
                except (ValueError, ValidationError) as exc:  # errores de dominio del motor o de validación
                    msg = str(exc) if not isinstance(exc, ValidationError) else "; ".join(
                        f"{'.'.join(str(x) for x in e['loc'])}: {e['msg']}" for e in exc.errors())
                    self.repo.save_result(pid, eid, ct, "error", h, prov, None, msg, code)
                    report.append({"element_id": eid, "code": code, "calc_type": ct, "result": "error", "detail": msg})
        return {"report": report, "n_calculated": sum(1 for r in report if r["result"] == "calculado"),
                "n_errors": sum(1 for r in report if r["result"] == "error"),
                "n_missing": sum(1 for r in report if r["result"] in ("faltan_datos", "error_datos"))}

    def adopt_proposal(self, pid: str, eid: str) -> dict:
        """Copia en los datos del elemento la armadura propuesta por un dimensionado actualizado."""
        an = self.analysis(pid)
        if eid not in an.el:
            self.repo.get_element(pid, eid)
        e = an.el[eid]
        calcs = an.calc_status(eid)
        res = an.results.get(eid, {})

        def full(ct: str) -> dict | None:
            if calcs.get(ct, {}).get("status") != "actual":
                return None
            return ((res.get(ct) or {}).get("output") or {}).get("result")

        upd: dict[str, Any] = {}
        if e["type"] == "viga":
            layers = []
            for ct in ("viga_flexion", "viga_flexion_neg"):
                r = full(ct)
                if r and r.get("mode") == "design" and r.get("proposal"):
                    layers += [{"face": l["face"], "n": l["n"], "diameter": l["diameter"]}
                               for l in r["proposal"]["layers"]]
            if layers and not e["data"].get("layers"):
                upd["layers"] = layers
            r = full("viga_cortante")
            if r and r.get("mode") == "design" and (r.get("result") or {}).get("proposal"):
                p = r["result"]["proposal"]
                upd.update({"stirrup_phi": p["diameter"], "stirrup_legs": p["legs"], "stirrup_s": p["spacing"]})
        elif e["type"] == "losa":
            for ct, pk, sk in (("losa_flexion", "phi", "s"), ("losa_flexion_neg", "phi_sup", "s_sup")):
                r = full(ct)
                if r and (r.get("result") or {}).get("proposal") and not e["data"].get(sk):
                    p = r["result"]["proposal"]
                    upd.update({pk: p["diameter"], sk: p["spacing"]})
        if not upd:
            raise ModelError("No hay propuestas de armado actualizadas para adoptar en este elemento (calcule primero "
                             "el dimensionado; solo se adoptan propuestas de resultados vigentes y no se sustituye "
                             "armadura ya definida)")
        self.repo.update_element(pid, eid, data=upd)
        return {"adopted": upd}
