"""Gestión de proyectos con persistencia en una base de datos SQLite (``estructura.db``).

Un proyecto agrupa los datos generales, el modelo estructural integral (niveles, losas, vigas,
pilares, zapatas, relaciones y resultados; ver ``estructura``) y los cálculos independientes de las
calculadoras («documentos de cálculo», formato de proyecto 1).

Esta clase mantiene la API ``/api/proyectos`` del formato 1 (lista, apertura, guardado de los
cálculos independientes, importación JSON) sobre la base de datos. Formato de exportación actual
(``format_version`` = 2)::

    {"format": "ha-anejo19-project", "format_version": 2, "software_version": "...",
     "id", "name", "description", "created", "modified", "norm", "parameter_overrides",
     "elements": [cálculos independientes {"id", "type", "name", "input", "result"}],
     "project": {"location", "client", "project_date", "structural_system", "status", "settings"},
     "model": {"levels": [...], "elements": [...], "links": [...], "results": [...]}}

Migración del almacenamiento anterior: al abrir la base de datos se importan una sola vez los ficheros
``*.json`` (formato 1) del directorio de datos, conservando su identificador. Los ficheros no se
borran ni se modifican; la importación queda registrada en la tabla ``legacy_imports``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from core.parameters import ParameterSet
from estructura.db import DB_FILENAME, Database
from estructura.model import ModelError
from estructura.repository import FORMAT_ID, FORMAT_VERSION, NotFound, Repository, now
from estructura.servicio import StructuralService

ELEMENT_TYPES = {"viga_flexion", "viga_cortante", "pilar", "losa", "els_fisuracion", "els_deformaciones"}


class ProjectError(ModelError):
    pass


class ProjectNotFound(NotFound):
    pass


def migrate(data: dict[str, Any]) -> dict[str, Any]:
    """Comprueba el formato de un proyecto exportado y lo lleva a la versión actual."""
    if data.get("format") != FORMAT_ID:
        raise ProjectError("El fichero no es un proyecto de HA-Anejo19")
    v = data.get("format_version")
    if not isinstance(v, int):
        raise ProjectError("Versión de formato ausente o no válida")
    if v > FORMAT_VERSION:
        raise ProjectError(f"El proyecto usa el formato {v}, más reciente que el soportado ({FORMAT_VERSION})")
    if v == 1:  # v1 → v2: sin modelo estructural
        data = {**data, "format_version": 2, "project": data.get("project") or {}, "model": data.get("model") or {}}
    return data


def validate_documents(docs: list[dict]) -> list[dict]:
    out = []
    for el in docs:
        if el.get("type") not in ELEMENT_TYPES:
            raise ProjectError(f"Tipo de elemento no admitido: {el.get('type')}")
        if not isinstance(el.get("input"), dict):
            raise ProjectError("Cada elemento debe incluir sus datos de entrada ('input')")
        out.append({"type": el["type"], "name": el.get("name", "Elemento"), "input": el["input"],
                    "result": el.get("result")})
    return out


def default_data_dir() -> Path:
    return Path(os.environ.get("HA_DATA_DIR") or Path(__file__).resolve().parents[1] / "data" / "projects")


class ProjectStore:
    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root) if root else default_data_dir()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = Database(os.environ.get("HA_DB_PATH") or self.root / DB_FILENAME) if not root else \
            Database(self.root / DB_FILENAME)
        self.repo = Repository(self.db)
        self.service = StructuralService(self.repo)
        self.import_legacy_files()

    # --- migración de los ficheros JSON del formato anterior
    def import_legacy_files(self) -> list[str]:
        done = {r["filename"] for r in self.repo._q("SELECT filename FROM legacy_imports")}
        imported = []
        for f in sorted(self.root.glob("*.json")):
            if f.name in done:
                continue
            note, pid = "", None
            try:
                data = migrate(json.loads(f.read_text(encoding="utf-8")))
                exists = data.get("id") and self.repo._q("SELECT 1 FROM projects WHERE id=?", (data["id"],))
                if exists:
                    note = "ya existía en la base de datos"
                else:
                    pid = self.repo.import_project(data, history="proyecto_migrado_json", keep_id=True,
                                                   docs_validator=validate_documents)
                    imported.append(pid)
            except (ValueError, json.JSONDecodeError, KeyError) as exc:
                note = f"no importado: {exc}"
            with self.db.tx() as c:
                c.execute("INSERT OR REPLACE INTO legacy_imports(filename, project_id, imported_at, note) "
                          "VALUES (?,?,?,?)", (f.name, pid, now(), note))
        return imported

    # --- API del formato 1
    def list(self) -> list[dict[str, Any]]:
        return [{"id": p["id"], "name": p["name"], "description": p["description"], "modified": p["modified"],
                 "created": p["created"], "n_elements": p["n_documents"], "status": p["status"],
                 "counts": p["counts"]} for p in self.repo.list_projects()]

    def get(self, pid: str) -> dict[str, Any]:
        try:
            return self.repo.export_project(pid)
        except NotFound as exc:
            raise ProjectNotFound(str(exc))

    def create(self, name: str, description: str = "", parameter_overrides: dict | None = None,
               elements: list[dict] | None = None) -> dict[str, Any]:
        docs = validate_documents(elements or [])
        ParameterSet(parameter_overrides or {})
        pid = self.repo.create_project({"name": name, "description": description}, {}, parameter_overrides or {})
        if docs:
            self.repo.set_documents(pid, docs)
        return self.get(pid)

    def update(self, pid: str, name: str, description: str, parameter_overrides: dict,
               elements: list[dict]) -> dict[str, Any]:
        self.get(pid)
        docs = validate_documents(elements)
        self.repo.update_project(pid, {"name": name, "description": description}, None, parameter_overrides)
        self.repo.set_documents(pid, docs)
        return self.get(pid)

    def delete(self, pid: str) -> None:
        try:
            self.repo.delete_project(pid)
        except NotFound as exc:
            raise ProjectNotFound(str(exc))

    def import_json(self, data: dict[str, Any]) -> dict[str, Any]:
        data = migrate(data)
        pid = self.repo.import_project(data, docs_validator=validate_documents)
        return self.get(pid)
