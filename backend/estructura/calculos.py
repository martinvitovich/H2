"""Ejecución de los cálculos de los elementos del proyecto integral.

Los cálculos del Anejo 19 se delegan sin cambios en el motor (``core``) a través de los mismos
modelos de entrada que usa la API (validación Pydantic incluida). La única comprobación propia de
este módulo es la presión media de las zapatas sobre el terreno, que no pertenece al Anejo 19 y se
identifica como tal.
"""

from __future__ import annotations

import math

from api.schemas import ColumnRequest, CrackRequest, DeflectionRequest, FlexureRequest, ShearRequest, SlabRequest
from core.elu.cortante import shear_beam
from core.elu.flexion import check_flexure, design_flexure
from core.elu.losas import slab_check
from core.elu.pilares import column_check
from core.els.fisuracion import crack_check
from core.els.flechas import deflection_check
from core.trace import CalcTrace, fmt

from .model import ModelError


def _flexure(req: dict) -> dict:
    r = FlexureRequest.model_validate(req)
    inp = r.build()
    return design_flexure(inp) if r.mode == "design" else check_flexure(inp)


def footing_soil(req: dict) -> dict:
    """Presión media sobre el terreno de una zapata aislada con carga centrada (sin momentos)."""
    B, L, h = req["B"], req["L"], req["h"] / 1000
    NG, NQ, gam, sadm = req["N_G_kN"], req["N_Q_kN"], req["gamma_hormigon"], req["sigma_adm_kPa"]
    tr = CalcTrace("Zapata aislada — presión media sobre el terreno",
                   "Equilibrio vertical con carga centrada y distribución uniforme de presiones",
                   "Comprobación geotécnica simplificada: fuera del ámbito del Anejo 19")
    tr.inputs = {"B": B, "L": L, "h": h, "N_G": NG, "N_Q": NQ, "gamma_HA": gam, "sigma_adm": sadm}
    tr.units = {"B, L, h": "m", "N": "kN", "γ": "kN/m³", "σ": "kPa"}
    tr.assume("Carga vertical centrada; no se consideran momentos ni excentricidades en la base del pilar.")
    tr.assume("Presión uniforme bajo la zapata; peso del relleno sobre la zapata no incluido.")
    tr.assume("Combinación característica (G + Q) frente a la tensión admisible del estudio geotécnico.")
    tr.limit("El dimensionado estructural de la zapata (flexión, cortante y punzonamiento; Anejo 19, 9.8 y 6.4) "
             "no está implementado.")
    tr.limit("No se comprueban vuelco, deslizamiento ni asientos.")
    A = B * L
    tr.step("Superficie de apoyo", "Geometría", "A = B·L", f"{fmt(B)}·{fmt(L)}", A, "m²", "A")
    pp = A * h * gam
    tr.step("Peso propio de la zapata", "Dato de proyecto γ_HA", "PP = A·h·γ", f"{fmt(A)}·{fmt(h)}·{fmt(gam)}", pp,
            "kN", "PP")
    Nk = NG + NQ
    tr.step("Axil característico del pilar", "Bajada de cargas", "N_k = N_G + N_Q", f"{fmt(NG)} + {fmt(NQ)}", Nk,
            "kN", "N_k")
    sig = (Nk + pp) / A
    tr.step("Presión media", "Equilibrio", "σ = (N_k + PP)/A", f"({fmt(Nk)} + {fmt(pp)})/{fmt(A)}", sig, "kPa", "σ")
    ok = tr.check("Presión media ≤ tensión admisible", "Estudio geotécnico (no Anejo 19)", f"σ = {fmt(sig)} kPa",
                  f"σ_adm = {fmt(sadm)} kPa", sig <= sadm)
    return {"ok": ok, "trace": tr.to_dict(), "result": {"A": A, "PP": pp, "N_k": Nk, "sigma": sig, "sigma_adm": sadm,
                                                        "B_min_cuadrada": math.sqrt((Nk + pp) / sadm)}}


ENGINE = {
    "losa_flexion": lambda r: slab_check(SlabRequest.model_validate(r).build()),
    "losa_flexion_neg": lambda r: slab_check(SlabRequest.model_validate(r).build()),
    "viga_flexion": _flexure,
    "viga_flexion_neg": _flexure,
    "viga_cortante": lambda r: shear_beam(ShearRequest.model_validate(r).build()),
    "viga_fisuracion": lambda r: crack_check(CrackRequest.model_validate(r).build()),
    "viga_flecha": lambda r: deflection_check(DeflectionRequest.model_validate(r).build()),
    "pilar": lambda r: column_check(ColumnRequest.model_validate(r).build()),
    "zapata_terreno": footing_soil,
}


def run(calc_type: str, request: dict) -> dict:
    if calc_type not in ENGINE:
        raise ModelError(f"Cálculo no admitido: {calc_type}")
    return ENGINE[calc_type](request)


def _layers_text(layers: list[dict]) -> str:
    by = {}
    for l in layers:
        by.setdefault(l["face"], []).append(f"{l['n']}Ø{fmt(l['diameter'], 0)}")
    return "; ".join(f"{k[:3]}.: {' + '.join(v)}" for k, v in by.items())


def summary(calc_type: str, request: dict, out: dict) -> dict:
    """Valores clave de un resultado para las tablas resumen (unidades de la interfaz)."""
    s: dict = {"ok": out.get("ok")}
    try:
        if calc_type in ("viga_flexion", "viga_flexion_neg"):
            s["M_Ed"] = request["M_Ed_kNm"]
            if out.get("mode") == "design":
                d, p = out.get("design") or {}, out.get("proposal") or {}
                s["As_nec"] = d.get("As1_req")
                s["As_min"] = d.get("As_min")
                s["armado"] = " + ".join(x for x in (p.get("text_tension"), p.get("text_compression") and
                                                    f"comp. {p['text_compression']}") if x) or None
                s["texto"] = f"Propuesta: {s['armado'] or '—'} (A_s,nec = {fmt(s['As_nec'] or 0, 0)} mm²)"
            else:
                v = out.get("verification") or {}
                s["M_Rd"] = v.get("M_Rd") / 1e6 if v.get("M_Rd") is not None else None
                s["armado"] = _layers_text(request.get("layers") or [])
                s["texto"] = f"M_Rd = {fmt(s['M_Rd'] or 0, 1)} kN·m ({s['armado']})"
        elif calc_type == "viga_cortante":
            r = out.get("result") or {}
            s["V_Ed"] = request["V_Ed_kN"]
            if out.get("mode") == "design":
                p = r.get("proposal") or {}
                s["estribos"] = (f"cØ{fmt(p['diameter'], 0)} ({p['legs']} ramas) c/{fmt(p['spacing'], 0)} mm"
                                 if p else None)
                s["texto"] = f"Propuesta: {s['estribos'] or '—'}"
            else:
                s["estribos"] = (f"cØ{fmt(request['stirrup_diameter'], 0)} ({request['stirrup_legs']} ramas) "
                                 f"c/{fmt(request['stirrup_spacing'], 0)} mm")
                s["V_Rd"] = min(x for x in (r.get("VRd_s"), r.get("VRd_max")) if x is not None) / 1e3 \
                    if r.get("VRd_s") is not None else None
                s["texto"] = f"{s['estribos']}; V_Rd = {fmt(s['V_Rd'] or 0, 1)} kN"
        elif calc_type == "viga_fisuracion":
            r = out.get("result") or {}
            s["w_k"], s["w_max"] = r.get("w_k"), r.get("w_max")
            s["texto"] = (f"w_k = {fmt(r['w_k'], 3)} mm ≤ w_max = {fmt(r.get('w_max') or 0, 2)} mm"
                          if r.get("w_k") is not None else "Sección no fisurada" if r.get("cracked") is False else "—")
        elif calc_type == "viga_flecha":
            c = (out.get("result") or {}).get("calc") or {}
            s["flecha_total"], s["limite_total"] = c.get("delta_total"), c.get("limit_total")
            s["flecha_activa"], s["limite_activa"] = c.get("delta_deferred"), c.get("limit_deferred")
            s["texto"] = (f"δ_tot = {fmt(c['delta_total'], 1)} mm (lím. {fmt(c['limit_total'], 1)}); "
                          f"δ_act = {fmt(c['delta_deferred'], 1)} mm (lím. {fmt(c['limit_deferred'], 1)})"
                          if c.get("delta_total") is not None else "—")
        elif calc_type in ("losa_flexion", "losa_flexion_neg"):
            r = out.get("result") or {}
            s["m_Ed"] = request["m_Ed_kNm"]
            s["armado"] = f"Ø{fmt(r['phi'], 0)} c/{fmt(r['s'], 0)} mm" if r.get("phi") and r.get("s") else None
            s["As_nec"], s["As"] = r.get("As_req"), r.get("As")
            sec = r.get("secondary") or {}
            s["reparto"] = f"Ø{fmt(sec['diameter'], 0)} c/{fmt(sec['spacing'], 0)} mm" if sec.get("spacing") else None
            s["texto"] = f"{s['armado'] or '—'}; reparto {s['reparto'] or '—'}"
        elif calc_type == "pilar":
            r = out.get("result") or {}
            s["N_Ed"] = request["N_Ed_kN"]
            s["M_Ed"] = r["MEd_crit"] / 1e6 if r.get("MEd_crit") is not None else None
            s["esbeltez"] = r.get("lambda")
            s["armado"] = _layers_text(request.get("layers") or [])
            s["texto"] = f"N_Ed = {fmt(s['N_Ed'], 1)} kN; M_Ed = {fmt(s['M_Ed'] or 0, 1)} kN·m; λ = {fmt(s['esbeltez'] or 0, 1)}"
        elif calc_type == "zapata_terreno":
            r = out.get("result") or {}
            s["sigma"], s["sigma_adm"] = r.get("sigma"), r.get("sigma_adm")
            s["texto"] = f"σ = {fmt(r['sigma'], 1)} kPa (σ_adm = {fmt(r['sigma_adm'], 1)} kPa)"
    except (KeyError, TypeError, ValueError):
        s["texto"] = "—"
    return s
