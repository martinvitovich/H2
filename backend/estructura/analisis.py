"""Transmisión de cargas, dependencias y estado de los resultados del proyecto integral.

A partir de los datos persistidos (proyecto, niveles, elementos y relaciones) se obtienen, de forma
determinista y sin consultar resultados previos:

* las cargas de cada elemento con su procedencia (qué elemento las transmite y con qué regla);
* los datos de entrada del motor de cálculo (``core``) para cada cálculo admitido;
* los datos que faltan para poder calcular (nunca se suponen);
* el grafo de dependencias (aguas arriba / aguas abajo).

El estado de cada resultado guardado se obtiene comparando la huella (SHA-256) de los datos de
entrada actuales con la del cálculo guardado y la versión del motor: si difieren, el resultado está
«desactualizado» y no se presenta como vigente.

Reglas de transmisión (ver docs/proyecto_integral.md):
* Losa: g = h·γ_HA + CM + P_muros/(L·B); q = SCU (kN/m²).
* Losa → viga (área tributaria A): w = carga·A / L_viga; (ancho tributario b): w = carga·b (kN/m).
* Viga: g = b·h·γ_HA + muros + otras + Σ losas; q = otras + Σ losas; cargas puntuales manuales y
  reacciones de las vigas que apoyan en ella (en la posición indicada). Esfuerzos y reacciones por
  equilibrio de la viga isostática (biapoyada o voladizo) o introducidos por el usuario (manual).
* Pilar: N = Σ reacciones de las vigas que apoyan en él + N del pilar superior + peso propio
  (b·h·l·γ_HA) + axiles adicionales; N_Ed = γ_G·N_G + γ_Q·N_Q en la base.
* Zapata: N_k = N_G + N_Q del pilar en su base; presión media σ = (N_k + PP_zapata)/(B·L).
Combinaciones: ELU γ_G·G + γ_Q·Q; característica G + Q; cuasi-permanente G + ψ₂·Q, con una única
acción variable aplicada simultáneamente en todo el elemento (sin alternancia de sobrecargas).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from version import __version__

from .estatica import BeamLoads, cantilever, simply_supported
from .model import TYPE_LABEL

ISOSTATIC_NOTE = ("Esfuerzos por equilibrio de viga isostática: no se consideran continuidad, redistribución, "
                  "alternancia de sobrecargas ni momentos transmitidos a los apoyos.")

CALC_LABEL = {
    "losa_flexion": "Losa — flexión y cortante (momento positivo)",
    "losa_flexion_neg": "Losa — flexión (momento negativo)",
    "viga_flexion": "Viga — flexión ELU (M⁺)",
    "viga_flexion_neg": "Viga — flexión ELU (M⁻)",
    "viga_cortante": "Viga — cortante ELU",
    "viga_fisuracion": "Viga — ELS fisuración",
    "viga_flecha": "Viga — ELS deformaciones",
    "pilar": "Pilar — flexocompresión ELU",
    "zapata_terreno": "Zapata — presión sobre el terreno",
}
CALC_ENDPOINT_KIND = {"losa_flexion": "losa", "losa_flexion_neg": "losa", "viga_flexion": "flexion",
                      "viga_flexion_neg": "flexion", "viga_cortante": "cortante", "viga_fisuracion": "fisuracion",
                      "viga_flecha": "deformaciones", "pilar": "pilar", "zapata_terreno": "zapata"}
CALCS_BY_TYPE = {"losa": ["losa_flexion", "losa_flexion_neg"],
                 "viga": ["viga_flexion", "viga_flexion_neg", "viga_cortante", "viga_fisuracion", "viga_flecha"],
                 "pilar": ["pilar"], "zapata": ["zapata_terreno"]}


def _r(x: float | None, nd: int = 3) -> float | None:
    return None if x is None else round(float(x), nd)


def _rt(x: Any, nd: int = 4) -> Any:
    """Redondeo para presentación (los cálculos internos usan los valores sin redondear)."""
    if isinstance(x, float):
        return round(x, nd)
    if isinstance(x, dict):
        return {k: _rt(v, nd) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_rt(v, nd) for v in x]
    return x


def _f(x: float | None, nd: int = 2) -> str:
    if x is None:
        return "—"
    s = f"{x:.{nd}f}".rstrip("0").rstrip(".")
    return (s if s not in ("-0", "") else "0").replace(".", ",")


def input_hash(calc_type: str, request: dict) -> str:
    blob = json.dumps({"calc": calc_type, "request": request, "engine": __version__}, sort_keys=True,
                      ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass
class Loads:
    """Cargas de un elemento con procedencia. G y Q característicos por separado."""
    g: float | None = None              # losa: kN/m²; viga: kN/m
    q: float | None = None
    points: list[dict] = field(default_factory=list)   # vigas: {pos, G, Q, origen}
    reactions: dict | None = None       # vigas: {"inicio": (G, Q), "fin": (G, Q)}
    efforts: dict | None = None         # vigas/losas: esfuerzos de cálculo y de servicio
    N_G: float | None = None            # pilares: axil en la base (kN)
    N_Q: float | None = None
    rows: list[dict] = field(default_factory=list)     # tabla de procedencia
    missing: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def row(self, concept: str, expr: str, G: float | None = None, Q: float | None = None, unit: str = "",
            origin: str = "", element_id: str | None = None) -> None:
        self.rows.append({"concepto": concept, "expresion": expr, "G": _r(G), "Q": _r(Q), "unidad": unit,
                          "origen": origin, "element_id": element_id})

    @property
    def ok(self) -> bool:
        return not self.missing and not self.errors

    def to_dict(self) -> dict:
        return {"g": _r(self.g, 4), "q": _r(self.q, 4), "points": _rt(self.points),
                "reactions": _rt(self.reactions), "efforts": _rt(self.efforts), "N_G": _r(self.N_G, 4), "N_Q": _r(self.N_Q, 4),
                "rows": self.rows, "missing": self.missing, "errors": self.errors, "warnings": self.warnings,
                "notes": self.notes, "ok": self.ok}


class ProjectAnalysis:
    def __init__(self, project: dict, levels: list[dict], elements: list[dict], links: list[dict],
                 results: dict[str, dict[str, dict]] | None = None) -> None:
        self.p = project
        self.s = project["settings"]
        self.levels = {l["id"]: l for l in levels}
        self.el = {e["id"]: e for e in elements}
        self.links = links
        self.results = results or {}
        self.inc: dict[str, list[dict]] = {}
        self.out: dict[str, list[dict]] = {}
        for l in links:
            self.inc.setdefault(l["target_id"], []).append(l)
            self.out.setdefault(l["source_id"], []).append(l)
        self._loads: dict[str, Loads] = {}
        self._busy: set[str] = set()

    # ------------------------------------------------------------------ utilidades
    def code(self, eid: str) -> str:
        return self.el[eid]["code"]

    def label(self, eid: str) -> str:
        e = self.el[eid]
        return f"{TYPE_LABEL[e['type']]} {e['code']}"

    def upstream(self, eid: str) -> list[str]:
        return [l["source_id"] for l in self.inc.get(eid, [])]

    def downstream(self, eid: str) -> list[str]:
        return [l["target_id"] for l in self.out.get(eid, [])]

    def affected_by(self, eid: str) -> list[str]:
        """Elementos cuyos datos de cálculo dependen (transitivamente) del elemento dado, incluido él."""
        seen, stack = [], [eid]
        while stack:
            n = stack.pop()
            if n in seen or n not in self.el:
                continue
            seen.append(n)
            stack.extend(self.downstream(n))
            # una viga de la que dependen otras vigas apoyadas (las reacciones no cambian, pero sus
            # cargas sí) no se incluye: la dependencia es solo aguas abajo
        return seen

    def topological(self) -> list[str]:
        """Orden de cálculo: cada elemento después de los que le transmiten cargas."""
        indeg = {e: 0 for e in self.el}
        for l in self.links:
            indeg[l["target_id"]] += 1
        order_key = {"losa": 0, "viga": 1, "pilar": 2, "zapata": 3}
        ready = sorted([e for e, d in indeg.items() if d == 0], key=lambda e: (order_key[self.el[e]["type"]],
                                                                              self.code(e)))
        out = []
        while ready:
            n = ready.pop(0)
            out.append(n)
            for t in self.downstream(n):
                indeg[t] -= 1
                if indeg[t] == 0:
                    ready.append(t)
            ready.sort(key=lambda e: (order_key[self.el[e]["type"]], self.code(e)))
        out.extend(e for e in self.el if e not in out)  # ciclos (impedidos al crear relaciones)
        return out

    def _gamma(self) -> float | None:
        return self.s.get("gamma_hormigon")

    def _level_height(self, e: dict) -> float | None:
        lv = self.levels.get(e.get("level_id") or "")
        return lv.get("height_m") if lv else None

    # ------------------------------------------------------------------ cargas
    def loads(self, eid: str) -> Loads:
        if eid in self._loads:
            return self._loads[eid]
        if eid in self._busy:
            ld = Loads()
            ld.errors.append(f"Ciclo en la transmisión de cargas a través de {self.label(eid)}")
            return ld
        self._busy.add(eid)
        try:
            t = self.el[eid]["type"]
            ld = {"losa": self._slab_loads, "viga": self._beam_loads, "pilar": self._column_loads,
                  "zapata": self._footing_loads}[t](self.el[eid])
        finally:
            self._busy.discard(eid)
        self._loads[eid] = ld
        return ld

    def _slab_loads(self, e: dict) -> Loads:
        d, ld = e["data"], Loads()
        gam = self._gamma()
        if d.get("h") is None:
            ld.missing.append("Espesor de la losa")
        if gam is None:
            ld.missing.append("Peso específico del hormigón (configuración del proyecto)")
        if d.get("scu") is None:
            ld.missing.append("Sobrecarga de uso de la losa")
        area = d["lx"] * d["ly"] if d.get("lx") and d.get("ly") else None
        if area is not None:
            ld.row("Superficie", f"{_f(d['lx'])} × {_f(d['ly'])}", area, None, "m²", "Datos de la losa")
        if d.get("muros") and area is None:
            ld.missing.append("Largo y ancho de la losa (para repartir el peso de los muros)")
        if ld.missing:
            return ld
        pp = d["h"] / 1000 * gam
        ld.row("Peso propio", f"h·γ = {_f(d['h'] / 1000, 3)} m × {_f(gam)} kN/m³", pp, None, "kN/m²", "Datos de la losa")
        g = pp + (d.get("cm") or 0)
        ld.row("Carga muerta", "CM", d.get("cm") or 0, None, "kN/m²", "Datos de la losa")
        if d.get("muros"):
            gm = d["muros"] / area
            ld.row("Descarga de muros", f"{_f(d['muros'])} kN / {_f(area)} m²", gm, None, "kN/m²", "Datos de la losa")
            g += gm
        ld.row("Sobrecarga de uso", "SCU", None, d["scu"], "kN/m²", "Datos de la losa")
        ld.g, ld.q = g, d["scu"]
        ld.row("Total", "g; q", g, d["scu"], "kN/m²", "")
        # Reparto a vigas: consistencia del área asignada
        assigned = [l for l in self.out.get(e["id"], []) if l["kind"] == "losa_viga" and l["data"].get("metodo") == "area"]
        if assigned and area:
            tot = sum(l["data"].get("area") or 0 for l in assigned)
            if abs(tot - area) > 0.02 * area:
                ld.warnings.append(f"El área tributaria asignada a vigas ({_f(tot)} m²) no coincide con la superficie "
                                   f"de la losa ({_f(area)} m²): revise el reparto.")
        if not self.out.get(e["id"]):
            ld.warnings.append("La losa no transmite carga a ninguna viga (sin relaciones losa → viga).")
        # Esfuerzos por metro
        gG, gQ, psi2 = self.s["gamma_G"], self.s["gamma_Q"], self.s["psi2"]
        pd = gG * g + gQ * d["scu"]
        mode = d.get("modelo") or "isostatico"
        eff: dict[str, Any] = {"modelo": mode}
        if mode == "manual":
            eff.update({"m_pos": d.get("m_pos"), "m_neg": d.get("m_neg"), "v_ed": d.get("v_ed")})
            if d.get("m_pos") is None and d.get("m_neg") is None:
                ld.missing.append("Momentos de cálculo de la losa (modelo manual)")
            ld.notes.append("Esfuerzos de la losa introducidos por el usuario (análisis externo).")
        elif d.get("tipo") == "bidireccional":
            ld.errors.append("Losa bidireccional: el motor no incluye análisis de placas; seleccione «Manual» e "
                             "introduzca los esfuerzos de un análisis externo.")
        elif not d.get("luz"):
            ld.missing.append("Luz de cálculo de la franja de losa")
        else:
            Lz = d["luz"]
            ld.row("Carga de cálculo por metro", f"γ_G·g + γ_Q·q = {_f(gG)}·{_f(g)} + {_f(gQ)}·{_f(d['scu'])}",
                   pd, None, "kN/m (franja 1 m)", "Combinación ELU")
            if mode == "isostatico":
                eff.update({"m_pos": pd * Lz ** 2 / 8, "m_neg": None, "v_ed": pd * Lz / 2})
                ld.row("m_Ed⁺ (biapoyada)", f"p_d·l²/8 = {_f(pd)}·{_f(Lz)}²/8", eff["m_pos"], None, "kN·m/m", "Equilibrio")
                ld.row("v_Ed (apoyo)", f"p_d·l/2", eff["v_ed"], None, "kN/m", "Equilibrio")
            else:
                eff.update({"m_pos": None, "m_neg": pd * Lz ** 2 / 2, "v_ed": pd * Lz})
                ld.row("|m_Ed⁻| (voladizo)", f"p_d·l²/2 = {_f(pd)}·{_f(Lz)}²/2", eff["m_neg"], None, "kN·m/m", "Equilibrio")
                ld.row("v_Ed (empotramiento)", "p_d·l", eff["v_ed"], None, "kN/m", "Equilibrio")
            ld.notes.append("Franja de 1 m isostática (equilibrio); no se considera continuidad entre paños.")
        ld.efforts = eff
        return ld

    def _beam_loads(self, e: dict) -> Loads:
        d, ld = e["data"], Loads()
        gam = self._gamma()
        for k, lab in (("b", "Ancho de la viga"), ("h", "Canto de la viga"), ("L", "Luz de la viga")):
            if d.get(k) is None:
                ld.missing.append(lab)
        if gam is None:
            ld.missing.append("Peso específico del hormigón (configuración del proyecto)")
        if ld.missing:
            return ld
        L = d["L"]
        pp = d["b"] / 1000 * d["h"] / 1000 * gam
        ld.row("Peso propio", f"b·h·γ = {_f(d['b'] / 1000, 3)}·{_f(d['h'] / 1000, 3)}·{_f(gam)}", pp, None, "kN/m",
               "Datos de la viga")
        g, q = pp, 0.0
        if d.get("muros"):
            ld.row("Muros", "dato", d["muros"], None, "kN/m", "Datos de la viga"); g += d["muros"]
        if d.get("g_extra") or d.get("q_extra"):
            ld.row("Otras cargas", "dato", d.get("g_extra") or 0, d.get("q_extra") or 0, "kN/m", "Datos de la viga")
            g += d.get("g_extra") or 0; q += d.get("q_extra") or 0
        for l in self.inc.get(e["id"], []):
            if l["kind"] != "losa_viga":
                continue
            sl = self.loads(l["source_id"])
            src = self.label(l["source_id"])
            if sl.g is None:
                ld.missing.append(f"Cargas de {src} (faltan datos en la losa)")
                continue
            if l["data"].get("metodo") == "ancho":
                bt = l["data"]["ancho"]
                wg, wq = sl.g * bt, sl.q * bt
                expr = f"carga·b = ({_f(sl.g)}; {_f(sl.q)}) kN/m² × {_f(bt)} m"
            else:
                A = l["data"]["area"]
                wg, wq = sl.g * A / L, sl.q * A / L
                expr = f"carga·A/L = ({_f(sl.g)}; {_f(sl.q)}) kN/m² × {_f(A)} m² / {_f(L)} m"
            ld.row(f"Carga de {src}", expr, wg, wq, "kN/m", src, l["source_id"])
            g += wg; q += wq
        pts = []
        for p in d.get("puntuales") or []:
            if p["pos"] > L:
                ld.errors.append(f"Carga puntual en x = {_f(p['pos'])} m fuera de la luz ({_f(L)} m)")
                continue
            pts.append({"pos": p["pos"], "G": p["G"], "Q": p["Q"], "origen": p.get("desc") or "Carga puntual (dato)"})
            ld.row(f"Puntual en x = {_f(p['pos'])} m", p.get("desc") or "dato", p["G"], p["Q"], "kN", "Datos de la viga")
        for l in self.inc.get(e["id"], []):
            if l["kind"] != "viga_apoyo":
                continue
            src = self.label(l["source_id"])
            bl = self.loads(l["source_id"])
            end = l["data"].get("extremo") or "fin"
            if bl.errors:
                ld.errors.extend(f"{src}: {x}" for x in bl.errors)
                continue
            if bl.reactions is None or bl.reactions.get(end) is None:
                ld.missing.append(f"Reacción de {src} (faltan datos en esa viga)")
                continue
            a = l["data"].get("posicion")
            if a is None or a > L:
                ld.errors.append(f"Posición del apoyo de {src} no válida sobre esta viga")
                continue
            G, Q = bl.reactions[end]
            pts.append({"pos": a, "G": G, "Q": Q, "origen": f"Reacción de {src} ({end})", "element_id": l["source_id"]})
            ld.row(f"Reacción de {src} en x = {_f(a)} m", f"extremo «{end}» de {src}", G, Q, "kN", src, l["source_id"])
        ld.g, ld.q, ld.points = g, q, pts
        ld.row("Total carga repartida", "g; q", g, q, "kN/m", "")
        if ld.missing or ld.errors:
            return ld
        self._beam_efforts(e, ld)
        sup = [l for l in self.out.get(e["id"], []) if l["kind"] == "viga_apoyo"]
        if not sup:
            ld.warnings.append("La viga no tiene apoyos definidos: sus reacciones no se transmiten a ningún elemento.")
        return ld

    def _beam_efforts(self, e: dict, ld: Loads) -> None:
        d = e["data"]
        gG, gQ, psi2 = self.s["gamma_G"], self.s["gamma_Q"], self.s["psi2"]
        L = d["L"]
        if (d.get("modelo") or "isostatico") == "manual":
            ld.notes.append("Esfuerzos y reacciones introducidos por el usuario (análisis externo).")
            eff = {"modelo": "manual", "M_pos": d.get("M_pos"), "M_neg": d.get("M_neg"), "V_ed": d.get("V_ed"),
                   "M_qp": d.get("M_qp"), "M_k": d.get("M_k")}
            if d.get("M_pos") is None and d.get("M_neg") is None:
                ld.missing.append("Momentos de cálculo de la viga (modelo manual)")
            reac = {}
            for end, s in (("inicio", "i"), ("fin", "j")):
                G, Q = d.get(f"R_G_{s}"), d.get(f"R_Q_{s}")
                reac[end] = (G, Q or 0.0) if G is not None else None
            ld.reactions = reac
            ld.efforts = eff
            return
        pts = ld.points
        allpts = [(p["pos"], 0.0) for p in pts]
        sysm = d.get("sistema") or "biapoyada"
        fn = simply_supported if sysm == "biapoyada" else cantilever
        rg = fn(BeamLoads(L, ld.g, [(p["pos"], p["G"]) for p in pts] + allpts))
        rq = fn(BeamLoads(L, ld.q, [(p["pos"], p["Q"]) for p in pts] + allpts))
        xs = rg["x"]
        Md = [gG * a + gQ * b for a, b in zip(rg["M"], rq["M"])]
        if sysm == "biapoyada":
            i = max(range(len(xs)), key=lambda k: Md[k])
            eff = {"M_pos": Md[i], "M_neg": None, "x_Mmax": xs[i]}
            Vi, Vj = gG * rg["R_i"] + gQ * rq["R_i"], gG * rg["R_j"] + gQ * rq["R_j"]
            eff["V_ed"] = max(Vi, Vj)
            reac = {"inicio": (rg["R_i"], rq["R_i"]), "fin": (rg["R_j"], rq["R_j"])}
        else:
            i = 0
            eff = {"M_pos": None, "M_neg": -Md[0], "x_Mmax": 0.0, "V_ed": gG * rg["R_i"] + gQ * rq["R_i"]}
            reac = {"inicio": (rg["R_i"], rq["R_i"]), "fin": None}
            ld.warnings.append("Voladizo: el momento de empotramiento no se transmite al elemento de apoyo "
                               "(solo la reacción vertical).")
        eff["M_k"] = rg["M"][i] + rq["M"][i]
        eff["M_qp"] = rg["M"][i] + psi2 * rq["M"][i]
        eff["modelo"] = "isostatico"
        ld.efforts = eff
        ld.reactions = reac
        tag = "biapoyada" if sysm == "biapoyada" else "voladizo"
        if eff["M_pos"] is not None:
            ld.row("M_Ed⁺ máximo", f"máx(γ_G·M_G + γ_Q·M_Q), x = {_f(xs[i])} m ({tag})", eff["M_pos"], None, "kN·m",
                   "Equilibrio")
        else:
            ld.row("|M_Ed⁻| empotramiento", f"γ_G·M_G + γ_Q·M_Q ({tag})", eff["M_neg"], None, "kN·m", "Equilibrio")
        ld.row("V_Ed máximo", "γ_G·R_G + γ_Q·R_Q (apoyo más cargado)", eff["V_ed"], None, "kN", "Equilibrio")
        ld.row("M característico / cuasi-permanente", "M_G + M_Q; M_G + ψ₂·M_Q", eff["M_k"], eff["M_qp"], "kN·m",
               "Equilibrio")
        for end, v in reac.items():
            if v is not None:
                ld.row(f"Reacción en el {end}", "equilibrio", v[0], v[1], "kN", "Equilibrio")
        ld.notes.append(ISOSTATIC_NOTE)

    def _column_loads(self, e: dict) -> Loads:
        d, ld = e["data"], Loads()
        gam = self._gamma()
        hgt = d.get("altura") or self._level_height(e)
        for k, lab in (("b", "Dimensión b del pilar"), ("h", "Dimensión h del pilar")):
            if d.get(k) is None:
                ld.missing.append(lab)
        if hgt is None:
            ld.missing.append("Altura del pilar (en el pilar o en su nivel)")
        if gam is None:
            ld.missing.append("Peso específico del hormigón (configuración del proyecto)")
        NG, NQ = 0.0, 0.0
        for l in self.inc.get(e["id"], []):
            src = self.label(l["source_id"])
            if l["kind"] == "viga_apoyo":
                bl = self.loads(l["source_id"])
                end = l["data"].get("extremo") or "fin"
                if bl.errors:
                    ld.errors.extend(f"{src}: {x}" for x in bl.errors)
                elif bl.reactions is None or bl.reactions.get(end) is None:
                    ld.missing.append(f"Reacción de {src} (faltan datos en esa viga)")
                else:
                    G, Q = bl.reactions[end]
                    ld.row(f"Reacción de {src}", f"extremo «{end}»", G, Q, "kN", src, l["source_id"])
                    NG += G; NQ += Q
            elif l["kind"] == "pilar_pilar":
                pl = self.loads(l["source_id"])
                if pl.errors:
                    ld.errors.extend(f"{src}: {x}" for x in pl.errors)
                elif pl.N_G is None:
                    ld.missing.append(f"Axil de {src} (faltan datos en el pilar superior)")
                else:
                    ld.row(f"Axil del pilar superior {src}", "N en su base", pl.N_G, pl.N_Q, "kN", src, l["source_id"])
                    NG += pl.N_G; NQ += pl.N_Q
        if d.get("N_G_extra") or d.get("N_Q_extra"):
            ld.row("Axiles adicionales", "dato", d.get("N_G_extra") or 0, d.get("N_Q_extra") or 0, "kN", "Datos del pilar")
            NG += d.get("N_G_extra") or 0; NQ += d.get("N_Q_extra") or 0
        if ld.missing or ld.errors:
            return ld
        pp = d["b"] / 1000 * d["h"] / 1000 * hgt * gam
        ld.row("Peso propio del pilar", f"b·h·l·γ = {_f(d['b'] / 1000, 3)}·{_f(d['h'] / 1000, 3)}·{_f(hgt)}·{_f(gam)}",
               pp, None, "kN", "Datos del pilar")
        NG += pp
        ld.N_G, ld.N_Q = NG, NQ
        gG, gQ = self.s["gamma_G"], self.s["gamma_Q"]
        NEd = gG * NG + gQ * NQ
        ld.row("Axil en la base", "N_G; N_Q", NG, NQ, "kN", "")
        ld.row("N_Ed (base)", f"γ_G·N_G + γ_Q·N_Q = {_f(gG)}·{_f(NG)} + {_f(gQ)}·{_f(NQ)}", NEd, None, "kN",
               "Combinación ELU")
        ld.efforts = {"N_Ed": NEd, "N_k": NG + NQ, "M01": d.get("M01") or 0.0, "M02": d.get("M02") or 0.0,
                      "altura": hgt}
        if not self.inc.get(e["id"]) and not (d.get("N_G_extra") or d.get("N_Q_extra")):
            ld.warnings.append("El pilar no recibe cargas de ninguna viga ni pilar superior.")
        if not any(l["kind"] in ("pilar_pilar", "pilar_zapata") for l in self.out.get(e["id"], [])):
            ld.warnings.append("El pilar no tiene pilar inferior ni zapata asignados.")
        ld.notes.append("El modelo isostático no transmite momentos a los pilares; M₀₁ y M₀₂ son datos del usuario.")
        return ld

    def _footing_loads(self, e: dict) -> Loads:
        d, ld = e["data"], Loads()
        sup = [l for l in self.inc.get(e["id"], []) if l["kind"] == "pilar_zapata"]
        if not sup:
            ld.missing.append("Pilar que apoya en la zapata (relación pilar → zapata)")
            return ld
        src = self.label(sup[0]["source_id"])
        pl = self.loads(sup[0]["source_id"])
        if pl.errors:
            ld.errors.extend(f"{src}: {x}" for x in pl.errors)
            return ld
        if pl.N_G is None:
            ld.missing.append(f"Axil de {src} (faltan datos en el pilar)")
            return ld
        ld.N_G, ld.N_Q = pl.N_G, pl.N_Q
        ld.row(f"Axil del pilar {src}", "N en su base", pl.N_G, pl.N_Q, "kN", src, sup[0]["source_id"])
        return ld

    # ------------------------------------------------------------------ entradas del motor
    def _common(self) -> dict:
        return {"concrete_class": self.s["concrete_class"], "parameter_overrides": self.p["parameter_overrides"]}

    def calc_inputs(self, eid: str) -> dict[str, dict]:
        """Para cada cálculo del elemento: {"request": ...} o {"missing": [...]} / {"error": ...} /
        {"not_applicable": motivo}."""
        e = self.el[eid]
        d, s = e["data"], self.s
        ld = self.loads(eid)
        out: dict[str, dict] = {}
        base_missing = list(ld.missing)
        if ld.errors:
            return {c: {"error": "; ".join(ld.errors)} for c in CALCS_BY_TYPE[e["type"]]}
        name = e["code"]
        if e["type"] == "losa":
            eff = ld.efforts or {}
            for ct, mkey, phik, sk, sign in (("losa_flexion", "m_pos", "phi", "s", 1),
                                              ("losa_flexion_neg", "m_neg", "phi_sup", "s_sup", -1)):
                if base_missing:
                    out[ct] = {"missing": base_missing}
                    continue
                m = eff.get(mkey)
                if m is None or m == 0:
                    out[ct] = {"not_applicable": "Sin momento " + ("positivo" if sign > 0 else "negativo")}
                    continue
                v = eff.get("v_ed") if (ct == "losa_flexion" or eff.get("m_pos") in (None, 0)) else None
                req = {"element_name": name, "mode": "check" if d.get(sk) else "design", "h": d["h"],
                       "cover": s["cover_slab"], "m_Ed_kNm": _r(sign * m, 4), "v_Ed_kN": _r(v or 0.0, 4),
                       "span": _r(d["luz"] * 1000, 1) if d.get("luz") else None, "bar_diameter": d.get(phik) or 12,
                       "bar_spacing": d.get(sk), "steel_grade": s["steel_grade"], "dg": s["dg"], **self._common()}
                out[ct] = {"request": req}
            return out
        if e["type"] == "viga":
            eff = ld.efforts or {}
            layers = d.get("layers") or []
            shape = {"kind": "rectangular", "b": d.get("b"), "h": d.get("h")}
            com = {"element_name": name, "shape": shape, "cover": s["cover_beam"],
                   "stirrup_diameter": d.get("stirrup_phi") or 8, "dg": s["dg"], **self._common()}
            for ct, key, sign in (("viga_flexion", "M_pos", 1), ("viga_flexion_neg", "M_neg", -1)):
                if base_missing:
                    out[ct] = {"missing": base_missing}; continue
                M = eff.get(key)
                if M is None or M == 0:
                    out[ct] = {"not_applicable": "Sin momento " + ("positivo" if sign > 0 else "negativo")}
                    continue
                out[ct] = {"request": {**com, "mode": "check" if layers else "design", "M_Ed_kNm": _r(sign * M, 4),
                                       "layers": layers, "steel_grade": s["steel_grade"],
                                       "stirrup_spacing": d.get("stirrup_s")}}
            need_layers = [] if layers else ["Armadura longitudinal dispuesta (puede adoptar la propuesta del "
                                             "dimensionado a flexión)"]
            tface = "superior" if (eff.get("M_pos") in (None, 0) and eff.get("M_neg")) else "inferior"
            miss = base_missing + need_layers
            if eff.get("V_ed") is None and not base_missing:
                miss = miss + ["Cortante de cálculo V_Ed"]
            out["viga_cortante"] = {"missing": miss} if miss else {"request": {
                **com, "mode": "check" if d.get("stirrup_s") else "design", "stirrup_legs": d.get("stirrup_legs") or 2,
                "stirrup_spacing": d.get("stirrup_s"), "layers": layers, "tension_face": tface,
                "V_Ed_kN": _r(abs(eff["V_ed"]), 4), "stirrup_grade": s["steel_grade"]}}
            miss = base_missing + need_layers
            if eff.get("M_qp") is None and not base_missing:
                miss = miss + ["Momento cuasi-permanente M_qp"]
            out["viga_fisuracion"] = {"missing": miss} if miss else {"request": {
                **com, "layers": layers, "M_qp_kNm": _r(eff["M_qp"], 4),
                "M_char_kNm": _r(eff.get("M_k"), 4), "exposure": s["exposure"], "w_max": s.get("w_max"),
                "steel_grade": s["steel_grade"]}}
            sysd = d.get("sistema_flecha") or "auto"
            if sysd == "auto":
                sysd = "voladizo" if d.get("sistema") == "voladizo" else "biapoyada"
            out["viga_flecha"] = {"missing": miss} if miss else {"request": {
                **com, "layers": layers, "span": _r(d["L"] * 1000, 1), "system": sysd,
                "M_qp_kNm": _r(eff["M_qp"], 4), "RH": s["RH"], "t0": s["t0"], "cement": s["cement"],
                "fragile_partitions": bool(s.get("fragile_partitions")), "steel_grade": s["steel_grade"]}}
            return out
        if e["type"] == "pilar":
            layers = d.get("layers") or []
            miss = base_missing + ([] if layers else ["Armadura longitudinal dispuesta del pilar"])
            eff = ld.efforts or {}
            if not miss and not (eff.get("N_Ed") or 0) > 0:
                return {"pilar": {"error": "El axil de cálculo resulta nulo: el pilar no recibe cargas"}}
            out["pilar"] = {"missing": miss} if miss else {"request": {
                "element_name": name, "b": d["b"], "h": d["h"], "cover": s["cover_column"],
                "stirrup_diameter": d.get("stirrup_phi") or 8, "stirrup_spacing": d.get("stirrup_s"), "dg": s["dg"],
                "layers": layers, "N_Ed_kN": _r(eff["N_Ed"], 4), "M01_kNm": eff["M01"], "M02_kNm": eff["M02"],
                "length": _r(eff["altura"] * 1000, 1), "braced": bool(d.get("braced", True)), "l0_mode": "beta",
                "beta": d.get("beta") or 1.0, "steel_grade": s["steel_grade"], **self._common()}}
            return out
        # zapata
        miss = list(base_missing)
        for k, lab in (("B", "Ancho B de la zapata"), ("L", "Largo L de la zapata"), ("h", "Canto de la zapata")):
            if d.get(k) is None:
                miss.append(lab)
        sig = d.get("sigma_adm") or s.get("sigma_adm")
        if sig is None:
            miss.append("Tensión admisible del terreno (zapata o configuración del proyecto)")
        if s.get("gamma_hormigon") is None:
            miss.append("Peso específico del hormigón")
        out["zapata_terreno"] = {"missing": miss} if miss else {"request": {
            "element_name": name, "B": d["B"], "L": d["L"], "h": d["h"], "N_G_kN": _r(ld.N_G, 4),
            "N_Q_kN": _r(ld.N_Q, 4), "gamma_hormigon": s["gamma_hormigon"], "sigma_adm_kPa": sig}}
        return out

    # ------------------------------------------------------------------ estado
    def calc_status(self, eid: str) -> dict[str, dict]:
        stored = self.results.get(eid, {})
        out = {}
        for ct, inp in self.calc_inputs(eid).items():
            r = stored.get(ct)
            st: dict[str, Any] = {"calc_type": ct, "label": CALC_LABEL[ct], "has_result": r is not None}
            if r is not None:
                st.update({"computed_at": r["computed_at"], "engine_version": r["engine_version"]})
            if "not_applicable" in inp:
                st.update({"status": "no_aplica", "reason": inp["not_applicable"]})
            elif "error" in inp:
                st.update({"status": "error_datos", "reason": inp["error"]})
            elif "missing" in inp:
                st.update({"status": "faltan_datos", "missing": inp["missing"]})
            else:
                h = input_hash(ct, inp["request"])
                st["input_hash"] = h
                if r is None:
                    st["status"] = "sin_calcular"
                elif r["input_hash"] != h or r["engine_version"] != __version__:
                    st["status"] = "desactualizado"
                    st["reason"] = ("Calculado con otra versión del motor" if r["engine_version"] != __version__
                                    and r["input_hash"] == h else "Los datos de entrada han cambiado desde el cálculo")
                elif r["status"] == "error":
                    st.update({"status": "error", "reason": r["error"]})
                else:
                    st["status"] = "actual"
                    st["ok"] = (r["output"] or {}).get("ok")
            out[ct] = st
        return out


def element_status(calcs: dict[str, dict]) -> dict:
    sts = [c["status"] for c in calcs.values() if c["status"] != "no_aplica"]
    if not sts:
        overall = "no_aplica"
    else:
        for k in ("error", "error_datos", "faltan_datos", "desactualizado", "sin_calcular"):
            if k in sts:
                overall = k
                break
        else:
            overall = "actual"
    oks = [c.get("ok") for c in calcs.values() if c["status"] == "actual"]
    if overall != "actual":
        compliance = None
    elif any(o is False for o in oks):
        compliance = "no_cumple"
    elif any(o is None for o in oks):
        compliance = "no_evaluable"
    else:
        compliance = "cumple"
    if any(o is False for o in oks) and overall != "actual":
        compliance = "no_cumple"
    return {"status": overall, "compliance": compliance}
