import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, downloadBlob } from "../api/client";
import { LayersEditor } from "../components/LayersEditor";
import { SectionDrawing } from "../components/SectionDrawing";
import { ChecksTable, TracePanel } from "../components/TracePanel";
import { ErrorBox, NumberField, PageHeader, SelectField, StatusBadge, fmt } from "../components/ui";
import { DEFAULT_BEAM, useAppState } from "../state/AppState";
import type { ElsResult, ElsState, Geometry } from "../types";

type Tab = "fisuracion" | "deformaciones";

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

function shapeOf(e: ElsState) {
  return e.shape.kind === "rectangular"
    ? { kind: "rectangular" as const, b: e.shape.b, h: e.shape.h }
    : { kind: "T" as const, bf: e.shape.bf, hf: e.shape.hf, bw: e.shape.bw, h: e.shape.h };
}

export default function ELS() {
  const { els, setEls, beam, overrides, activeProject } = useAppState();
  const [params, setParams] = useSearchParams();
  const tab: Tab = params.get("calc") === "deformaciones" ? "deformaciones" : "fisuracion";
  const [catalog, setCatalog] = useState<{ concrete_classes: string[]; steel_grades: string[] }>({ concrete_classes: ["C25/30"], steel_grades: ["B500S"] });
  const [exposures, setExposures] = useState<Record<string, number>>({ XC1: 0.4 });
  const [systems, setSystems] = useState<Record<string, { K: number; description: string }>>({});
  const [result, setResult] = useState<ElsResult | null>(null);
  const [sent, setSent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<Geometry | null>(null);

  useEffect(() => {
    api.catalog().then(setCatalog).catch(() => undefined);
    api
      .elsCatalog()
      .then((c) => {
        setExposures(c.exposure_wmax);
        setSystems(c.systems);
      })
      .catch(() => undefined);
  }, []);
  useEffect(() => {
    setResult(null);
    setSent(null);
  }, [tab]);

  const update = (patch: Partial<ElsState>) => setEls({ ...els, ...patch });
  const updShape = (patch: Partial<ElsState["shape"]>) => setEls({ ...els, shape: { ...els.shape, ...patch } });
  const common = { element_name: els.element_name, shape: shapeOf(els), cover: els.cover, stirrup_diameter: els.stirrup_diameter, dg: els.dg, layers: els.layers, concrete_class: els.concrete_class, steel_grade: els.steel_grade, parameter_overrides: overrides };
  const req = useMemo(
    () =>
      tab === "fisuracion"
        ? { ...common, M_qp_kNm: els.M_qp_kNm, M_char_kNm: els.M_char_kNm, exposure: els.exposure, w_max: els.w_max, long_term: els.long_term }
        : {
            ...common,
            span: els.span,
            system: els.system,
            M_qp_kNm: els.M_qp_defl_kNm,
            RH: els.RH,
            t0: els.t0,
            cement: els.cement,
            perimeter: els.perimeter,
            phi_override: els.phi_override,
            eps_cs_override: els.eps_cs_override,
            camber: els.camber,
            kM: els.kM,
            kcs: els.kcs,
            As_req: els.As_req,
            As2_req: els.As2_req,
            fragile_partitions: els.fragile_partitions,
          },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [els, overrides, tab],
  );
  const stale = result !== null && sent !== JSON.stringify(req);

  useEffect(() => {
    const t = setTimeout(() => {
      api
        .sectionProperties({ shape: common.shape, cover: els.cover, stirrup_diameter: els.stirrup_diameter, dg: els.dg, layers: els.layers, parameter_overrides: overrides })
        .then(setPreview)
        .catch(() => setPreview(null));
    }, 250);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [els.shape, els.cover, els.stirrup_diameter, els.dg, els.layers, overrides]);

  function copyFromBeam() {
    setEls({
      ...els,
      element_name: beam.element_name,
      shape: { ...DEFAULT_BEAM.shape, ...beam.shape },
      cover: beam.cover,
      stirrup_diameter: beam.stirrup_diameter,
      dg: beam.dg,
      layers: beam.layers.map((l) => ({ ...l })),
      concrete_class: beam.concrete_class,
      steel_grade: beam.steel_grade,
    });
  }

  async function calculate() {
    setBusy(true);
    setError(null);
    setMsg(null);
    try {
      const r = tab === "fisuracion" ? await api.crack(req) : await api.deflection(req);
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
      const blob = await api.elsReport(tab, { project_name: activeProject?.name ?? "Sin proyecto", author: "", request: req });
      downloadBlob(blob, `informe_${tab}_${els.element_name.replace(/[^A-Za-z0-9_-]+/g, "_")}.pdf`);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function saveToProject() {
    if (!activeProject) return;
    try {
      const p = await api.project(activeProject.id);
      const type = tab === "fisuracion" ? ("els_fisuracion" as const) : ("els_deformaciones" as const);
      const R = result && !stale ? result.result : null;
      const summary = R
        ? {
            ok: result!.ok,
            summary: tab === "fisuracion" ? `w_k = ${fmt(R.w_k, 3)} mm (w_max = ${fmt(R.w_max, 2)})` : R.calc ? `δ_tot = ${fmt(R.calc.delta_total, 1)} mm` : "l/d",
          }
        : null;
      const idx = p.elements.findIndex((e) => e.name === els.element_name && e.type === type);
      const el = { id: idx >= 0 ? p.elements[idx].id : undefined, type, name: els.element_name, input: req, result: summary };
      const elements = idx >= 0 ? p.elements.map((e, i) => (i === idx ? el : e)) : [...p.elements, el];
      await api.updateProject(p.id, { name: p.name, description: p.description, parameter_overrides: overrides, elements });
      setMsg(`Guardado en el proyecto «${p.name}».`);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const R = result?.result;
  const geom = result && !stale ? result.result.geometry : preview;

  return (
    <>
      <PageHeader title="Estados Límite de Servicio (ELS)" subtitle="Fisuración y limitación de tensiones (7.2, 7.3) y control de deformaciones (7.4) de vigas y losas en flexión simple.">
        <StatusBadge status="pendiente_validacion" />
      </PageHeader>
      <div className="mb-4 flex gap-1 border-b border-slate-200">
        {(["fisuracion", "deformaciones"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setParams(t === "fisuracion" ? {} : { calc: t })}
            className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium ${tab === t ? "border-brand text-brand" : "border-transparent text-slate-500 hover:text-ink"}`}
          >
            {t === "fisuracion" ? "Fisuración" : "Deformaciones"}
          </button>
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-[minmax(320px,400px)_1fr]">
        <div className="space-y-4">
          <section className="card space-y-3">
            <label className="block">
              <span className="label">Elemento</span>
              <input className="input" value={els.element_name} onChange={(e) => update({ element_name: e.target.value })} />
            </label>
            <button className="btn-secondary w-full text-xs" onClick={copyFromBeam}>
              Copiar sección, armado y materiales de «Vigas — flexión»
            </button>
            <SelectField
              label="Tipo de sección"
              value={els.shape.kind}
              options={[
                { value: "rectangular", label: "Rectangular (viga o banda de losa)" },
                { value: "T", label: "En T" },
              ]}
              onChange={(v) => updShape({ kind: v })}
            />
            <div className="grid grid-cols-2 gap-2">
              {els.shape.kind === "rectangular" ? (
                <NumberField label="b" unit="mm" value={els.shape.b} onChange={(v) => updShape({ b: v })} />
              ) : (
                <>
                  <NumberField label="b_f" unit="mm" value={els.shape.bf} onChange={(v) => updShape({ bf: v })} />
                  <NumberField label="h_f" unit="mm" value={els.shape.hf} onChange={(v) => updShape({ hf: v })} />
                  <NumberField label="b_w" unit="mm" value={els.shape.bw} onChange={(v) => updShape({ bw: v })} />
                </>
              )}
              <NumberField label="h" unit="mm" value={els.shape.h} onChange={(v) => updShape({ h: v })} />
              <NumberField label="c_nom" unit="mm" value={els.cover} onChange={(v) => update({ cover: v })} />
              <NumberField label="φ estribo" unit="mm" value={els.stirrup_diameter} onChange={(v) => update({ stirrup_diameter: v })} />
              <SelectField label="Hormigón" value={els.concrete_class} options={catalog.concrete_classes.map((c) => ({ value: c, label: c }))} onChange={(v) => update({ concrete_class: v })} />
              <SelectField label="Acero" value={els.steel_grade} options={catalog.steel_grades.map((c) => ({ value: c, label: c }))} onChange={(v) => update({ steel_grade: v })} />
            </div>
            <LayersEditor layers={els.layers} onChange={(layers) => update({ layers })} />
          </section>

          {tab === "fisuracion" ? (
            <section className="card space-y-3">
              <h2 className="h2">Fisuración</h2>
              <div className="grid grid-cols-2 gap-2">
                <NumberField label="M cuasi-permanente" unit="kN·m" value={els.M_qp_kNm} onChange={(v) => update({ M_qp_kNm: v })} hint="+ tracción inferior" />
                <NumberField label="M característico (opcional)" unit="kN·m" value={els.M_char_kNm ?? undefined} onChange={(v) => update({ M_char_kNm: Number.isFinite(v) ? v : null })} hint="Para 7.2(2) y 7.2(5)" />
                <SelectField label="Clase de exposición" value={els.exposure} options={Object.keys(exposures).map((k) => ({ value: k, label: `${k} (w_max ${String(exposures[k]).replace(".", ",")} mm)` }))} onChange={(v) => update({ exposure: v })} />
                <NumberField label="w_max del proyecto (opcional)" unit="mm" value={els.w_max ?? undefined} step={0.05} onChange={(v) => update({ w_max: Number.isFinite(v) ? v : null })} hint="Vacío: tabla 27.2" />
              </div>
              <label className="flex items-center gap-2 text-xs">
                <input type="checkbox" checked={els.long_term} onChange={(e) => update({ long_term: e.target.checked })} />
                Cargas de larga duración (k_t = 0,4; si no, 0,6)
              </label>
            </section>
          ) : (
            <section className="card space-y-3">
              <h2 className="h2">Deformaciones</h2>
              <div className="grid grid-cols-2 gap-2">
                <NumberField label="Luz L" unit="mm" value={els.span} onChange={(v) => update({ span: v })} />
                <NumberField label="M cuasi-permanente máx." unit="kN·m" value={els.M_qp_defl_kNm} onChange={(v) => update({ M_qp_defl_kNm: v })} hint="Voladizo: negativo" />
              </div>
              <SelectField
                label="Sistema estructural (tabla A19.7.4)"
                value={els.system}
                options={Object.entries(systems).map(([k, v]) => ({ value: k as ElsState["system"], label: `${v.description} (K = ${String(v.K).replace(".", ",")})` }))}
                onChange={(v) => update({ system: v })}
              />
              {els.system !== "biapoyada" && els.system !== "voladizo" && (
                <div className="grid grid-cols-2 gap-2">
                  <NumberField label="k_M (forma, carga)" value={els.kM ?? undefined} step={0.005} onChange={(v) => update({ kM: Number.isFinite(v) ? v : null })} />
                  <NumberField label="k_cs (forma, retracción)" value={els.kcs ?? undefined} step={0.005} onChange={(v) => update({ kcs: Number.isFinite(v) ? v : null })} />
                  <p className="col-span-2 text-[11px] text-slate-500">Sin estos coeficientes solo se evalúa el método simplificado.</p>
                </div>
              )}
              <h3 className="text-xs font-semibold text-slate-500 uppercase">Fluencia y retracción (3.1.4, Apéndice B)</h3>
              <div className="grid grid-cols-2 gap-2">
                <NumberField label="Humedad relativa HR" unit="%" value={els.RH} onChange={(v) => update({ RH: v })} />
                <NumberField label="Edad de carga t₀" unit="días" value={els.t0} onChange={(v) => update({ t0: v })} />
                <SelectField
                  label="Cemento"
                  value={els.cement}
                  options={[
                    { value: "S" as const, label: "Clase S" },
                    { value: "N" as const, label: "Clase N" },
                    { value: "R" as const, label: "Clase R" },
                  ]}
                  onChange={(v) => update({ cement: v })}
                />
                <NumberField label="Perímetro expuesto u" unit="mm" value={els.perimeter ?? undefined} onChange={(v) => update({ perimeter: Number.isFinite(v) ? v : null })} hint="Vacío: perímetro completo" />
                <NumberField label="φ(∞,t₀) (opcional)" value={els.phi_override ?? undefined} step={0.1} onChange={(v) => update({ phi_override: Number.isFinite(v) ? v : null })} hint="Vacío: Apéndice B" />
                <NumberField label="ε_cs (opcional)" unit="‰" value={els.eps_cs_override ?? undefined} step={0.05} onChange={(v) => update({ eps_cs_override: Number.isFinite(v) ? v : null })} />
                <NumberField label="Contraflecha" unit="mm" value={els.camber} onChange={(v) => update({ camber: v })} />
              </div>
              <h3 className="text-xs font-semibold text-slate-500 uppercase">Método simplificado (7.4.2)</h3>
              <div className="grid grid-cols-2 gap-2">
                <NumberField label="A_s,req (ELU)" unit="mm²" value={els.As_req ?? undefined} onChange={(v) => update({ As_req: Number.isFinite(v) ? v : null })} />
                <NumberField label="A_s2,req (ELU)" unit="mm²" value={els.As2_req} onChange={(v) => update({ As2_req: v })} />
              </div>
              <label className="flex items-center gap-2 text-xs">
                <input type="checkbox" checked={els.fragile_partitions} onChange={(e) => update({ fragile_partitions: e.target.checked })} />
                Soporta tabiques susceptibles de dañarse (corrección 7/l_eff u 8,5/l_eff)
              </label>
            </section>
          )}

          <div className="flex flex-wrap gap-2">
            <button className="btn-primary flex-1" onClick={calculate} disabled={busy}>
              {busy ? "Calculando…" : tab === "fisuracion" ? "Comprobar fisuración" : "Comprobar deformaciones"}
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
              Para guardar, abra o cree un proyecto en{" "}
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
                <SectionDrawing shape={geom.shape} bars={geom.bars} cover={els.cover} />
              </div>
            ) : (
              <p className="text-sm text-slate-500">Geometría no válida.</p>
            )}
          </section>
          {result && R && (
            <>
              {stale && <div className="rounded-md border border-amber-200 bg-amber-50 p-2 text-sm text-amber-900">Los datos han cambiado: resultados desactualizados.</div>}
              <section className="card">
                <div className="mb-3 flex flex-wrap items-center gap-2">
                  <h2 className="h2">Resultado</h2>
                  {result.ok === true && <span className="rounded bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-800">Todas las verificaciones se cumplen</span>}
                  {result.ok === false && <span className="rounded bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-800">Hay verificaciones no superadas</span>}
                  {result.ok === null && <span className="rounded bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-800">Verificación incompleta</span>}
                </div>
                {tab === "fisuracion" ? (
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                    <Metric label="M_cr" value={fmt(R.Mcr / 1e6, 1)} unit="kN·m" />
                    <Metric label="x (fisurada)" value={fmt(R.x, 1)} unit="mm" />
                    <Metric label="σ_s (cuasi-perm.)" value={fmt(R.sigma_s, 0)} unit="MPa" />
                    <Metric label="σ_c (cuasi-perm.)" value={fmt(R.sigma_c, 1)} unit="MPa" />
                    {R.s_r_max !== undefined && <Metric label="s_r,max" value={fmt(R.s_r_max, 0)} unit="mm" />}
                    <Metric label="w_k" value={fmt(R.w_k, 3)} unit="mm" />
                    <Metric label="w_max" value={fmt(R.w_max, 2)} unit="mm" />
                    {R.As_min_crack !== undefined && <Metric label="A_s,min (7.1)" value={fmt(R.As_min_crack, 0)} unit="mm²" />}
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                    {R.ld && <Metric label="l/d (actual / límite)" value={`${fmt(R.ld.actual, 1)} / ${fmt(R.ld.limit, 1)}`} />}
                    {R.calc && (
                      <>
                        <Metric label="φ(∞,t₀)" value={fmt(R.calc.phi, 2)} />
                        <Metric label="ε_cs" value={fmt(R.calc.eps_cs * 1000, 3)} unit="‰" />
                        <Metric label="M_cr" value={fmt(R.calc.Mcr / 1e6, 1)} unit="kN·m" />
                        <Metric label="δ instantánea" value={fmt(R.calc.delta_inst, 1)} unit="mm" />
                        <Metric label="δ total (L/250)" value={`${fmt(R.calc.delta_total, 1)} (${fmt(R.calc.limit_total, 1)})`} unit="mm" />
                        <Metric label="δ diferida (L/500)" value={`${fmt(R.calc.delta_deferred, 1)} (${fmt(R.calc.limit_deferred, 1)})`} unit="mm" />
                      </>
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
    </>
  );
}
