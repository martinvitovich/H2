"""Aplicación FastAPI: punto de entrada del backend.

Ejecución: ``uvicorn main:app --reload`` desde el directorio ``backend``.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from api.routes import router
from core.elu.analysis import AnalysisError
from core.elu.cortante import ShearInputError
from core.elu.nm import NMError
from core.elu.losas import SlabInputError
from core.elu.pilares import ColumnInputError
from core.els.fisuracion import CrackInputError
from core.els.flechas import DeflectionInputError
from core.els.fluencia import CreepError
from core.elu.flexion import FlexureInputError
from core.materials import MaterialError
from core.parameters import ParameterError
from core.section import SectionError
from services.projects import ProjectError, ProjectNotFound
from version import SOFTWARE_NAME, __version__

app = FastAPI(title=f"{SOFTWARE_NAME} API", version=__version__,
              description="API de cálculo de estructuras de hormigón armado según el Anejo 19 del "
                          "Código Estructural (RD 470/2021).")

origins = os.environ.get("HA_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(ProjectNotFound)
async def _not_found(_: Request, exc: ProjectNotFound):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(ValueError)
async def _value_error(_: Request, exc: ValueError):
    # Errores de validación del dominio (geometría, materiales, parámetros, proyectos...)
    kinds = (SectionError, MaterialError, ParameterError, FlexureInputError, AnalysisError, ProjectError,
             ShearInputError, ColumnInputError, NMError, CrackInputError, DeflectionInputError, CreepError,
             SlabInputError)
    if isinstance(exc, kinds):
        return JSONResponse(status_code=422, content={"detail": str(exc), "type": type(exc).__name__})
    return JSONResponse(status_code=400, content={"detail": str(exc)})


app.include_router(router)

class SPAStaticFiles(StaticFiles):
    """Sirve la compilación del frontend y devuelve index.html para las rutas de la aplicación
    (p. ej. /pilares) que no corresponden a un fichero, de modo que se puedan recargar."""

    async def get_response(self, path, scope):
        from starlette.exceptions import HTTPException as StarletteHTTPException
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404 and not scope.get("path", "").startswith("/api"):
                return await super().get_response("index.html", scope)
            raise


# Si existe una compilación del frontend (npm run build), se sirve desde el backend.
_dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if _dist.is_dir():
    app.mount("/", SPAStaticFiles(directory=_dist, html=True), name="frontend")
