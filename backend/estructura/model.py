"""Definición del modelo de datos del proyecto integral: datos generales, configuración y campos de
cada tipo de elemento (unidades, rangos y valores por defecto).

Es la fuente única de los formularios y tablas editables de la interfaz (``GET /api/estructuras/esquema``)
y de la validación de los datos recibidos. Convenio de unidades del modelo: luces y dimensiones en
planta en m; dimensiones de sección y cantos en mm; cargas superficiales en kN/m², lineales en kN/m,
puntuales en kN; momentos en kN·m.
"""

from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

from core.materials import CONCRETE_FCK_CLASSES, STEEL_GRADES
from core.els.fisuracion import WMAX_RC

ELEMENT_TYPES = ("losa", "viga", "pilar", "zapata")
TYPE_LABEL = {"losa": "Losa", "viga": "Viga", "pilar": "Pilar", "zapata": "Zapata"}
CODE_PREFIX = {"losa": "L", "viga": "V", "pilar": "P", "zapata": "Z"}

LINK_KINDS = {
    # tipo: (tipos origen, tipos destino, descripción)
    "losa_viga": (("losa",), ("viga",), "La losa transmite carga a la viga (área o ancho tributario)"),
    "viga_apoyo": (("viga",), ("pilar", "viga"), "La viga apoya en un pilar o en otra viga"),
    "pilar_pilar": (("pilar",), ("pilar",), "El pilar continúa en el pilar inferior"),
    "pilar_zapata": (("pilar",), ("zapata",), "El pilar se apoya en la zapata"),
}


class ModelError(ValueError):
    pass


def F(key: str, label: str, kind: str = "number", unit: str = "", default: Any = None, min: float | None = None,
      max: float | None = None, options: list | None = None, help: str = "", group: str = "",
      table: bool = False) -> dict:
    return {"key": key, "label": label, "kind": kind, "unit": unit, "default": default, "min": min, "max": max,
            "options": options, "help": help, "group": group, "table": table}


_CONC = [{"value": c, "label": c} for c in CONCRETE_FCK_CLASSES]
_STEEL = [{"value": s, "label": s} for s in STEEL_GRADES]
_EXPO = [{"value": k, "label": k} for k in WMAX_RC]

# Configuración del proyecto. Los valores que no proceden del Anejo 19 se marcan en ``origin``.
SETTINGS_FIELDS: list[dict] = [
    F("concrete_class", "Hormigón", "select", "", "C25/30", options=_CONC, group="Materiales"),
    F("steel_grade", "Acero de armaduras", "select", "", "B500S", options=_STEEL, group="Materiales"),
    F("gamma_hormigon", "Peso específico del hormigón armado", "number", "kN/m³", 25.0, 15, 30, group="Acciones",
      help="Valor de proyecto definido por el usuario (no procede del Anejo 19)."),
    F("gamma_G", "Coeficiente parcial de acciones permanentes γ_G", "number", "", 1.35, 1.0, 2.0, group="Acciones",
      help="Combinaciones de acciones: fuera del alcance del Anejo 19. Valor por defecto del programa; "
           "el usuario debe confirmarlo para su proyecto."),
    F("gamma_Q", "Coeficiente parcial de acciones variables γ_Q", "number", "", 1.5, 1.0, 2.0, group="Acciones",
      help="Fuera del alcance del Anejo 19. Valor por defecto del programa; debe confirmarlo el usuario."),
    F("psi2", "Coeficiente de combinación cuasi-permanente ψ₂", "number", "", 0.3, 0.0, 1.0, group="Acciones",
      help="Depende del uso del edificio (fuera del alcance del Anejo 19). Valor por defecto del programa; "
           "debe confirmarlo el usuario."),
    F("cover_slab", "Recubrimiento nominal en losas (a la armadura principal)", "number", "mm", 25.0, 10, 100,
      group="Recubrimientos", help="Definido por el usuario; la comprobación por durabilidad (4.4.1) no está implementada."),
    F("cover_beam", "Recubrimiento nominal en vigas (al estribo)", "number", "mm", 30.0, 10, 100, group="Recubrimientos"),
    F("cover_column", "Recubrimiento nominal en pilares (al estribo)", "number", "mm", 30.0, 10, 100, group="Recubrimientos"),
    F("cover_footing", "Recubrimiento nominal en cimentación", "number", "mm", 50.0, 10, 150, group="Recubrimientos"),
    F("dg", "Tamaño máximo del árido d_g", "number", "mm", 20.0, 4, 63, group="Materiales"),
    F("exposure", "Clase de exposición (fisuración)", "select", "", "XC1", options=_EXPO, group="Servicio"),
    F("w_max", "Abertura máxima de fisura del proyecto (vacío = tabla 27.2)", "number", "mm", None, 0.05, 1.0,
      group="Servicio"),
    F("RH", "Humedad relativa ambiente", "number", "%", 60.0, 40, 100, group="Servicio"),
    F("cement", "Tipo de cemento (fluencia y retracción)", "select", "", "N",
      options=[{"value": "S", "label": "S (lento)"}, {"value": "N", "label": "N (normal)"},
               {"value": "R", "label": "R (rápido)"}], group="Servicio"),
    F("t0", "Edad del hormigón en la puesta en carga", "number", "días", 28.0, 1, 10000, group="Servicio"),
    F("fragile_partitions", "Tabiquería frágil (límites de flecha)", "bool", "", False, group="Servicio"),
    F("sigma_adm", "Tensión admisible del terreno", "number", "kPa", None, 10, 5000, group="Cimentación",
      help="Dato geotécnico del proyecto (estudio geotécnico). Imprescindible para la comprobación de zapatas."),
]

SETTINGS_ORIGIN = {
    "gamma_hormigon": "definido por el usuario (dato de proyecto)",
    "gamma_G": "valor por defecto del programa — confirmar (combinaciones fuera del Anejo 19)",
    "gamma_Q": "valor por defecto del programa — confirmar (combinaciones fuera del Anejo 19)",
    "psi2": "valor por defecto del programa — confirmar según el uso (fuera del Anejo 19)",
    "sigma_adm": "dato geotécnico del proyecto",
}

LAYERS_HELP = "Capas de armadura dispuesta: cara (inferior/superior/lateral), n.º de barras y diámetro."

ELEMENT_FIELDS: dict[str, list[dict]] = {
    "losa": [
        F("tipo", "Tipo de losa", "select", "", "unidireccional",
          options=[{"value": "unidireccional", "label": "Maciza unidireccional"},
                   {"value": "bidireccional", "label": "Maciza bidireccional"}], group="Geometría", table=True),
        F("lx", "Largo", "number", "m", None, 0.1, 50, group="Geometría", table=True),
        F("ly", "Ancho", "number", "m", None, 0.1, 50, group="Geometría", table=True),
        F("h", "Espesor", "number", "mm", 150.0, 50, 1000, group="Geometría", table=True),
        F("cm", "Carga muerta (solados, revestimientos…)", "number", "kN/m²", 0.0, 0, 100, group="Cargas", table=True),
        F("scu", "Sobrecarga de uso", "number", "kN/m²", None, 0, 100, group="Cargas", table=True),
        F("muros", "Peso total de muros sobre la losa", "number", "kN", 0.0, 0, 1e5, group="Cargas", table=True,
          help="Se reparte uniformemente sobre la superficie de la losa (descarga de muros = peso/superficie)."),
        F("modelo", "Obtención de esfuerzos", "select", "", "isostatico",
          options=[{"value": "isostatico", "label": "Isostático: franja de 1 m biapoyada (luz de cálculo)"},
                   {"value": "voladizo", "label": "Isostático: franja de 1 m en voladizo"},
                   {"value": "manual", "label": "Manual (esfuerzos de un análisis externo)"}], group="Esfuerzos",
          table=True,
          help="El motor no incluye análisis de placas ni de continuidad: losas bidireccionales y continuas "
               "requieren esfuerzos manuales."),
        F("luz", "Luz de cálculo (franja unidireccional)", "number", "m", None, 0.1, 50, group="Esfuerzos", table=True),
        F("m_pos", "Momento de cálculo positivo m_Ed⁺ (manual)", "number", "kN·m/m", None, 0, 1e4, group="Esfuerzos"),
        F("m_neg", "Momento de cálculo negativo |m_Ed⁻| (manual)", "number", "kN·m/m", None, 0, 1e4, group="Esfuerzos"),
        F("v_ed", "Cortante de cálculo v_Ed (manual)", "number", "kN/m", None, 0, 1e4, group="Esfuerzos"),
        F("phi", "Diámetro armadura principal inferior", "number", "mm", 12.0, 5, 40, group="Armadura"),
        F("s", "Separación armadura inferior dispuesta (vacío = dimensionar)", "number", "mm", None, 20, 1000,
          group="Armadura"),
        F("phi_sup", "Diámetro armadura superior (negativos)", "number", "mm", 12.0, 5, 40, group="Armadura"),
        F("s_sup", "Separación armadura superior dispuesta (vacío = dimensionar)", "number", "mm", None, 20, 1000,
          group="Armadura"),
    ],
    "viga": [
        F("b", "Ancho b", "number", "mm", 250.0, 100, 3000, group="Sección", table=True),
        F("h", "Canto h", "number", "mm", 500.0, 100, 3000, group="Sección", table=True),
        F("L", "Luz", "number", "m", None, 0.1, 50, group="Geometría", table=True),
        F("sistema", "Sistema estructural", "select", "", "biapoyada",
          options=[{"value": "biapoyada", "label": "Biapoyada (isostática)"},
                   {"value": "voladizo", "label": "Voladizo (empotrada en el inicio)"}], group="Geometría", table=True),
        F("posicion", "Posición", "select", "", "INT",
          options=[{"value": "INT", "label": "Interior"}, {"value": "EXT", "label": "Exterior"}], group="Geometría",
          table=True),
        F("invertida", "Viga invertida", "bool", "", False, group="Geometría"),
        F("muros", "Carga lineal de muros", "number", "kN/m", 0.0, 0, 1000, group="Cargas", table=True),
        F("g_extra", "Otras cargas permanentes", "number", "kN/m", 0.0, 0, 1000, group="Cargas", table=True),
        F("q_extra", "Otras cargas variables", "number", "kN/m", 0.0, 0, 1000, group="Cargas", table=True),
        F("puntuales", "Cargas puntuales adicionales", "pointloads", "", [], group="Cargas",
          help="Posición desde el inicio de la viga (m), G y Q característicos (kN)."),
        F("modelo", "Obtención de esfuerzos", "select", "", "isostatico",
          options=[{"value": "isostatico", "label": "Isostático según el sistema (sin continuidad)"},
                   {"value": "manual", "label": "Manual (esfuerzos de un análisis externo)"}], group="Esfuerzos",
          table=True),
        F("M_pos", "M_Ed⁺ máximo (manual)", "number", "kN·m", None, 0, 1e5, group="Esfuerzos"),
        F("M_neg", "|M_Ed⁻| máximo (manual)", "number", "kN·m", None, 0, 1e5, group="Esfuerzos"),
        F("V_ed", "V_Ed máximo (manual)", "number", "kN", None, 0, 1e5, group="Esfuerzos"),
        F("M_qp", "M cuasi-permanente máximo en vano (manual, con signo)", "number", "kN·m", None, -1e5, 1e5,
          group="Esfuerzos"),
        F("M_k", "M característico máximo en vano (manual, con signo)", "number", "kN·m", None, -1e5, 1e5,
          group="Esfuerzos"),
        F("R_G_i", "Reacción permanente en el inicio (manual)", "number", "kN", None, -1e5, 1e5, group="Esfuerzos"),
        F("R_Q_i", "Reacción variable en el inicio (manual)", "number", "kN", None, -1e5, 1e5, group="Esfuerzos"),
        F("R_G_j", "Reacción permanente en el final (manual)", "number", "kN", None, -1e5, 1e5, group="Esfuerzos"),
        F("R_Q_j", "Reacción variable en el final (manual)", "number", "kN", None, -1e5, 1e5, group="Esfuerzos"),
        F("sistema_flecha", "Sistema para ELS de deformaciones", "select", "", "auto",
          options=[{"value": "auto", "label": "Según el sistema estructural"},
                   {"value": "continua_extremo", "label": "Vano extremo de viga continua"},
                   {"value": "continua_interior", "label": "Vano interior de viga continua"}], group="Esfuerzos"),
        F("layers", "Armadura longitudinal dispuesta", "layers", "", [], group="Armadura", help=LAYERS_HELP),
        F("stirrup_phi", "Diámetro de estribos", "number", "mm", 8.0, 5, 20, group="Armadura"),
        F("stirrup_s", "Separación de estribos dispuesta (vacío = dimensionar)", "number", "mm", None, 25, 1000,
          group="Armadura"),
        F("stirrup_legs", "Ramas de estribo", "int", "", 2, 2, 8, group="Armadura"),
    ],
    "pilar": [
        F("b", "Dimensión b (perpendicular al plano de flexión)", "number", "mm", 300.0, 100, 3000, group="Sección",
          table=True),
        F("h", "Dimensión h (en el plano de flexión)", "number", "mm", 300.0, 100, 3000, group="Sección", table=True),
        F("altura", "Altura libre (vacío = altura del nivel)", "number", "m", None, 0.3, 50, group="Geometría",
          table=True),
        F("beta", "Factor de longitud de pandeo β (l₀ = β·l)", "number", "", 1.0, 0.5, 5, group="Geometría", table=True),
        F("braced", "Pilar arriostrado (intraslacional)", "bool", "", True, group="Geometría"),
        F("M01", "Momento de primer orden M₀₁ (extremo menor)", "number", "kN·m", 0.0, -1e5, 1e5, group="Esfuerzos",
          help="El modelo isostático no transmite momentos a los pilares: introdúzcalos si proceden de un "
               "análisis externo."),
        F("M02", "Momento de primer orden M₀₂ (extremo mayor)", "number", "kN·m", 0.0, -1e5, 1e5, group="Esfuerzos"),
        F("N_G_extra", "Axil permanente adicional", "number", "kN", 0.0, 0, 1e5, group="Esfuerzos", table=True),
        F("N_Q_extra", "Axil variable adicional", "number", "kN", 0.0, 0, 1e5, group="Esfuerzos", table=True),
        F("layers", "Armadura longitudinal dispuesta", "layers", "", [], group="Armadura", help=LAYERS_HELP),
        F("stirrup_phi", "Diámetro de cercos", "number", "mm", 8.0, 5, 20, group="Armadura"),
        F("stirrup_s", "Separación de cercos", "number", "mm", None, 25, 1000, group="Armadura"),
    ],
    "zapata": [
        F("B", "Ancho B", "number", "m", None, 0.3, 20, group="Geometría", table=True),
        F("L", "Largo L", "number", "m", None, 0.3, 20, group="Geometría", table=True),
        F("h", "Canto", "number", "mm", 500.0, 200, 3000, group="Geometría", table=True),
        F("sigma_adm", "Tensión admisible del terreno (vacío = la del proyecto)", "number", "kPa", None, 10, 5000,
          group="Terreno", table=True),
    ],
}

LINK_FIELDS: dict[str, list[dict]] = {
    "losa_viga": [
        F("metodo", "Método de reparto", "select", "", "area",
          options=[{"value": "area", "label": "Área tributaria (q·A/L)"},
                   {"value": "ancho", "label": "Ancho tributario (q·b)"}]),
        F("area", "Área tributaria", "number", "m²", None, 0.001, 1e4),
        F("ancho", "Ancho tributario", "number", "m", None, 0.001, 100),
    ],
    "viga_apoyo": [
        F("extremo", "Extremo de la viga", "select", "", "fin",
          options=[{"value": "inicio", "label": "Inicio"}, {"value": "fin", "label": "Final"}]),
        F("posicion", "Posición en la viga de apoyo (desde su inicio)", "number", "m", None, 0, 100,
          help="Solo cuando apoya en otra viga."),
    ],
    "pilar_pilar": [],
    "pilar_zapata": [],
}

SETTINGS_DEFAULTS = {f["key"]: f["default"] for f in SETTINGS_FIELDS}


def schema() -> dict:
    return {"settings": SETTINGS_FIELDS, "settings_origin": SETTINGS_ORIGIN, "elements": ELEMENT_FIELDS,
            "links": LINK_FIELDS, "link_kinds": {k: {"source": v[0], "target": v[1], "label": v[2]}
                                                 for k, v in LINK_KINDS.items()},
            "types": {t: {"label": TYPE_LABEL[t], "prefix": CODE_PREFIX[t]} for t in ELEMENT_TYPES}}


def _clean_value(f: dict, v: Any, where: str) -> Any:
    if v is None or v == "":
        return None
    k = f["kind"]
    try:
        if k == "number":
            v = float(v)
            if not math.isfinite(v):
                raise ValueError
        elif k == "int":
            v = int(v)
        elif k == "bool":
            if not isinstance(v, bool):
                raise ValueError
        elif k in ("select", "text"):
            v = str(v)
    except (TypeError, ValueError):
        raise ModelError(f"{where}: «{f['label']}» no es válido ({v!r})")
    if k in ("number", "int"):
        if f["min"] is not None and v < f["min"]:
            raise ModelError(f"{where}: «{f['label']}» = {v} es menor que el mínimo admitido ({f['min']} {f['unit']})")
        if f["max"] is not None and v > f["max"]:
            raise ModelError(f"{where}: «{f['label']}» = {v} supera el máximo admitido ({f['max']} {f['unit']})")
    if k == "select" and f["options"] and v not in [o["value"] for o in f["options"]]:
        raise ModelError(f"{where}: «{f['label']}» = {v!r} no es una opción admitida")
    if k == "layers":
        out = []
        if not isinstance(v, list):
            raise ModelError(f"{where}: la armadura debe ser una lista de capas")
        for i, ly in enumerate(v):
            try:
                face = str(ly["face"])
                n = int(ly["n"])
                d = float(ly["diameter"])
            except (KeyError, TypeError, ValueError):
                raise ModelError(f"{where}: capa de armadura {i + 1} incompleta (cara, n, diámetro)")
            if face not in ("inferior", "superior", "lateral") or not 1 <= n <= 30 or not 5 <= d <= 40:
                raise ModelError(f"{where}: capa de armadura {i + 1} fuera de rango")
            depth = ly.get("depth")
            if depth not in (None, ""):
                try:
                    depth = float(depth)
                except (TypeError, ValueError):
                    raise ModelError(f"{where}: profundidad de la capa {i + 1} no válida")
                if depth <= 0:
                    raise ModelError(f"{where}: profundidad de la capa {i + 1} no válida")
            out.append({"face": face, "n": n, "diameter": d, **({"depth": depth} if depth not in (None, "") else {})})
        return out
    if k == "pointloads":
        out = []
        if not isinstance(v, list):
            raise ModelError(f"{where}: las cargas puntuales deben ser una lista")
        for i, p in enumerate(v):
            try:
                a = float(p["pos"])
                g = float(p.get("G") or 0)
                q = float(p.get("Q") or 0)
            except (KeyError, TypeError, ValueError):
                raise ModelError(f"{where}: carga puntual {i + 1} incompleta (posición, G, Q)")
            if a < 0 or g < 0 or q < 0:
                raise ModelError(f"{where}: carga puntual {i + 1}: valores negativos no admitidos")
            out.append({"pos": a, "G": g, "Q": q, "desc": str(p.get("desc") or "")[:120]})
        return out
    return v


def clean_fields(fields: list[dict], data: dict[str, Any] | None, where: str, fill_defaults: bool) -> dict:
    data = data or {}
    known = {f["key"] for f in fields}
    unknown = set(data) - known
    if unknown:
        raise ModelError(f"{where}: campos no reconocidos: {', '.join(sorted(unknown))}")
    out = {}
    for f in fields:
        if f["key"] in data:
            out[f["key"]] = _clean_value(f, data[f["key"]], where)
        elif fill_defaults:
            out[f["key"]] = deepcopy(f["default"])
    return out


def clean_element_data(etype: str, data: dict | None, where: str = "Elemento", fill_defaults: bool = True) -> dict:
    if etype not in ELEMENT_FIELDS:
        raise ModelError(f"Tipo de elemento no admitido: {etype}")
    return clean_fields(ELEMENT_FIELDS[etype], data, where, fill_defaults)


def clean_settings(data: dict | None, fill_defaults: bool = True) -> dict:
    return clean_fields(SETTINGS_FIELDS, data, "Configuración del proyecto", fill_defaults)


def clean_link_data(kind: str, data: dict | None) -> dict:
    if kind not in LINK_FIELDS:
        raise ModelError(f"Tipo de relación no admitido: {kind}")
    return clean_fields(LINK_FIELDS[kind], data, "Relación", True)
