"""Acceso a datos del proyecto integral (SQLite): proyectos, niveles, elementos, relaciones,
resultados, historial de cambios y cálculos independientes.

Reglas de integridad que se aplican aquí además de las claves foráneas de la base de datos:
* los códigos de elemento y de nivel son únicos en cada proyecto (las relaciones usan siempre
  los identificadores internos, nunca los nombres visibles);
* las relaciones solo unen tipos compatibles (``LINK_KINDS``) del mismo proyecto;
* cada extremo de viga tiene como máximo un apoyo; un pilar tiene como máximo un pilar inferior
  y una zapata; una zapata recibe como máximo un pilar.
"""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from core.parameters import ParameterSet, norm_info
from version import __version__

from .db import Database
from .model import (CODE_PREFIX, ELEMENT_TYPES, LINK_KINDS, ModelError, SETTINGS_DEFAULTS, TYPE_LABEL,
                    clean_element_data, clean_link_data, clean_settings)

FORMAT_ID = "ha-anejo19-project"
FORMAT_VERSION = 2
_ID_RE = re.compile(r"^[0-9a-f]{32}$")
_CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-/ ]{0,39}$")
PROJECT_FIELDS = ("name", "description", "location", "client", "project_date", "structural_system")


class NotFound(ModelError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id() -> str:
    return uuid.uuid4().hex


def _check_id(x: str, what: str) -> str:
    if not isinstance(x, str) or not _ID_RE.match(x):
        raise NotFound(f"Identificador de {what} no válido: {x}")
    return x


def _code(code: str, what: str) -> str:
    code = (code or "").strip()
    if not _CODE_RE.match(code):
        raise ModelError(f"Código de {what} no válido: «{code}» (1–40 caracteres: letras, números, . _ - /)")
    return code


def _j(s: str | None) -> Any:
    return json.loads(s) if s else None


class Repository:
    def __init__(self, db: Database) -> None:
        self.db = db

    # ------------------------------------------------------------------ utilidades
    def _q(self, sql: str, args: tuple = ()) -> list[sqlite3.Row]:
        with self.db.lock:
            return self.db.conn.execute(sql, args).fetchall()

    def _touch(self, c: sqlite3.Connection, pid: str) -> None:
        c.execute("UPDATE projects SET modified=?, rev=rev+1, software_version=? WHERE id=?", (now(), __version__, pid))

    def _hist(self, c: sqlite3.Connection, pid: str, action: str, detail: dict | None = None,
              element_id: str | None = None, element_code: str | None = None) -> None:
        detail = detail or {}
        if action == "elemento_modificado" and element_id:
            # Agrupa las ediciones sucesivas (autoguardado) del mismo elemento en menos de 2 minutos
            row = c.execute("SELECT id, ts, action, element_id, detail_json FROM history WHERE project_id=? "
                            "ORDER BY id DESC LIMIT 1", (pid,)).fetchone()
            if row and row["action"] == action and row["element_id"] == element_id:
                try:
                    age = (datetime.now(timezone.utc) - datetime.fromisoformat(row["ts"])).total_seconds()
                except ValueError:
                    age = 1e9
                if age < 120:
                    prev = json.loads(row["detail_json"])
                    ch = prev.get("cambios", {})
                    for k, v in detail.get("cambios", {}).items():
                        ch[k] = {"antes": ch[k]["antes"] if k in ch else v["antes"], "despues": v["despues"]}
                    prev["cambios"] = {k: v for k, v in ch.items() if v["antes"] != v["despues"]}
                    c.execute("UPDATE history SET ts=?, detail_json=? WHERE id=?",
                              (now(), json.dumps(prev, ensure_ascii=False), row["id"]))
                    return
        c.execute("INSERT INTO history(project_id, element_id, element_code, ts, action, detail_json) "
                  "VALUES (?,?,?,?,?,?)", (pid, element_id, element_code, now(), action,
                                           json.dumps(detail, ensure_ascii=False)))

    # ------------------------------------------------------------------ proyectos
    def _project_row(self, pid: str) -> sqlite3.Row:
        _check_id(pid, "proyecto")
        rows = self._q("SELECT * FROM projects WHERE id=?", (pid,))
        if not rows:
            raise NotFound(f"No existe el proyecto {pid}")
        return rows[0]

    @staticmethod
    def _project_dict(r: sqlite3.Row) -> dict:
        settings = dict(SETTINGS_DEFAULTS)
        settings.update(json.loads(r["settings_json"]))
        return {"id": r["id"], "name": r["name"], "description": r["description"], "location": r["location"],
                "client": r["client"], "project_date": r["project_date"],
                "structural_system": r["structural_system"], "status": r["status"],
                "norm": json.loads(r["norm_json"]), "settings": settings,
                "parameter_overrides": json.loads(r["parameter_overrides_json"]),
                "software_version": r["software_version"], "created": r["created"], "modified": r["modified"],
                "rev": r["rev"]}

    def get_project(self, pid: str) -> dict:
        return self._project_dict(self._project_row(pid))

    def list_projects(self) -> list[dict]:
        rows = self._q("SELECT * FROM projects ORDER BY modified DESC")
        counts: dict[str, dict] = {}
        for r in self._q("SELECT project_id, type, COUNT(*) n FROM elements GROUP BY project_id, type"):
            counts.setdefault(r["project_id"], {})[r["type"]] = r["n"]
        docs = {r["project_id"]: r["n"] for r in
                self._q("SELECT project_id, COUNT(*) n FROM calc_documents GROUP BY project_id")}
        out = []
        for r in rows:
            d = self._project_dict(r)
            d["counts"] = {t: counts.get(r["id"], {}).get(t, 0) for t in ELEMENT_TYPES}
            d["n_documents"] = docs.get(r["id"], 0)
            out.append(d)
        return out

    def create_project(self, info: dict, settings: dict | None = None,
                       parameter_overrides: dict | None = None, pid: str | None = None,
                       created: str | None = None, history: str = "proyecto_creado") -> str:
        name = (info.get("name") or "").strip()
        if not name:
            raise ModelError("El proyecto necesita un nombre")
        ParameterSet(parameter_overrides or {})
        st = clean_settings(settings or {})
        pid = pid or new_id()
        t = now()
        with self.db.tx() as c:
            c.execute("INSERT INTO projects(id, name, description, location, client, project_date, structural_system, "
                      "status, norm_json, settings_json, parameter_overrides_json, software_version, created, modified) "
                      "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (pid, name[:200], str(info.get("description") or "")[:4000], str(info.get("location") or "")[:200],
                       str(info.get("client") or "")[:200], str(info.get("project_date") or "")[:40],
                       str(info.get("structural_system") or "")[:400], "activo",
                       json.dumps(norm_info(), ensure_ascii=False), json.dumps(st, ensure_ascii=False),
                       json.dumps(parameter_overrides or {}, ensure_ascii=False), __version__, created or t, t))
            self._hist(c, pid, history, {"nombre": name})
        return pid

    def update_project(self, pid: str, info: dict | None = None, settings: dict | None = None,
                       parameter_overrides: dict | None = None) -> dict:
        cur = self.get_project(pid)
        changes: dict = {}
        sets, args = [], []
        for k, v in (info or {}).items():
            if k not in PROJECT_FIELDS:
                raise ModelError(f"Campo de proyecto no reconocido: {k}")
            v = str(v or "").strip()
            if k == "name" and not v:
                raise ModelError("El proyecto necesita un nombre")
            if v != cur[k]:
                sets.append(f"{k}=?")
                args.append(v)
                changes[k] = {"antes": cur[k], "despues": v}
        if settings is not None:
            new = clean_settings(settings, fill_defaults=False)
            merged = dict(cur["settings"])
            merged.update(new)
            for k, v in new.items():
                if cur["settings"].get(k) != v:
                    changes["config." + k] = {"antes": cur["settings"].get(k), "despues": v}
            sets.append("settings_json=?")
            args.append(json.dumps(merged, ensure_ascii=False))
        if parameter_overrides is not None:
            ParameterSet(parameter_overrides)
            if parameter_overrides != cur["parameter_overrides"]:
                changes["parametros_normativos"] = {"antes": cur["parameter_overrides"], "despues": parameter_overrides}
            sets.append("parameter_overrides_json=?")
            args.append(json.dumps(parameter_overrides, ensure_ascii=False))
        if sets:
            with self.db.tx() as c:
                c.execute(f"UPDATE projects SET {', '.join(sets)} WHERE id=?", (*args, pid))
                if changes:
                    self._touch(c, pid)
                    self._hist(c, pid, "proyecto_modificado", {"cambios": changes})
        return self.get_project(pid)

    def set_archived(self, pid: str, archived: bool) -> dict:
        self._project_row(pid)
        with self.db.tx() as c:
            c.execute("UPDATE projects SET status=? WHERE id=?", ("archivado" if archived else "activo", pid))
            self._touch(c, pid)
            self._hist(c, pid, "proyecto_archivado" if archived else "proyecto_reactivado")
        return self.get_project(pid)

    def delete_project(self, pid: str) -> None:
        self._project_row(pid)
        with self.db.tx() as c:
            c.execute("DELETE FROM projects WHERE id=?", (pid,))

    def duplicate_project(self, pid: str, name: str | None = None) -> str:
        data = self.export_project(pid)
        data["name"] = name or f"{data['name']} (copia)"
        return self.import_project(data, history="proyecto_duplicado")

    # ------------------------------------------------------------------ niveles
    def list_levels(self, pid: str) -> list[dict]:
        return [dict(r) for r in self._q("SELECT id, code, name, elevation_m, height_m, sort_order FROM levels "
                                         "WHERE project_id=? ORDER BY sort_order, elevation_m, code", (pid,))]

    def _level_args(self, d: dict) -> dict:
        out = {}
        for k in ("elevation_m", "height_m"):
            if k in d:
                v = d[k]
                if v in (None, ""):
                    out[k] = None
                else:
                    try:
                        out[k] = float(v)
                    except (TypeError, ValueError):
                        raise ModelError(f"Nivel: valor no válido para {k}: {v!r}")
                    if k == "height_m" and not 0.3 <= out[k] <= 50:
                        raise ModelError("Nivel: la altura de planta debe estar entre 0,3 y 50 m")
        if "name" in d:
            out["name"] = str(d["name"] or "")[:120]
        if "sort_order" in d:
            out["sort_order"] = int(d["sort_order"] or 0)
        return out

    def create_level(self, pid: str, code: str, d: dict | None = None, lid: str | None = None) -> str:
        self._project_row(pid)
        code = _code(code, "nivel")
        args = self._level_args(d or {})
        lid = lid or new_id()
        try:
            with self.db.tx() as c:
                c.execute("INSERT INTO levels(id, project_id, code, name, elevation_m, height_m, sort_order) "
                          "VALUES (?,?,?,?,?,?,?)", (lid, pid, code, args.get("name", ""), args.get("elevation_m"),
                                                    args.get("height_m"), args.get("sort_order", 0)))
                self._touch(c, pid)
                self._hist(c, pid, "nivel_creado", {"codigo": code})
        except sqlite3.IntegrityError:
            raise ModelError(f"Ya existe un nivel con el código «{code}» en este proyecto")
        return lid

    def _level_row(self, pid: str, lid: str) -> sqlite3.Row:
        _check_id(lid, "nivel")
        rows = self._q("SELECT * FROM levels WHERE id=? AND project_id=?", (lid, pid))
        if not rows:
            raise NotFound(f"No existe el nivel {lid} en este proyecto")
        return rows[0]

    def update_level(self, pid: str, lid: str, d: dict) -> None:
        row = self._level_row(pid, lid)
        args = self._level_args(d)
        if "code" in d:
            args["code"] = _code(d["code"], "nivel")
        changes = {k: {"antes": row[k], "despues": v} for k, v in args.items() if row[k] != v}
        if not changes:
            return
        try:
            with self.db.tx() as c:
                c.execute(f"UPDATE levels SET {', '.join(f'{k}=?' for k in args)} WHERE id=?", (*args.values(), lid))
                self._touch(c, pid)
                self._hist(c, pid, "nivel_modificado", {"codigo": row["code"], "cambios": changes})
        except sqlite3.IntegrityError:
            raise ModelError(f"Ya existe un nivel con el código «{d.get('code')}» en este proyecto")

    def delete_level(self, pid: str, lid: str) -> None:
        row = self._level_row(pid, lid)
        used = self._q("SELECT code FROM elements WHERE level_id=? ORDER BY code", (lid,))
        if used:
            raise ModelError(f"El nivel «{row['code']}» tiene elementos asignados "
                             f"({', '.join(r['code'] for r in used[:10])}{'…' if len(used) > 10 else ''}); "
                             "reasígnelos o elimínelos antes de borrar el nivel")
        with self.db.tx() as c:
            c.execute("DELETE FROM levels WHERE id=?", (lid,))
            self._touch(c, pid)
            self._hist(c, pid, "nivel_eliminado", {"codigo": row["code"]})

    # ------------------------------------------------------------------ elementos
    @staticmethod
    def _element_dict(r: sqlite3.Row) -> dict:
        return {"id": r["id"], "type": r["type"], "code": r["code"], "level_id": r["level_id"],
                "description": r["description"], "data": json.loads(r["data_json"]),
                "created": r["created"], "modified": r["modified"]}

    def list_elements(self, pid: str, etype: str | None = None) -> list[dict]:
        if etype:
            rows = self._q("SELECT * FROM elements WHERE project_id=? AND type=? ORDER BY code", (pid, etype))
        else:
            rows = self._q("SELECT * FROM elements WHERE project_id=? ORDER BY type, code", (pid,))
        return [self._element_dict(r) for r in rows]

    def get_element(self, pid: str, eid: str) -> dict:
        _check_id(eid, "elemento")
        rows = self._q("SELECT * FROM elements WHERE id=? AND project_id=?", (eid, pid))
        if not rows:
            raise NotFound(f"No existe el elemento {eid} en este proyecto")
        return self._element_dict(rows[0])

    def next_code(self, pid: str, etype: str) -> str:
        codes = {r["code"] for r in self._q("SELECT code FROM elements WHERE project_id=?", (pid,))}
        p = CODE_PREFIX[etype]
        n = 1
        while f"{p}{n}" in codes:
            n += 1
        return f"{p}{n}"

    def _check_level(self, pid: str, lid: str | None) -> str | None:
        if lid in (None, ""):
            return None
        self._level_row(pid, lid)
        return lid

    def create_element(self, pid: str, etype: str, code: str | None = None, level_id: str | None = None,
                       description: str = "", data: dict | None = None, eid: str | None = None,
                       history: str = "elemento_creado") -> str:
        self._project_row(pid)
        if etype not in ELEMENT_TYPES:
            raise ModelError(f"Tipo de elemento no admitido: {etype}")
        code = _code(code or self.next_code(pid, etype), "elemento")
        clean = clean_element_data(etype, data, f"{TYPE_LABEL[etype]} {code}")
        level_id = self._check_level(pid, level_id)
        eid = eid or new_id()
        t = now()
        try:
            with self.db.tx() as c:
                c.execute("INSERT INTO elements(id, project_id, level_id, type, code, description, data_json, created, "
                          "modified) VALUES (?,?,?,?,?,?,?,?,?)",
                          (eid, pid, level_id, etype, code, str(description or "")[:400],
                           json.dumps(clean, ensure_ascii=False), t, t))
                self._touch(c, pid)
                self._hist(c, pid, history, {"tipo": etype}, eid, code)
        except sqlite3.IntegrityError:
            raise ModelError(f"Ya existe un elemento con el código «{code}» en este proyecto")
        return eid

    def update_element(self, pid: str, eid: str, code: str | None = None, level_id: Any = ...,
                       description: str | None = None, data: dict | None = None) -> dict:
        el = self.get_element(pid, eid)
        sets, args, changes = [], [], {}
        if code is not None:
            code = _code(code, "elemento")
            if code != el["code"]:
                sets.append("code=?"); args.append(code)
                changes["codigo"] = {"antes": el["code"], "despues": code}
        if level_id is not ...:
            level_id = self._check_level(pid, level_id)
            if level_id != el["level_id"]:
                sets.append("level_id=?"); args.append(level_id)
                changes["nivel"] = {"antes": el["level_id"], "despues": level_id}
        if description is not None and description != el["description"]:
            sets.append("description=?"); args.append(str(description)[:400])
            changes["descripcion"] = {"antes": el["description"], "despues": description}
        if data is not None:
            new = clean_element_data(el["type"], data, f"{TYPE_LABEL[el['type']]} {code or el['code']}",
                                     fill_defaults=False)
            merged = dict(el["data"])
            merged.update(new)
            for k, v in new.items():
                if el["data"].get(k) != v:
                    changes[k] = {"antes": el["data"].get(k), "despues": v}
            if merged != el["data"]:
                sets.append("data_json=?"); args.append(json.dumps(merged, ensure_ascii=False))
        if not changes:
            return el
        sets.append("modified=?"); args.append(now())
        try:
            with self.db.tx() as c:
                c.execute(f"UPDATE elements SET {', '.join(sets)} WHERE id=?", (*args, eid))
                self._touch(c, pid)
                self._hist(c, pid, "elemento_modificado", {"cambios": changes}, eid, code or el["code"])
        except sqlite3.IntegrityError:
            raise ModelError(f"Ya existe un elemento con el código «{code}» en este proyecto")
        return self.get_element(pid, eid)

    def delete_element(self, pid: str, eid: str) -> list[str]:
        el = self.get_element(pid, eid)
        linked = [r["code"] for r in self._q(
            "SELECT DISTINCT e.code FROM links l JOIN elements e ON e.id = CASE WHEN l.source_id=? THEN l.target_id "
            "ELSE l.source_id END WHERE l.source_id=? OR l.target_id=?", (eid, eid, eid))]
        with self.db.tx() as c:
            c.execute("DELETE FROM elements WHERE id=?", (eid,))
            self._touch(c, pid)
            self._hist(c, pid, "elemento_eliminado", {"tipo": el["type"], "relaciones_eliminadas_con": linked},
                       eid, el["code"])
        return linked

    def duplicate_element(self, pid: str, eid: str, code: str | None = None) -> str:
        el = self.get_element(pid, eid)
        return self.create_element(pid, el["type"], code or self.next_code(pid, el["type"]), el["level_id"],
                                   el["description"], el["data"], history="elemento_duplicado")

    # ------------------------------------------------------------------ relaciones
    def list_links(self, pid: str) -> list[dict]:
        return [{"id": r["id"], "kind": r["kind"], "source_id": r["source_id"], "target_id": r["target_id"],
                 "data": json.loads(r["data_json"])}
                for r in self._q("SELECT * FROM links WHERE project_id=? ORDER BY created", (pid,))]

    def _validate_link(self, pid: str, kind: str, src: dict, tgt: dict, data: dict, exclude: str | None) -> None:
        if kind not in LINK_KINDS:
            raise ModelError(f"Tipo de relación no admitido: {kind}")
        st, tt, _ = LINK_KINDS[kind]
        if src["type"] not in st or tgt["type"] not in tt:
            raise ModelError(f"Relación {kind} no admitida entre {TYPE_LABEL[src['type']]} {src['code']} y "
                             f"{TYPE_LABEL[tgt['type']]} {tgt['code']}")
        if src["id"] == tgt["id"]:
            raise ModelError("Un elemento no puede relacionarse consigo mismo")
        others = [l for l in self.list_links(pid) if l["id"] != exclude]
        if kind == "losa_viga":
            m = data.get("metodo") or "area"
            if m == "area" and not data.get("area"):
                raise ModelError(f"Reparto {src['code']} → {tgt['code']}: indique el área tributaria (m²)")
            if m == "ancho" and not data.get("ancho"):
                raise ModelError(f"Reparto {src['code']} → {tgt['code']}: indique el ancho tributario (m)")
        if kind == "viga_apoyo":
            end = data.get("extremo") or "fin"
            for l in others:
                if l["kind"] == kind and l["source_id"] == src["id"] and (l["data"].get("extremo") or "fin") == end:
                    raise ModelError(f"El extremo «{end}» de la viga {src['code']} ya tiene un apoyo definido")
            if src["data"].get("sistema") == "voladizo" and end != "inicio":
                raise ModelError(f"La viga {src['code']} es un voladizo empotrado en su inicio: "
                                 "solo admite apoyo en el extremo «inicio»")
            if tgt["type"] == "viga":
                if data.get("posicion") is None:
                    raise ModelError(f"Indique la posición del apoyo de {src['code']} sobre la viga {tgt['code']} "
                                     "(m desde su inicio)")
                L = tgt["data"].get("L")
                if L is not None and not 0 <= data["posicion"] <= L:
                    raise ModelError(f"La posición {data['posicion']} m queda fuera de la viga {tgt['code']} (L = {L} m)")
        if kind == "pilar_pilar":
            for l in others:
                if l["kind"] == kind and l["source_id"] == src["id"]:
                    raise ModelError(f"El pilar {src['code']} ya continúa en otro pilar inferior")
                if l["kind"] == kind and l["target_id"] == tgt["id"]:
                    raise ModelError(f"El pilar {tgt['code']} ya recibe otro pilar superior")
        if kind == "pilar_zapata":
            for l in others:
                if l["kind"] == kind and l["source_id"] == src["id"]:
                    raise ModelError(f"El pilar {src['code']} ya tiene zapata asignada")
                if l["kind"] == kind and l["target_id"] == tgt["id"]:
                    raise ModelError(f"La zapata {tgt['code']} ya recibe otro pilar (solo zapatas aisladas)")
            if any(l["kind"] == "pilar_pilar" and l["source_id"] == src["id"] for l in others):
                raise ModelError(f"El pilar {src['code']} continúa en un pilar inferior; asigne la zapata al pilar "
                                 "del nivel más bajo")
        if kind == "pilar_pilar" and any(l["kind"] == "pilar_zapata" and l["source_id"] == src["id"] for l in others):
            raise ModelError(f"El pilar {src['code']} ya apoya en una zapata")
        # Ciclos en la cadena de transmisión de cargas
        graph: dict[str, set[str]] = {}
        for l in others:
            graph.setdefault(l["source_id"], set()).add(l["target_id"])
        stack, seen = [tgt["id"]], set()
        while stack:
            n = stack.pop()
            if n == src["id"]:
                raise ModelError(f"La relación {src['code']} → {tgt['code']} crearía un ciclo en la transmisión de "
                                 "cargas")
            if n in seen:
                continue
            seen.add(n)
            stack.extend(graph.get(n, ()))

    def create_link(self, pid: str, kind: str, source_id: str, target_id: str, data: dict | None = None,
                    lid: str | None = None) -> str:
        src = self.get_element(pid, source_id)
        tgt = self.get_element(pid, target_id)
        clean = clean_link_data(kind, data)
        self._validate_link(pid, kind, src, tgt, clean, None)
        lid = lid or new_id()
        try:
            with self.db.tx() as c:
                c.execute("INSERT INTO links(id, project_id, source_id, target_id, kind, data_json, created) "
                          "VALUES (?,?,?,?,?,?,?)", (lid, pid, source_id, target_id, kind,
                                                    json.dumps(clean, ensure_ascii=False), now()))
                self._touch(c, pid)
                self._hist(c, pid, "relacion_creada", {"tipo": kind, "origen": src["code"], "destino": tgt["code"],
                                                       "datos": clean}, source_id, src["code"])
        except sqlite3.IntegrityError:
            raise ModelError(f"La relación {src['code']} → {tgt['code']} ya existe")
        return lid

    def _link_row(self, pid: str, lid: str) -> dict:
        _check_id(lid, "relación")
        for l in self.list_links(pid):
            if l["id"] == lid:
                return l
        raise NotFound(f"No existe la relación {lid} en este proyecto")

    def update_link(self, pid: str, lid: str, data: dict) -> None:
        l = self._link_row(pid, lid)
        src = self.get_element(pid, l["source_id"])
        tgt = self.get_element(pid, l["target_id"])
        merged = dict(l["data"]); merged.update(data or {})
        clean = clean_link_data(l["kind"], merged)
        self._validate_link(pid, l["kind"], src, tgt, clean, lid)
        if clean == l["data"]:
            return
        with self.db.tx() as c:
            c.execute("UPDATE links SET data_json=? WHERE id=?", (json.dumps(clean, ensure_ascii=False), lid))
            self._touch(c, pid)
            self._hist(c, pid, "relacion_modificada", {"tipo": l["kind"], "origen": src["code"], "destino": tgt["code"],
                                                       "antes": l["data"], "despues": clean}, src["id"], src["code"])

    def delete_link(self, pid: str, lid: str) -> None:
        l = self._link_row(pid, lid)
        src = self.get_element(pid, l["source_id"])
        tgt = self.get_element(pid, l["target_id"])
        with self.db.tx() as c:
            c.execute("DELETE FROM links WHERE id=?", (lid,))
            self._touch(c, pid)
            self._hist(c, pid, "relacion_eliminada", {"tipo": l["kind"], "origen": src["code"], "destino": tgt["code"]},
                       src["id"], src["code"])

    # ------------------------------------------------------------------ resultados
    def list_results(self, pid: str) -> dict[str, dict[str, dict]]:
        rows = self._q("SELECT r.* FROM results r JOIN elements e ON e.id=r.element_id WHERE e.project_id=?", (pid,))
        out: dict[str, dict[str, dict]] = {}
        for r in rows:
            out.setdefault(r["element_id"], {})[r["calc_type"]] = {
                "calc_type": r["calc_type"], "status": r["status"], "computed_at": r["computed_at"],
                "engine_version": r["engine_version"], "input_hash": r["input_hash"],
                "input": _j(r["input_json"]), "output": _j(r["output_json"]), "error": r["error"]}
        return out

    def save_result(self, pid: str, element_id: str, calc_type: str, status: str, input_hash: str,
                    input_data: dict, output: dict | None, error: str | None, code: str) -> None:
        t = now()
        with self.db.tx() as c:
            c.execute("INSERT INTO results(id, element_id, calc_type, status, computed_at, engine_version, input_hash, "
                      "input_json, output_json, error) VALUES (?,?,?,?,?,?,?,?,?,?) "
                      "ON CONFLICT(element_id, calc_type) DO UPDATE SET status=excluded.status, "
                      "computed_at=excluded.computed_at, engine_version=excluded.engine_version, "
                      "input_hash=excluded.input_hash, input_json=excluded.input_json, "
                      "output_json=excluded.output_json, error=excluded.error",
                      (new_id(), element_id, calc_type, status, t, __version__, input_hash,
                       json.dumps(input_data, ensure_ascii=False), json.dumps(output, ensure_ascii=False)
                       if output is not None else None, error))
            self._hist(c, pid, "calculo", {"calculo": calc_type, "estado": status, "hash": input_hash[:12],
                                          **({"error": error} if error else {})}, element_id, code)

    def delete_result(self, element_id: str, calc_type: str) -> None:
        with self.db.tx() as c:
            c.execute("DELETE FROM results WHERE element_id=? AND calc_type=?", (element_id, calc_type))

    # ------------------------------------------------------------------ historial
    def history(self, pid: str, element_id: str | None = None, limit: int = 200) -> list[dict]:
        if element_id:
            rows = self._q("SELECT * FROM history WHERE project_id=? AND element_id=? ORDER BY id DESC LIMIT ?",
                           (pid, element_id, limit))
        else:
            rows = self._q("SELECT * FROM history WHERE project_id=? ORDER BY id DESC LIMIT ?", (pid, limit))
        return [{"ts": r["ts"], "action": r["action"], "element_id": r["element_id"],
                 "element_code": r["element_code"], "detail": json.loads(r["detail_json"])} for r in rows]

    # ------------------------------------------------------------------ cálculos independientes (formato 1)
    def list_documents(self, pid: str) -> list[dict]:
        return [{"id": r["id"], "type": r["type"], "name": r["name"], "input": _j(r["input_json"]),
                 "result": _j(r["result_json"])}
                for r in self._q("SELECT * FROM calc_documents WHERE project_id=? ORDER BY sort_order", (pid,))]

    def set_documents(self, pid: str, docs: list[dict], c: sqlite3.Connection | None = None) -> None:
        def run(cx):
            cx.execute("DELETE FROM calc_documents WHERE project_id=?", (pid,))
            for i, d in enumerate(docs):
                cx.execute("INSERT INTO calc_documents(id, project_id, sort_order, type, name, input_json, result_json) "
                           "VALUES (?,?,?,?,?,?,?)", (new_id(), pid, i, d["type"], d.get("name", "Elemento"),
                                                      json.dumps(d["input"], ensure_ascii=False),
                                                      json.dumps(d.get("result"), ensure_ascii=False)
                                                      if d.get("result") is not None else None))
        if c is not None:
            run(c)
        else:
            with self.db.tx() as cx:
                run(cx)
                self._touch(cx, pid)

    # ------------------------------------------------------------------ exportación / importación
    def export_project(self, pid: str) -> dict:
        p = self.get_project(pid)
        res = self.list_results(pid)
        return {
            "format": FORMAT_ID, "format_version": FORMAT_VERSION, "software_version": __version__,
            "id": p["id"], "name": p["name"], "description": p["description"],
            "created": p["created"], "modified": p["modified"], "norm": p["norm"],
            "parameter_overrides": p["parameter_overrides"],
            "elements": self.list_documents(pid),
            "project": {k: p[k] for k in ("location", "client", "project_date", "structural_system", "status",
                                          "settings")},
            "model": {
                "levels": self.list_levels(pid),
                "elements": [{k: e[k] for k in ("id", "type", "code", "level_id", "description", "data")}
                             for e in self.list_elements(pid)],
                "links": self.list_links(pid),
                "results": [{"element_id": eid, **{k: v for k, v in r.items()}}
                            for eid, rr in res.items() for r in rr.values()],
            },
        }

    def import_project(self, data: dict, history: str = "proyecto_importado", keep_id: bool = False,
                       docs_validator=None) -> str:
        """Crea un proyecto nuevo a partir de un JSON (formato 1 o 2). Los identificadores internos se
        regeneran (salvo ``keep_id``) y las relaciones se reasignan a los nuevos identificadores."""
        if data.get("format") != FORMAT_ID:
            raise ModelError("El fichero no es un proyecto de HA-Anejo19")
        v = data.get("format_version")
        if not isinstance(v, int) or v < 1:
            raise ModelError("Versión de formato ausente o no válida")
        if v > FORMAT_VERSION:
            raise ModelError(f"El proyecto usa el formato {v}, más reciente que el soportado ({FORMAT_VERSION})")
        proj = data.get("project") or {}
        model = data.get("model") or {}
        docs = data.get("elements") or []
        if docs_validator:
            docs = docs_validator(docs)
        pid_src = data.get("id") if keep_id and isinstance(data.get("id"), str) and _ID_RE.match(data["id"]) else None
        info = {"name": data.get("name") or "Proyecto importado", "description": data.get("description", ""),
                **{k: proj.get(k, "") for k in ("location", "client", "project_date", "structural_system")}}
        pid = self.create_project(info, proj.get("settings") or {}, data.get("parameter_overrides") or {},
                                  pid=pid_src, created=data.get("created") if keep_id else None, history=history)
        try:
            lmap: dict[str, str] = {}
            for lv in model.get("levels", []):
                lmap[lv["id"]] = self.create_level(pid, lv["code"], lv)
            emap: dict[str, str] = {}
            for e in model.get("elements", []):
                emap[e["id"]] = self.create_element(pid, e["type"], e["code"], lmap.get(e.get("level_id") or ""),
                                                    e.get("description", ""), e.get("data") or {}, history="elemento_importado")
            for l in model.get("links", []):
                if l["source_id"] not in emap or l["target_id"] not in emap:
                    raise ModelError("Relación con elementos inexistentes en el fichero")
                self.create_link(pid, l["kind"], emap[l["source_id"]], emap[l["target_id"]], l.get("data") or {})
            for r in model.get("results", []):
                if r.get("element_id") in emap and r.get("calc_type") and r.get("input_hash"):
                    with self.db.tx() as c:
                        c.execute("INSERT INTO results(id, element_id, calc_type, status, computed_at, engine_version, "
                                  "input_hash, input_json, output_json, error) VALUES (?,?,?,?,?,?,?,?,?,?)",
                                  (new_id(), emap[r["element_id"]], r["calc_type"], r.get("status", "ok"),
                                   r.get("computed_at") or now(), r.get("engine_version") or "?", r["input_hash"],
                                   json.dumps(r.get("input"), ensure_ascii=False),
                                   json.dumps(r.get("output"), ensure_ascii=False) if r.get("output") is not None else None,
                                   r.get("error")))
            if docs:
                with self.db.tx() as c:
                    self.set_documents(pid, docs, c)
            if proj.get("status") == "archivado":
                with self.db.tx() as c:
                    c.execute("UPDATE projects SET status='archivado' WHERE id=?", (pid,))
        except Exception:
            self.delete_project(pid)
            raise
        return pid
