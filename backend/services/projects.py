"""Gestión de proyectos con persistencia local en ficheros JSON versionados.

Formato de almacenamiento (``format_version`` = 1)::

    {
      "format": "ha-anejo19-project",
      "format_version": 1,
      "software_version": "0.4.0",
      "id": "<uuid>",
      "name": "...", "description": "...",
      "created": "<ISO 8601>", "modified": "<ISO 8601>",
      "norm": {"id": ..., "name": ..., "edition": ...},
      "parameter_overrides": {...},
      "elements": [
        {"id": "<uuid>", "type": "viga_flexion" | "viga_cortante" | "pilar", "name": "...",
         "input": {... FlexureRequest | ShearRequest ...}, "result": {...} | null}
      ]
    }

La interfaz ``ProjectStore`` aísla el almacenamiento para poder sustituirlo por una
base de datos sin cambiar la API.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.parameters import ParameterSet, norm_info
from version import __version__

FORMAT_ID = "ha-anejo19-project"
FORMAT_VERSION = 1
ELEMENT_TYPES = {"viga_flexion", "viga_cortante", "pilar"}

_ID_RE = re.compile(r"^[0-9a-f]{32}$")


class ProjectError(ValueError):
    pass


class ProjectNotFound(ProjectError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def migrate(data: dict[str, Any]) -> dict[str, Any]:
    """Actualiza un proyecto de una versión de formato anterior a la actual."""
    if data.get("format") != FORMAT_ID:
        raise ProjectError("El fichero no es un proyecto de HA-Anejo19")
    v = data.get("format_version")
    if not isinstance(v, int):
        raise ProjectError("Versión de formato ausente o no válida")
    if v > FORMAT_VERSION:
        raise ProjectError(f"El proyecto usa el formato {v}, más reciente que el soportado ({FORMAT_VERSION})")
    # v == 1: formato actual. Las migraciones futuras se encadenan aquí (v1 → v2 → ...).
    return data


def validate_project(data: dict[str, Any]) -> None:
    ParameterSet(data.get("parameter_overrides") or {})  # lanza ParameterError si no es válido
    for el in data.get("elements", []):
        if el.get("type") not in ELEMENT_TYPES:
            raise ProjectError(f"Tipo de elemento no admitido: {el.get('type')}")
        if not isinstance(el.get("input"), dict):
            raise ProjectError("Cada elemento debe incluir sus datos de entrada ('input')")


class ProjectStore:
    def __init__(self, root: Path | str | None = None) -> None:
        root = root or os.environ.get("HA_DATA_DIR") or Path(__file__).resolve().parents[1] / "data" / "projects"
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, pid: str) -> Path:
        if not _ID_RE.match(pid):
            raise ProjectNotFound(f"Identificador de proyecto no válido: {pid}")
        return self.root / f"{pid}.json"

    def list(self) -> list[dict[str, Any]]:
        out = []
        for f in self.root.glob("*.json"):
            try:
                d = migrate(json.loads(f.read_text(encoding="utf-8")))
            except (ProjectError, json.JSONDecodeError):
                continue
            out.append({"id": d["id"], "name": d["name"], "description": d.get("description", ""),
                        "modified": d["modified"], "created": d["created"],
                        "n_elements": len(d.get("elements", []))})
        return sorted(out, key=lambda x: x["modified"], reverse=True)

    def get(self, pid: str) -> dict[str, Any]:
        p = self._path(pid)
        if not p.exists():
            raise ProjectNotFound(f"No existe el proyecto {pid}")
        return migrate(json.loads(p.read_text(encoding="utf-8")))

    def _write(self, data: dict[str, Any]) -> None:
        p = self._path(data["id"])
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(p)

    def create(self, name: str, description: str = "", parameter_overrides: dict | None = None,
               elements: list[dict] | None = None) -> dict[str, Any]:
        now = _now()
        data = {
            "format": FORMAT_ID, "format_version": FORMAT_VERSION, "software_version": __version__,
            "id": uuid.uuid4().hex, "name": name, "description": description,
            "created": now, "modified": now, "norm": norm_info(),
            "parameter_overrides": parameter_overrides or {},
            "elements": [self._normalize_element(e) for e in (elements or [])],
        }
        validate_project(data)
        self._write(data)
        return data

    def update(self, pid: str, name: str, description: str, parameter_overrides: dict,
               elements: list[dict]) -> dict[str, Any]:
        data = self.get(pid)
        data.update({"name": name, "description": description,
                     "parameter_overrides": parameter_overrides,
                     "elements": [self._normalize_element(e) for e in elements],
                     "modified": _now(), "software_version": __version__})
        validate_project(data)
        self._write(data)
        return data

    def delete(self, pid: str) -> None:
        p = self._path(pid)
        if not p.exists():
            raise ProjectNotFound(f"No existe el proyecto {pid}")
        p.unlink()

    def import_json(self, data: dict[str, Any]) -> dict[str, Any]:
        data = migrate(data)
        return self.create(data.get("name", "Proyecto importado"), data.get("description", ""),
                           data.get("parameter_overrides", {}), data.get("elements", []))

    @staticmethod
    def _normalize_element(e: dict[str, Any]) -> dict[str, Any]:
        return {"id": e.get("id") or uuid.uuid4().hex, "type": e.get("type"),
                "name": e.get("name", "Elemento"), "input": e.get("input"),
                "result": e.get("result")}
