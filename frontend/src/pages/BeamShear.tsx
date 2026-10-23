import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, downloadBlob } from "../api/client";
import { LayersEditor } from "../components/LayersEditor";
import { SectionDrawing } from "../components/SectionDrawing";
import { ChecksTable, TracePanel } from "../components/TracePanel";
import { ErrorBox, NumberField, SelectField, fmt } from "../components/ui";
import { useAppState } from "../state/AppState";
import type { Geometry, ShearRequest, ShearResult } from "../types";

function cleanShear(x: ShearRequest, overrides: Record<string, unknown>): ShearRequest {
  const shape =
    x.shape.kind === "rectangular"
      ? { kind: "rectangular" as const, b: x.shape.b, h: x.shape.h }
      : { kind: "T" as const, bf: x.shape.bf, hf: x.shape.hf, bw: x.shape.bw, h: x.shape.h };
  return { ...x, shape, stirrup_spacing: x.mode === "check" ? x.stirrup_spacing : null, parameter_overrides: overrides };
}

function Metric({ label, value, unit }: { label: string; value: string; unit?: string }) {
  return (
    <div className="rounded-md bg-slate-50 p-2.5">
      <div className="text-[11px] text-slate-500">{label}</div>
      <div className="font-mono text-base font-semibold text-ink">
        {value} <span className="text-xs font-normal text-slate-500">{unit}</span>
      </div>
    </div>
  );
}

export default function BeamShear() {
  const { shear, setShear, beam, overrides, activeProject } = useAppState();
  const [catalog, setCatalog] = useState<{ concrete_classes: string[]; steel_grades: string[] }>({
    concrete_classes: ["C25/30"],
    steel_grades: ["B500S"],
  });
  const [result, setResult] = useState<ShearResult | null>(null);
  const [sent, setSent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<Geometry | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);

  useEffect(() => {
    api.catalog().then(setCatalog).catch(() => undefined);
  }, []);
  const req = useMemo(() => cleanShear(shear, overrides), [shear, overrides]);
  const stale = result !== null && sent !== JSON.stringify(req);
  const update = (patch: Partial<ShearRequest>) => setShear({ ...shear, ...patch });
  const updShape = (patch: Partial<ShearRequest["shape"]>) => setShear({ ...shear, shape: { ...shear.shape, ...patch } });

  useEffect(() => {
    const t = setTimeout(() => {
      api
        .sectionProperties({ shape: req.shape, cover: req.cover, stirrup_diameter: req.stirrup_diameter, dg: req.dg, layers: req.layers, parameter_overrides: overrides })
        .then((g) => {
          setPreview(g);
          setPreviewError(null);
        })
        .catch((e) => {
          setPreview(null);
          setPreviewError(e.message);
        });
    }, 250);
    return () => clearTimeout(t);
  }, [req, overrides]);

  function copyFromFlexure() {
    setShear({
      ...shear,
      element_name: beam.element_name,
      shape: { ...beam.shape },
      cover: beam.cover,
      stirrup_diameter: beam.stirrup_diameter > 0 ? beam.stirrup_diameter : shear.stirrup_diameter,
      dg: beam.dg,
      concrete_class: beam.concrete_class,
      situation: beam.situation,
      layers: beam.layers.map((l) => ({ ...l })),
      tension_face: beam.M_Ed_kNm >= 0 ? "inferior" : "superior",
      stirrup_spacing: beam.stirrup_spacing ?? shear.stirrup_spacing,
    });
  }

  async function calculate() {
    setBusy(true);
    setError(null);
    setMsg(null);
    try {
      const r = await api.shear(req);
      setResult(r);
      setSent(JSON.stringify(req));
    } catch (e) {
      setResult(null);
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function pdf() {
    setError(null);
    try {
      const blob = await api.shearReport({ project_name: activeProject?.name ?? "Sin proyecto", author: "", request: req });
      downloadBlob(blob, `informe_cortante_${req.element_name.replace(/[^A-Za-z0-9_-]+/g, "_")}.pdf`);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function saveToProject() {
    if (!activeProject) return;
    setError(null);
    try {
      const p = await api.project(activeProject.id);
      const R = result && !stale ? result.result : null;
      const summary =
        result && !stale && R
          ? {
              ok: result.ok,
              summary:
                result.mode === "design" && R.proposal
                  ? `cercos φ${R.proposal.diameter} ${R.proposal.legs}r c/${R.proposal.spacing} mm`
                  : `V_Rd,s = ${fmt((R.VRd_s ?? 0) / 1000, 1)} kN; V_Rd,max = ${fmt((R.VRd_max ?? 0) / 1000, 1)} kN`,
            }
          : null;
      const name = req.element_name;
      const idx = p.elements.findIndex((e) => e.name === name && e.type === "viga_cortante");
      const el = { id: idx >= 0 ? p.elements[idx].id : undefined, type: "viga_cortante" as const, name, input: req, result: summary };
      const elements = idx >= 0 ? p.elements.map((e, i) => (i === idx ? el : e)) : [...p.elements, el];
      await api.updateProject(p.id, { name: p.name, description: p.description, parameter_overrides: overrides, elements });
      setMsg(`Cortante de «${name}» guardado en el proyecto «${p.name}».`);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const R = result?.result;
  const geom = result && !stale ? result.result.geometry : preview;

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(320px,400px)_1fr]">
      <div className="space-y-4">
        <section className="card space-y-3">
          <div className="grid grid-cols-2 gap-2">
            <label className="col-span-2 block">
              <span className="label">Elemento</span>
              <input className="input" value={shear.element_name} maxLength={120} onChange={(e) => update({ element_name: e.target.value })} />
            </label>
            <button className={shear.mode === "design" ? "btn-primary" : "btn-secondary"} onClick={() => update({ mode: "design" })}>
              Dimensionar cercos
            </button>
            <button className={shear.mode === "check" ? "btn-primary" : "btn-secondary"} onClick={() => update({ mode: "check" })}>
              Comprobar cercos
            </button>
          </div>
          <button className="btn-secondary w-full text-xs" onClick={copyFromFlexure}>
            Copiar geometría, materiales y armado longitudinal de «Flexión»
          </button>
        </section>

        <section className="card space-y-3">
          <h2 className="h2">Geometría</h2>
          <SelectField
            label="Tipo de sección"
            value={shear.shape.kind}
            options={[
              { value: "rectangular", label: "Rectangular" },
              { value: "T", label: "En T (ala superior)" },
            ]}
            onChange={(v) => updShape({ kind: v })}
          />
          <div className="grid grid-cols-2 gap-2">
            {shear.shape.kind === "rectangular" ? (
              <NumberField label="Ancho b" unit="mm" value={shear.shape.b} onChange={(v) => updShape({ b: v })} />
            ) : (
              <>
                <NumberField label="b_f" unit="mm" value={shear.shape.bf} onChange={(v) => updShape({ bf: v })} />
                <NumberField label="h_f" unit="mm" value={shear.shape.hf} onChange={(v) => updShape({ hf: v })} />
                <NumberField label="b_w" unit="mm" value={shear.shape.bw} onChange={(v) => updShape({ bw: v })} />
              </>
            )}
            <NumberField label="Canto h" unit="mm" value={shear.shape.h} onChange={(v) => updShape({ h: v })} />
            <NumberField label="Recubrimiento c_nom" unit="mm" value={shear.cover} onChange={(v) => update({ cover: v })} hint="Hasta el cerco" />
            <NumberField label="Tamaño máx. árido d_g" unit="mm" value={shear.dg} onChange={(v) => update({ dg: v })} />
          </div>
        </section>

        <section className="card space-y-3">
          <h2 className="h2">Materiales</h2>
          <div className="grid grid-cols-2 gap-2">
            <SelectField label="Hormigón" value={shear.concrete_class} options={catalog.concrete_classes.map((c) => ({ value: c, label: c }))} onChange={(v) => update({ concrete_class: v })} />
            <SelectField label="Acero de cercos" value={shear.stirrup_grade} options={catalog.steel_grades.map((c) => ({ value: c, label: c }))} onChange={(v) => update({ stirrup_grade: v })} />
            <SelectField
              label="Situación de proyecto"
              value={shear.situation}
              options={[
                { value: "persistente" as const, label: "Persistente" },
                { value: "transitoria" as const, label: "Transitoria" },
                { value: "accidental" as const, label: "Accidental" },
              ]}
              onChange={(v) => update({ situation: v })}
            />
          </div>
        </section>

        <section className="card space-y-3">
          <h2 className="h2">Armadura longitudinal</h2>
          <SelectField
            label="Cara traccionada (A_sl y d)"
            value={shear.tension_face}
            options={[
              { value: "inferior" as const, label: "Inferior (momento positivo)" },
              { value: "superior" as const, label: "Superior (momento negativo)" },
            ]}
            onChange={(v) => update({ tension_face: v })}
          />
          <LayersEditor layers={shear.layers} onChange={(layers) => update({ layers })} />
          <p className="text-[11px] text-slate-500">A_sl debe prolongarse ≥ l_bd + d más allá de la sección (figura A19.6.3).</p>
        </section>

        <section className="card space-y-3">
          <h2 className="h2">Solicitaciones</h2>
          <div className="grid grid-cols-2 gap-2">
            <NumberField label="Cortante V_Ed" unit="kN" value={shear.V_Ed_kN} min={0} onChange={(v) => update({ V_Ed_kN: v })} />
            <NumberField label="Axil N_Ed" unit="kN" value={shear.N_Ed_kN} onChange={(v) => update({ N_Ed_kN: v })} hint="Compresión positiva" />
          </div>
        </section>

        <section className="card space-y-3">
          <h2 className="h2">Cercos</h2>
          <div className="grid grid-cols-2 gap-2">
            <SelectField label="φ cerco [mm]" value={shear.stirrup_diameter} options={[6, 8, 10, 12, 14, 16].map((d) => ({ value: d, label: String(d) }))} onChange={(v) => update({ stirrup_diameter: v })} />
            <SelectField label="N.º de ramas" value={shear.stirrup_legs} options={[2, 3, 4, 6].map((d) => ({ value: d, label: String(d) }))} onChange={(v) => update({ stirrup_legs: v })} />
            <NumberField label="Inclinación α" unit="°" value={shear.alpha_deg} min={45} max={90} onChange={(v) => update({ alpha_deg: v })} hint="45° ≤ α ≤ 90° (9.2.2(1))" />
            {shear.mode === "check" && (
              <NumberField label="Separación s" unit="mm" value={shear.stirrup_spacing ?? undefined} onChange={(v) => update({ stirrup_spacing: Number.isFinite(v) ? v : null })} />
            )}
          </div>
          <label className="flex items-start gap-2 text-xs text-slate-700">
            <input type="checkbox" className="mt-0.5" checked={shear.cot_theta !== null} onChange={(e) => update({ cot_theta: e.target.checked ? 2 : null })} />
            <span>Fijar la inclinación de las bielas (si no, se elige automáticamente dentro de 0,5 ≤ cot θ ≤ 2, expresión (6.7)).</span>
          </label>
          {shear.cot_theta !== null && (
            <NumberField label="cot θ" value={shear.cot_theta} step={0.05} min={0.5} max={2} onChange={(v) => update({ cot_theta: v })} />
          )}
          <label className="flex items-start gap-2 text-xs text-slate-700">
            <input type="checkbox" className="mt-0.5" checked={shear.nu1_simplified} onChange={(e) => update({ nu1_simplified: e.target.checked })} />
            <span>Usar ν₁ según (6.10) con f_ywd = 0,8·f_ywk (nota de 6.2.3(3)).</span>
          </label>
        </section>

        <div className="flex flex-wrap gap-2">
          <button className="btn-primary flex-1" onClick={calculate} disabled={busy}>
            {busy ? "Calculando…" : shear.mode === "design" ? "Dimensionar cercos" : "Comprobar cortante"}
          </button>
          <button className="btn-secondary" onClick={pdf} disabled={busy}>
            Informe PDF
          </button>
          {activeProject && (
            <button className="btn-secondary" onClick={saveToProject}>
              Guardar en proyecto
            </button>
          )}
        </div>
        {!activeProject && (
          <p className="text-[11px] text-slate-500">
            Para guardar el elemento, abra o cree un proyecto en{" "}
            <Link to="/proyectos/calculos" className="text-brand underline">
              Proyectos
            </Link>
            .
          </p>
        )}
        <ErrorBox error={error} />
        {msg && <div className="rounded-md border border-emerald-200 bg-emerald-50 p-2 text-sm text-emerald-800">{msg}</div>}
      </div>

      <div className="min-w-0 space-y-4">
        <section className="card">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="h2">Sección transversal</h2>
            {geom && (
              <span className="text-xs text-slate-500">
                A_sl = {fmt(shear.tension_face === "inferior" ? geom.As_inferior : geom.As_superior, 0)} mm² · d ={" "}
                {fmt(shear.tension_face === "inferior" ? geom.d_inferior : geom.d_superior, 1)} mm
              </span>
            )}
          </div>
          {geom ? (
            <div className="flex justify-center">
              <SectionDrawing shape={geom.shape} bars={geom.bars} cover={shear.cover} />
            </div>
          ) : (
            <ErrorBox error={previewError ?? "Introduzca una geometría válida."} />
          )}
        </section>
        {result && R && (
          <>
            {stale && (
              <div className="rounded-md border border-amber-200 bg-amber-50 p-2 text-sm text-amber-900">
                Los datos han cambiado desde el último cálculo: los resultados mostrados están desactualizados.
              </div>
            )}
            <section className="card">
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <h2 className="h2">Resultado</h2>
                {result.ok === true && <span className="rounded bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-800">Todas las verificaciones se cumplen</span>}
                {result.ok === false && <span className="rounded bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-800">Hay verificaciones no superadas</span>}
                {result.ok === null && <span className="rounded bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-800">Verificación incompleta</span>}
              </div>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                <Metric label="V_Ed" value={fmt(result.request.V_Ed_kN, 1)} unit="kN" />
                <Metric label="V_Rd,c (sin armadura)" value={fmt(R.VRdc.VRdc / 1000, 1)} unit="kN" />
                {R.cot_theta !== undefined && <Metric label="cot θ (θ)" value={`${fmt(R.cot_theta, 3)} (${fmt(R.theta_deg, 1)}°)`} />}
                {R.VRd_max !== undefined && <Metric label="V_Rd,max (bielas)" value={fmt(R.VRd_max / 1000, 1)} unit="kN" />}
                {R.VRd_s !== undefined && <Metric label="V_Rd,s (cercos)" value={fmt(R.VRd_s / 1000, 1)} unit="kN" />}
                {R.Asw_s_design !== undefined && <Metric label="(A_sw/s) necesaria" value={fmt(R.Asw_s_design * 1000, 0)} unit="mm²/m" />}
                {R.Asw_s_provided !== undefined && <Metric label="(A_sw/s) dispuesta" value={fmt(R.Asw_s_provided * 1000, 0)} unit="mm²/m" />}
                <Metric label="s_l,max" value={fmt(R.s_l_max, 0)} unit="mm" />
                {R.Delta_Ftd !== undefined && <Metric label="ΔF_td (6.18)" value={fmt(R.Delta_Ftd / 1000, 1)} unit="kN" />}
              </div>
              {result.mode === "design" && R.proposal && (
                <div className="mt-4">
                  <h3 className="text-sm font-semibold">Cercos propuestos</h3>
                  <p className="mt-1 font-mono text-sm font-semibold">
                    φ{R.proposal.diameter} de {R.proposal.legs} ramas c/ {fmt(R.proposal.spacing, 0)} mm
                  </p>
                  {R.alternatives && R.alternatives.length > 0 && (
                    <div className="mt-2 overflow-x-auto">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="border-b text-left text-slate-500">
                            <th className="py-1 font-medium">Alternativa</th>
                            <th className="py-1 font-medium">A_sw/s [mm²/m]</th>
                            <th className="py-1 font-medium">s_t entre ramas [mm]</th>
                            <th />
                          </tr>
                        </thead>
                        <tbody>
                          {R.alternatives.map((a, i) => (
                            <tr key={i} className="border-b border-slate-100">
                              <td className="py-1 font-mono">
                                φ{a.diameter} · {a.legs} ramas · c/{a.spacing}
                              </td>
                              <td className="py-1">{fmt(a.Asw_s_mm2_m, 0)}</td>
                              <td className="py-1">{fmt(a.s_t, 0)}</td>
                              <td className="py-1 text-right">
                                <button
                                  className="text-brand hover:underline"
                                  onClick={() => update({ mode: "check", stirrup_diameter: a.diameter, stirrup_legs: a.legs, stirrup_spacing: a.spacing })}
                                >
                                  Comprobar esta
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}
            </section>
            <section className="card">
              <h2 className="h2 mb-2">Verificaciones</h2>
              <ChecksTable checks={result.trace.checks} />
            </section>
            <TracePanel trace={result.trace} />
          </>
        )}
      </div>
    </div>
  );
}
