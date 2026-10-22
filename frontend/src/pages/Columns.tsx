import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, downloadBlob } from "../api/client";
import { LayersEditor } from "../components/LayersEditor";
import { SectionDrawing } from "../components/SectionDrawing";
import { ChecksTable, TracePanel } from "../components/TracePanel";
import { ErrorBox, NumberField, PageHeader, SelectField, StatusBadge, fmt } from "../components/ui";
import { useAppState } from "../state/AppState";
import type { ColumnRequest, ColumnResult, Geometry } from "../types";

const BETAS = [
  { value: 2.0, label: "2,0 — ménsula (empotrado-libre)" },
  { value: 1.0, label: "1,0 — biarticulado" },
  { value: 0.7, label: "0,7 — empotrado-articulado" },
  { value: 0.5, label: "0,5 — biempotrado" },
];

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

type CreepMode = "phi_ef" | "phi_inf" | "unknown";

export default function Columns() {
  const { column, setColumn, overrides, activeProject } = useAppState();
  const [catalog, setCatalog] = useState<{ concrete_classes: string[]; steel_grades: string[] }>({
    concrete_classes: ["C25/30"],
    steel_grades: ["B500S"],
  });
  const [result, setResult] = useState<ColumnResult | null>(null);
  const [sent, setSent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<Geometry | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const creepMode: CreepMode = column.phi_ef !== null ? "phi_ef" : column.phi_inf !== null && column.m0eqp_ratio !== null ? "phi_inf" : "unknown";

  useEffect(() => {
    api.catalog().then(setCatalog).catch(() => undefined);
  }, []);
  const req = useMemo<ColumnRequest>(
    () => ({
      ...column,
      beta: column.l0_mode === "beta" ? column.beta : null,
      k1: column.l0_mode === "k" ? column.k1 : null,
      k2: column.l0_mode === "k" ? column.k2 : null,
      M0_span_kNm: column.transverse_load ? column.M0_span_kNm : null,
      parameter_overrides: overrides,
    }),
    [column, overrides],
  );
  const stale = result !== null && sent !== JSON.stringify(req);
  const update = (patch: Partial<ColumnRequest>) => setColumn({ ...column, ...patch });

  useEffect(() => {
    const t = setTimeout(() => {
      api
        .sectionProperties({ shape: { kind: "rectangular", b: req.b, h: req.h }, cover: req.cover, stirrup_diameter: req.stirrup_diameter, dg: req.dg, layers: req.layers, parameter_overrides: overrides })
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

  async function calculate() {
    setBusy(true);
    setError(null);
    setMsg(null);
    try {
      const r = await api.column(req);
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
      const blob = await api.columnReport({ project_name: activeProject?.name ?? "Sin proyecto", author: "", request: req });
      downloadBlob(blob, `informe_pilar_${req.element_name.replace(/[^A-Za-z0-9_-]+/g, "_")}.pdf`);
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
      const summary = R
        ? { ok: result!.ok, summary: `λ = ${fmt(R.lambda, 1)}; M_Ed = ${fmt(R.MEd_crit / 1e6, 1)} kN·m; M_Rd = ${fmt((R.MRd ?? 0) / 1e6, 1)} kN·m` }
        : null;
      const name = req.element_name;
      const idx = p.elements.findIndex((e) => e.name === name && e.type === "pilar");
      const el = { id: idx >= 0 ? p.elements[idx].id : undefined, type: "pilar" as const, name, input: req, result: summary };
      const elements = idx >= 0 ? p.elements.map((e, i) => (i === idx ? el : e)) : [...p.elements, el];
      await api.updateProject(p.id, { name: p.name, description: p.description, parameter_overrides: overrides, elements });
      setMsg(`Pilar «${name}» guardado en el proyecto «${p.name}».`);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const R = result?.result;
  const geom = result && !stale ? result.result.geometry : preview;

  return (
    <>
      <PageHeader
        title="Pilares — flexocompresión y segundo orden"
        subtitle="Pilar aislado de sección rectangular en flexión compuesta recta: esbeltez (5.8.3), imperfecciones (5.2), curvatura nominal (5.8.8), excentricidad mínima (6.1(4)), diagrama de interacción N–M (6.1) y disposiciones (9.5)."
      >
        <StatusBadge status="pendiente_validacion" />
      </PageHeader>
      <div className="grid gap-4 lg:grid-cols-[minmax(320px,400px)_1fr]">
        <div className="space-y-4">
          <section className="card space-y-3">
            <label className="block">
              <span className="label">Elemento</span>
              <input className="input" value={column.element_name} maxLength={120} onChange={(e) => update({ element_name: e.target.value })} />
            </label>
            <h2 className="h2">Sección</h2>
            <div className="grid grid-cols-2 gap-2">
              <NumberField label="b (perpendicular a la flexión)" unit="mm" value={column.b} onChange={(v) => update({ b: v })} />
              <NumberField label="h (en el plano de flexión)" unit="mm" value={column.h} onChange={(v) => update({ h: v })} />
              <NumberField label="Recubrimiento c_nom" unit="mm" value={column.cover} onChange={(v) => update({ cover: v })} />
              <SelectField label="φ cerco [mm]" value={column.stirrup_diameter} options={[6, 8, 10, 12].map((d) => ({ value: d, label: String(d) }))} onChange={(v) => update({ stirrup_diameter: v })} />
              <NumberField label="Separación de cercos" unit="mm" value={column.stirrup_spacing ?? undefined} onChange={(v) => update({ stirrup_spacing: Number.isFinite(v) ? v : null })} />
              <NumberField label="Tamaño máx. árido" unit="mm" value={column.dg} onChange={(v) => update({ dg: v })} />
            </div>
            <LayersEditor layers={column.layers} onChange={(layers) => update({ layers })} />
            <label className="flex items-start gap-2 text-xs text-slate-700">
              <input type="checkbox" className="mt-0.5" checked={column.intermediate_bars_tied} onChange={(e) => update({ intermediate_bars_tied: e.target.checked })} />
              <span>Las barras intermedias están sujetas con horquillas o cercos interiores (9.5.3(6)).</span>
            </label>
          </section>

          <section className="card space-y-3">
            <h2 className="h2">Materiales</h2>
            <div className="grid grid-cols-2 gap-2">
              <SelectField label="Hormigón" value={column.concrete_class} options={catalog.concrete_classes.map((c) => ({ value: c, label: c }))} onChange={(v) => update({ concrete_class: v })} />
              <SelectField label="Acero" value={column.steel_grade} options={catalog.steel_grades.map((c) => ({ value: c, label: c }))} onChange={(v) => update({ steel_grade: v })} />
              <SelectField
                label="Situación"
                value={column.situation}
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
            <h2 className="h2">Solicitaciones de primer orden</h2>
            <div className="grid grid-cols-3 gap-2">
              <NumberField label="N_Ed" unit="kN" value={column.N_Ed_kN} onChange={(v) => update({ N_Ed_kN: v })} hint="Compresión +" />
              <NumberField label="M01" unit="kN·m" value={column.M01_kNm} onChange={(v) => update({ M01_kNm: v })} />
              <NumberField label="M02" unit="kN·m" value={column.M02_kNm} onChange={(v) => update({ M02_kNm: v })} hint="|M02| ≥ |M01|" />
            </div>
            <p className="text-[11px] text-slate-500">M01 y M02 con el mismo signo si traccionan la misma cara (curvatura simple).</p>
            <label className="flex items-start gap-2 text-xs text-slate-700">
              <input type="checkbox" className="mt-0.5" checked={column.transverse_load} onChange={(e) => update({ transverse_load: e.target.checked, M0_span_kNm: e.target.checked ? column.M0_span_kNm ?? 0 : null })} />
              <span>Hay cargas transversales entre extremos (r_m = 1).</span>
            </label>
            {column.transverse_load && (
              <NumberField label="Momento máximo de primer orden en el vano" unit="kN·m" value={column.M0_span_kNm ?? undefined} onChange={(v) => update({ M0_span_kNm: v })} />
            )}
          </section>

          <section className="card space-y-3">
            <h2 className="h2">Longitud efectiva</h2>
            <NumberField label="Longitud libre l" unit="mm" value={column.length} onChange={(v) => update({ length: v })} />
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={column.braced} onChange={(e) => update({ braced: e.target.checked, ei_simplified: e.target.checked ? column.ei_simplified : false })} />
              Pilar arriostrado (sistema arriostrado)
            </label>
            <SelectField
              label="Definición de l₀"
              value={column.l0_mode}
              options={[
                { value: "beta" as const, label: "l₀ = β·l (figura A19.5.7)" },
                { value: "k" as const, label: "Flexibilidades k1, k2 (5.15 / 5.16)" },
              ]}
              onChange={(v) => update({ l0_mode: v })}
            />
            {column.l0_mode === "beta" ? (
              <SelectField label="β" value={column.beta ?? 1} options={BETAS} onChange={(v) => update({ beta: v })} />
            ) : (
              <div className="grid grid-cols-2 gap-2">
                <NumberField label="k1" value={column.k1 ?? undefined} step={0.05} onChange={(v) => update({ k1: v })} hint="0 = empotramiento; mín. recomendado 0,1" />
                <NumberField label="k2" value={column.k2 ?? undefined} step={0.05} onChange={(v) => update({ k2: v })} />
              </div>
            )}
            <label className="flex items-start gap-2 text-xs text-slate-700">
              <input type="checkbox" className="mt-0.5" disabled={!column.braced} checked={column.ei_simplified} onChange={(e) => update({ ei_simplified: e.target.checked })} />
              <span>Imperfección simplificada e_i = l₀/400 (solo arriostrados, 5.2(9)).</span>
            </label>
          </section>

          <section className="card space-y-3">
            <h2 className="h2">Fluencia</h2>
            <SelectField
              label="Coeficiente de fluencia eficaz"
              value={creepMode}
              options={[
                { value: "phi_inf" as CreepMode, label: "Calcular φ_ef = φ(∞,t₀)·M0Eqp/M0Ed (5.19)" },
                { value: "phi_ef" as CreepMode, label: "Introducir φ_ef" },
                { value: "unknown" as CreepMode, label: "Desconocido (A = 0,7; no permite el segundo orden)" },
              ]}
              onChange={(v) =>
                update(
                  v === "phi_ef"
                    ? { phi_ef: column.phi_ef ?? 1.0 }
                    : v === "phi_inf"
                      ? { phi_ef: null, phi_inf: column.phi_inf ?? 2.0, m0eqp_ratio: column.m0eqp_ratio ?? 0.6 }
                      : { phi_ef: null, phi_inf: null, m0eqp_ratio: null },
                )
              }
            />
            {creepMode === "phi_ef" && <NumberField label="φ_ef" value={column.phi_ef ?? undefined} step={0.1} onChange={(v) => update({ phi_ef: v })} />}
            {creepMode === "phi_inf" && (
              <div className="grid grid-cols-2 gap-2">
                <NumberField label="φ(∞,t₀)" value={column.phi_inf ?? undefined} step={0.1} onChange={(v) => update({ phi_inf: v })} hint="Apartado 3.1.4" />
                <NumberField label="M0Eqp/M0Ed" value={column.m0eqp_ratio ?? undefined} step={0.05} onChange={(v) => update({ m0eqp_ratio: v })} />
              </div>
            )}
          </section>

          <div className="flex flex-wrap gap-2">
            <button className="btn-primary flex-1" onClick={calculate} disabled={busy}>
              {busy ? "Calculando…" : "Comprobar pilar"}
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
              Para guardar el pilar, abra o cree un proyecto en{" "}
              <Link to="/proyectos" className="text-brand underline">
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
            <h2 className="h2 mb-2">Sección transversal</h2>
            {geom ? (
              <div className="flex justify-center">
                <SectionDrawing shape={geom.shape} bars={geom.bars} cover={column.cover} />
              </div>
            ) : (
              <ErrorBox error={previewError ?? "Introduzca una geometría válida."} />
            )}
            <p className="mt-1 text-center text-[11px] text-slate-500">La flexión estudiada actúa en el plano de la dimensión h (vertical en el dibujo).</p>
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
                  {result.ok === null && <span className="rounded bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-800">Verificación incompleta (faltan datos)</span>}
                </div>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                  <Metric label="l₀" value={fmt(R.l0, 0)} unit="mm" />
                  <Metric label="λ / λ_lim" value={`${fmt(R.lambda, 1)} / ${fmt(R.lambda_lim, 1)}`} />
                  <Metric label="Segundo orden" value={R.second_order ? "Sí" : "No"} />
                  <Metric label="e_i / e₀" value={`${fmt(R.e_i, 1)} / ${fmt(R.e_0, 1)}`} unit="mm" />
                  <Metric label="M_0Ed" value={fmt(R.M0Ed / 1e6, 1)} unit="kN·m" />
                  <Metric label="M₂" value={fmt(R.M2 / 1e6, 1)} unit="kN·m" />
                  <Metric label="M_Ed (crítica)" value={fmt(R.MEd_crit / 1e6, 1)} unit="kN·m" />
                  <Metric label="M_Rd(N_Ed)" value={R.MRd !== undefined ? fmt(R.MRd / 1e6, 1) : "—"} unit="kN·m" />
                </div>
              </section>
              <section className="card">
                <h2 className="h2 mb-2">Diagrama de interacción N–M</h2>
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart margin={{ top: 5, right: 16, bottom: 20, left: 8 }}>
                      <CartesianGrid stroke="#e2e8f0" />
                      <XAxis type="number" dataKey="M_kNm" fontSize={11} tickFormatter={(v) => fmt(v, 0)} label={{ value: "M [kN·m]", position: "insideBottom", offset: -10, fontSize: 11 }} />
                      <YAxis type="number" dataKey="N_kN" fontSize={11} tickFormatter={(v) => fmt(v, 0)} label={{ value: "N [kN] (compresión +)", angle: -90, position: "insideLeft", fontSize: 11 }} />
                      <Tooltip formatter={(v: number, name: string) => [fmt(v, 1), name]} />
                      <Legend verticalAlign="top" height={24} wrapperStyle={{ fontSize: 11 }} />
                      <ReferenceLine x={0} stroke="#94a3b8" />
                      <ReferenceLine y={0} stroke="#94a3b8" />
                      <Line data={[...R.diagram, R.diagram[0]]} dataKey="N_kN" name="Envolvente resistente" stroke="#1f3a5f" dot={false} strokeWidth={2} isAnimationActive={false} />
                      <Line data={R.design_points} dataKey="N_kN" name="Solicitaciones de cálculo" stroke="transparent" dot={{ r: 5, fill: "#b03a2e", stroke: "#b03a2e" }} isAnimationActive={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
                <p className="mt-1 text-[11px] text-slate-500">
                  Envolvente por el método general (6.1) con pivotes A, B y C. Puntos rojos: (N_Ed, M_Ed) en la sección crítica{R.design_points.length > 1 ? " y en el extremo" : ""}.
                </p>
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
    </>
  );
}
