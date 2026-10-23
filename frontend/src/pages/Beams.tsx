import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import BeamShear from "./BeamShear";
import { api, downloadBlob } from "../api/client";
import { LayersEditor, DIAMETERS } from "../components/LayersEditor";
import { SectionDrawing } from "../components/SectionDrawing";
import { ChecksTable, TracePanel } from "../components/TracePanel";
import { ErrorBox, NumberField, PageHeader, SelectField, StatusBadge, fmt } from "../components/ui";
import { useAppState } from "../state/AppState";
import type { FlexureRequest, FlexureResult, Geometry } from "../types";

const SITUATIONS = [
  { value: "persistente" as const, label: "Persistente" },
  { value: "transitoria" as const, label: "Transitoria" },
  { value: "accidental" as const, label: "Accidental" },
];

function cleanRequest(beam: FlexureRequest, overrides: Record<string, unknown>): FlexureRequest {
  const shape =
    beam.shape.kind === "rectangular"
      ? { kind: "rectangular" as const, b: beam.shape.b, h: beam.shape.h }
      : { kind: "T" as const, bf: beam.shape.bf, hf: beam.shape.hf, bw: beam.shape.bw, h: beam.shape.h };
  return { ...beam, shape, parameter_overrides: overrides };
}

export default function Beams() {
  const [params, setParams] = useSearchParams();
  const calc = params.get("calc") === "cortante" ? "cortante" : "flexion";
  const tabs = [
    { id: "flexion", label: "Flexión simple" },
    { id: "cortante", label: "Cortante" },
  ];
  return (
    <>
      <PageHeader
        title={calc === "flexion" ? "Vigas — flexión simple ELU" : "Vigas — cortante ELU"}
        subtitle={
          calc === "flexion"
            ? "Dimensionado de la armadura longitudinal de secciones rectangulares y comprobación de secciones rectangulares o en T con armadura existente (Anejo 19, 6.1; 3.1.7; 9.2.1.1; 8.2)."
            : "Resistencia sin armadura de cortante, dimensionado y comprobación de cercos con modelo de celosía de ángulo variable (Anejo 19, 6.2; 9.2.2)."
        }
      >
        <StatusBadge status="pendiente_validacion" />
      </PageHeader>
      <div className="mb-4 flex gap-1 border-b border-slate-200">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setParams(t.id === "flexion" ? {} : { calc: t.id })}
            className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium ${calc === t.id ? "border-brand text-brand" : "border-transparent text-slate-500 hover:text-ink"}`}
          >
            {t.label}
          </button>
        ))}
      </div>
      {calc === "flexion" ? <BeamFlexure /> : <BeamShear />}
    </>
  );
}

function BeamFlexure() {
  const { beam, setBeam, overrides, activeProject } = useAppState();
  const [catalog, setCatalog] = useState<{ concrete_classes: string[]; steel_grades: string[] }>({
    concrete_classes: ["C25/30"],
    steel_grades: ["B500S"],
  });
  const [result, setResult] = useState<FlexureResult | null>(null);
  const [sentReq, setSentReq] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<Geometry | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const resultRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.catalog().then(setCatalog).catch(() => undefined);
  }, []);

  const req = useMemo(() => cleanRequest(beam, overrides), [beam, overrides]);
  const stale = result !== null && sentReq !== JSON.stringify(req);
  const update = (patch: Partial<FlexureRequest>) => setBeam({ ...beam, ...patch });
  const updShape = (patch: Partial<FlexureRequest["shape"]>) => setBeam({ ...beam, shape: { ...beam.shape, ...patch } });

  // Vista previa de la sección (posiciones de barras calculadas en el backend)
  useEffect(() => {
    const t = setTimeout(() => {
      const layers = beam.mode === "check" ? req.layers : [];
      api
        .sectionProperties({ shape: req.shape, cover: req.cover, stirrup_diameter: req.stirrup_diameter, dg: req.dg, layers, parameter_overrides: overrides })
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
  }, [req, beam.mode, overrides]);

  async function calculate() {
    setBusy(true);
    setError(null);
    setMsg(null);
    try {
      const r = await api.flexure(req);
      setResult(r);
      setSentReq(JSON.stringify(req));
      setTimeout(() => resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
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
      const blob = await api.flexureReport({ project_name: activeProject?.name ?? "Sin proyecto", author: "", request: req });
      downloadBlob(blob, `informe_${req.element_name.replace(/[^A-Za-z0-9_-]+/g, "_")}.pdf`);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function saveToProject() {
    if (!activeProject) return;
    setError(null);
    try {
      const p = await api.project(activeProject.id);
      const summary = result && !stale ? { ok: result.ok, summary: summaryText(result) } : null;
      const idx = p.elements.findIndex((e) => e.name === req.element_name && e.type === "viga_flexion");
      const el = { id: idx >= 0 ? p.elements[idx].id : undefined, type: "viga_flexion" as const, name: req.element_name, input: req, result: summary };
      const elements = idx >= 0 ? p.elements.map((e, i) => (i === idx ? el : e)) : [...p.elements, el];
      await api.updateProject(p.id, { name: p.name, description: p.description, parameter_overrides: overrides, elements });
      setMsg(`Elemento «${req.element_name}» guardado en el proyecto «${p.name}».`);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const drawGeom: Geometry | null =
    result && !stale ? (result.mode === "design" ? result.proposal?.geometry ?? preview : result.geometry ?? preview) : preview;

  return (
    <>
      <div className="grid gap-4 lg:grid-cols-[minmax(320px,400px)_1fr]">
        {/* Entrada de datos */}
        <div className="space-y-4">
          <section className="card space-y-3">
            <div className="grid grid-cols-2 gap-2">
              <label className="col-span-2 block">
                <span className="label">Elemento</span>
                <input className="input" value={beam.element_name} maxLength={120} onChange={(e) => update({ element_name: e.target.value })} />
              </label>
              <button
                className={beam.mode === "design" ? "btn-primary" : "btn-secondary"}
                onClick={() => update({ mode: "design", shape: { ...beam.shape, kind: "rectangular" } })}
              >
                Dimensionar
              </button>
              <button className={beam.mode === "check" ? "btn-primary" : "btn-secondary"} onClick={() => update({ mode: "check" })}>
                Comprobar armado
              </button>
            </div>
          </section>

          <section className="card space-y-3">
            <h2 className="h2">Geometría</h2>
            {beam.mode === "check" && (
              <SelectField
                label="Tipo de sección"
                value={beam.shape.kind}
                options={[
                  { value: "rectangular", label: "Rectangular" },
                  { value: "T", label: "En T (ala superior)" },
                ]}
                onChange={(v) => updShape({ kind: v })}
              />
            )}
            {beam.mode === "design" && (
              <p className="text-[11px] text-slate-500">El dimensionado automático está implementado para secciones rectangulares.</p>
            )}
            <div className="grid grid-cols-2 gap-2">
              {beam.shape.kind === "rectangular" ? (
                <NumberField label="Ancho b" unit="mm" value={beam.shape.b} onChange={(v) => updShape({ b: v })} min={1} />
              ) : (
                <>
                  <NumberField label="Ancho eficaz del ala b_f" unit="mm" value={beam.shape.bf} onChange={(v) => updShape({ bf: v })} hint="Según 5.3.2.1 (lo fija el usuario)" />
                  <NumberField label="Espesor del ala h_f" unit="mm" value={beam.shape.hf} onChange={(v) => updShape({ hf: v })} />
                  <NumberField label="Ancho del alma b_w" unit="mm" value={beam.shape.bw} onChange={(v) => updShape({ bw: v })} />
                </>
              )}
              <NumberField label="Canto h" unit="mm" value={beam.shape.h} onChange={(v) => updShape({ h: v })} min={1} />
              <NumberField label="Recubrimiento nominal c_nom" unit="mm" value={beam.cover} onChange={(v) => update({ cover: v })} hint="Hasta el estribo (4.4.1, fijado por el usuario)" />
              <SelectField
                label="φ estribo [mm]"
                value={beam.stirrup_diameter}
                options={[0, 6, 8, 10, 12].map((d) => ({ value: d, label: d === 0 ? "sin estribo" : String(d) }))}
                onChange={(v) => update({ stirrup_diameter: v })}
              />
              <NumberField label="Tamaño máx. árido d_g" unit="mm" value={beam.dg} onChange={(v) => update({ dg: v })} />
              <NumberField
                label="Separación de estribos s_t"
                unit="mm"
                value={beam.stirrup_spacing ?? undefined}
                onChange={(v) => update({ stirrup_spacing: Number.isFinite(v) ? v : null })}
                hint="Para 9.2.1.2(3): s_t ≤ 15·φ de las barras comprimidas"
              />
            </div>
          </section>

          <section className="card space-y-3">
            <h2 className="h2">Materiales</h2>
            <div className="grid grid-cols-2 gap-2">
              <SelectField label="Hormigón" value={beam.concrete_class} options={catalog.concrete_classes.map((c) => ({ value: c, label: c }))} onChange={(v) => update({ concrete_class: v })} />
              <SelectField label="Acero" value={beam.steel_grade} options={catalog.steel_grades.map((c) => ({ value: c, label: c }))} onChange={(v) => update({ steel_grade: v })} />
              <SelectField
                label="Diagrama del acero"
                value={beam.steel_branch}
                options={[
                  { value: "horizontal", label: "Rama horizontal" },
                  { value: "inclinada", label: "Rama inclinada (ε_ud)" },
                ]}
                onChange={(v) => update({ steel_branch: v })}
              />
              <SelectField label="Situación de proyecto" value={beam.situation} options={SITUATIONS} onChange={(v) => update({ situation: v })} />
            </div>
            <p className="text-[11px] text-slate-500">
              Coeficientes y parámetros:{" "}
              <Link className="text-brand underline" to="/normativa">
                configuración normativa
              </Link>
              {Object.keys(overrides).length > 0 && <span className="ml-1 text-sky-700">({Object.keys(overrides).length} modificado(s))</span>}
            </p>
          </section>

          <section className="card space-y-3">
            <h2 className="h2">Solicitación y armado</h2>
            <NumberField label="Momento flector de cálculo M_Ed" unit="kN·m" value={beam.M_Ed_kNm} step={1} onChange={(v) => update({ M_Ed_kNm: v })} hint="Positivo: tracción en la cara inferior. Flexión simple (N_Ed = 0)." />
            <label className="flex items-start gap-2 text-xs text-slate-700">
              <input
                type="checkbox"
                className="mt-0.5"
                checked={beam.secondary_element}
                onChange={(e) => update({ secondary_element: e.target.checked })}
              />
              <span>
                Elemento secundario en el que es admisible cierto riesgo de rotura frágil: A_s,min = 1,2·A_s,nec (alternativa de 9.2.1.1(1)).
              </span>
            </label>
            {beam.mode === "design" ? (
              <SelectField
                label="Diámetro supuesto para el canto útil inicial [mm]"
                value={beam.assumed_bar_diameter}
                options={DIAMETERS.filter((d) => d >= 10).map((d) => ({ value: d, label: String(d) }))}
                onChange={(v) => update({ assumed_bar_diameter: v })}
              />
            ) : (
              <LayersEditor layers={beam.layers} onChange={(layers) => update({ layers })} />
            )}
          </section>

          <div className="flex flex-wrap gap-2">
            <button className="btn-primary flex-1" onClick={calculate} disabled={busy}>
              {busy ? "Calculando…" : beam.mode === "design" ? "Dimensionar armadura" : "Comprobar sección"}
            </button>
            <button className="btn-secondary" onClick={pdf} disabled={busy} title="Genera el informe PDF con los datos actuales">
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

        {/* Resultados */}
        <div className="min-w-0 space-y-4" ref={resultRef}>
          <section className="card">
            <div className="mb-2 flex items-center justify-between">
              <h2 className="h2">Sección transversal</h2>
              {drawGeom && (
                <span className="text-xs text-slate-500">
                  A_s inf = {fmt(drawGeom.As_inferior, 0)} mm² · A_s sup = {fmt(drawGeom.As_superior, 0)} mm²
                  {drawGeom.d_inferior ? ` · d = ${fmt(drawGeom.d_inferior, 1)} mm` : ""}
                </span>
              )}
            </div>
            {drawGeom ? (
              <div className="flex justify-center">
                <SectionDrawing shape={drawGeom.shape} bars={drawGeom.bars} cover={beam.cover} verification={result && !stale ? result.verification : null} />
              </div>
            ) : (
              <ErrorBox error={previewError ?? "Introduzca una geometría válida."} />
            )}
            {beam.mode === "design" && !(result && !stale) && (
              <p className="mt-2 text-center text-xs text-slate-500">La armadura se dibujará tras el dimensionado.</p>
            )}
            {drawGeom && drawGeom.issues.length > 0 && (
              <ul className="mt-2 space-y-1 text-xs text-amber-800">
                {drawGeom.issues.map((i) => (
                  <li key={i}>⚠ {i}</li>
                ))}
              </ul>
            )}
          </section>

          {result && (
            <>
              {stale && (
                <div className="rounded-md border border-amber-200 bg-amber-50 p-2 text-sm text-amber-900">
                  Los datos han cambiado desde el último cálculo: los resultados mostrados están desactualizados.
                </div>
              )}
              <ResultSummary result={result} onUse={(layers) => update({ mode: "check", layers })} />
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

function summaryText(r: FlexureResult): string {
  const v = r.verification;
  if (r.mode === "design") {
    return r.proposal ? `${r.proposal.text_tension}${r.proposal.text_compression ? " / " + r.proposal.text_compression : ""}; M_Rd = ${fmt(v ? Math.abs(v.M_Rd) / 1e6 : null)} kN·m` : "Sin disposición práctica";
  }
  return v ? `M_Rd = ${fmt(Math.abs(v.M_Rd) / 1e6)} kN·m` : "Sin resultado";
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

function ResultSummary({ result, onUse }: { result: FlexureResult; onUse: (layers: FlexureResult["request"]["layers"]) => void }) {
  const v = result.verification;
  const d = result.design;
  const ok = result.ok;
  return (
    <section className="card">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <h2 className="h2">Resultado</h2>
        {ok === true && <span className="rounded bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-800">Todas las verificaciones se cumplen</span>}
        {ok === false && <span className="rounded bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-800">Hay verificaciones no superadas</span>}
        {ok === null && <span className="rounded bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-800">Verificación incompleta</span>}
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Metric label="M_Ed" value={fmt(result.request.M_Ed_kNm, 2)} unit="kN·m" />
        {v && <Metric label="M_Rd (parábola-rectángulo)" value={fmt(Math.abs(v.M_Rd) / 1e6, 2)} unit="kN·m" />}
        {v && <Metric label="x / d" value={fmt(v.xi, 3)} />}
        {v && <Metric label="d" value={fmt(v.d, 1)} unit="mm" />}
        {d && <Metric label="A_s1 necesaria (cálculo)" value={fmt(d.As1 as number, 0)} unit="mm²" />}
        {d && <Metric label="A_s2 necesaria" value={fmt(d.As2 as number, 0)} unit="mm²" />}
        {d && <Metric label="A_s,min" value={fmt(d.As_min as number, 0)} unit="mm²" />}
        {d && <Metric label="M_lim (sin A_s2)" value={fmt(d.M_lim_kNm as number, 1)} unit="kN·m" />}
        {result.comparison && <Metric label="M_Rd (bloque rectangular)" value={fmt(Math.abs(result.comparison.M_Rd) / 1e6, 2)} unit="kN·m" />}
      </div>
      {result.mode === "design" && result.proposal && (
        <div className="mt-4">
          <h3 className="text-sm font-semibold">Armadura propuesta</h3>
          <p className="mt-1 text-sm">
            Tracción: <span className="font-mono font-semibold">{result.proposal.text_tension}</span> ({fmt(result.proposal.As_tension, 0)} mm²) · Compresión:{" "}
            <span className="font-mono font-semibold">{result.proposal.text_compression ?? "no requerida por el cálculo"}</span>
          </p>
          <div className="mt-2 overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b text-left text-slate-500">
                  <th className="py-1 font-medium">Alternativa (tracción / compresión)</th>
                  <th className="py-1 font-medium">A_s [mm²]</th>
                  <th className="py-1 font-medium">d [mm]</th>
                  <th className="py-1 font-medium">M_Rd [kN·m]</th>
                  <th className="py-1 font-medium">x/d</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {result.proposal.alternatives.map((a, i) => (
                  <tr key={i} className="border-b border-slate-100">
                    <td className="py-1 font-mono">
                      {a.text_tension}
                      {a.text_compression ? ` / ${a.text_compression}` : ""}
                    </td>
                    <td className="py-1">{fmt(a.As_tension + a.As_compression, 0)}</td>
                    <td className="py-1">{fmt(a.d, 1)}</td>
                    <td className="py-1">{fmt(a.M_Rd_kNm, 1)}</td>
                    <td className="py-1">{fmt(a.xi, 3)}</td>
                    <td className="py-1 text-right">
                      <button className="text-brand hover:underline" onClick={() => onUse(a.layers)}>
                        Comprobar esta
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      {v && (
        <details className="mt-3">
          <summary className="cursor-pointer text-xs font-medium text-slate-600">Estado de las barras en rotura</summary>
          <table className="mt-1 w-full text-xs">
            <thead>
              <tr className="border-b text-left text-slate-500">
                <th className="py-1 font-medium">Barra</th>
                <th className="py-1 font-medium">y [mm]</th>
                <th className="py-1 font-medium">ε_s [‰]</th>
                <th className="py-1 font-medium">σ_s [MPa]</th>
                <th className="py-1 font-medium">F [kN]</th>
              </tr>
            </thead>
            <tbody>
              {v.bars.map((b, i) => (
                <tr key={i} className="border-b border-slate-100 font-mono">
                  <td className="py-0.5">
                    φ{b.diameter} ({b.face})
                  </td>
                  <td>{fmt(b.y, 1)}</td>
                  <td>{fmt(b.strain * 1000, 3)}</td>
                  <td>{fmt(b.stress, 1)}</td>
                  <td>{fmt(b.force / 1000, 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-1 text-[11px] text-slate-500">
            y medida desde la fibra comprimida. Tracción positiva. Pivote {v.pivot}; residuo de equilibrio {fmt(v.residual_N, 6)} N.
          </p>
        </details>
      )}
    </section>
  );
}
