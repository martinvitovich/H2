import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, downloadBlob } from "../api/client";
import { ChecksTable, TracePanel } from "../components/TracePanel";
import { ErrorBox, NumberField, PageHeader, SelectField, StatusBadge, fmt } from "../components/ui";
import { useAppState } from "../state/AppState";
import type { ElsResult, SlabRequest } from "../types";

const DIAMS = [6, 8, 10, 12, 16, 20, 25];

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

function StripDrawing({ h, cover, phi, s, top }: { h: number; cover: number; phi: number; s: number; top: boolean }) {
  const W = 1000;
  const sc = 460 / W;
  const H = h * sc;
  const n = Math.max(1, Math.floor(W / s));
  const xs = Array.from({ length: n }, (_, i) => s / 2 + i * s).filter((x) => x < W);
  const y = top ? cover + phi / 2 : h - cover - phi / 2;
  return (
    <svg viewBox={`0 0 ${W * sc + 40} ${H + 40}`} className="h-auto w-full max-w-[520px]" role="img" aria-label="Banda de losa de 1 m">
      <rect x={20} y={20} width={W * sc} height={H} fill="#e2e8f0" stroke="#1e293b" strokeWidth={1.5} />
      {xs.map((x, i) => (
        <circle key={i} cx={20 + x * sc} cy={20 + y * sc} r={Math.max((phi / 2) * sc, 1.5)} fill="#b03a2e" />
      ))}
      <text x={20} y={14} fontSize={10} fill="#475569">
        banda de 1 m · h = {h} mm · φ{phi} c/{s} mm
      </text>
    </svg>
  );
}

export default function Slabs() {
  const { slab, setSlab, overrides, activeProject } = useAppState();
  const [catalog, setCatalog] = useState<{ concrete_classes: string[]; steel_grades: string[] }>({ concrete_classes: ["C25/30"], steel_grades: ["B500S"] });
  const [result, setResult] = useState<ElsResult | null>(null);
  const [sent, setSent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    api.catalog().then(setCatalog).catch(() => undefined);
  }, []);
  const req = useMemo<SlabRequest>(() => ({ ...slab, bar_spacing: slab.mode === "check" ? slab.bar_spacing : null, parameter_overrides: overrides }), [slab, overrides]);
  const stale = result !== null && sent !== JSON.stringify(req);
  const update = (patch: Partial<SlabRequest>) => setSlab({ ...slab, ...patch });

  async function calculate() {
    setBusy(true);
    setError(null);
    setMsg(null);
    try {
      const r = await api.slab(req);
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
    try {
      const blob = await api.slabReport({ project_name: activeProject?.name ?? "Sin proyecto", author: "", request: req });
      downloadBlob(blob, `informe_losa_${slab.element_name.replace(/[^A-Za-z0-9_-]+/g, "_")}.pdf`);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function saveToProject() {
    if (!activeProject) return;
    try {
      const p = await api.project(activeProject.id);
      const R = result && !stale ? result.result : null;
      const summary = R ? { ok: result!.ok, summary: `φ${R.phi} c/${R.s}; m_Rd = ${fmt(R.m_Rd / 1e6, 1)} kN·m/m` } : null;
      const idx = p.elements.findIndex((e) => e.name === slab.element_name && e.type === "losa");
      const el = { id: idx >= 0 ? p.elements[idx].id : undefined, type: "losa" as const, name: slab.element_name, input: req, result: summary };
      const elements = idx >= 0 ? p.elements.map((e, i) => (i === idx ? el : e)) : [...p.elements, el];
      await api.updateProject(p.id, { name: p.name, description: p.description, parameter_overrides: overrides, elements });
      setMsg(`Losa guardada en el proyecto «${p.name}».`);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  const R = result?.result;

  return (
    <>
      <PageHeader
        title="Losas macizas unidireccionales"
        subtitle="Cálculo por banda de 1 m: flexión ELU, cuantías y separaciones (9.3.1), armadura de reparto y cortante sin armadura de cortante (6.2.2). Las flechas se comprueban en «Estados Límite de Servicio» con una sección rectangular de 1000 mm de ancho."
      >
        <StatusBadge status="pendiente_validacion" />
      </PageHeader>
      <div className="grid gap-4 lg:grid-cols-[minmax(320px,400px)_1fr]">
        <div className="space-y-4">
          <section className="card space-y-3">
            <label className="block">
              <span className="label">Elemento</span>
              <input className="input" value={slab.element_name} onChange={(e) => update({ element_name: e.target.value })} />
            </label>
            <div className="grid grid-cols-2 gap-2">
              <button className={slab.mode === "design" ? "btn-primary" : "btn-secondary"} onClick={() => update({ mode: "design" })}>
                Dimensionar
              </button>
              <button className={slab.mode === "check" ? "btn-primary" : "btn-secondary"} onClick={() => update({ mode: "check" })}>
                Comprobar
              </button>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <NumberField label="Canto h" unit="mm" value={slab.h} onChange={(v) => update({ h: v })} />
              <NumberField label="Recubrimiento c_nom" unit="mm" value={slab.cover} onChange={(v) => update({ cover: v })} hint="Hasta la armadura principal" />
              <NumberField label="Luz eficaz l_eff" unit="mm" value={slab.span ?? undefined} onChange={(v) => update({ span: Number.isFinite(v) ? v : null })} />
              <SelectField label="Hormigón" value={slab.concrete_class} options={catalog.concrete_classes.map((c) => ({ value: c, label: c }))} onChange={(v) => update({ concrete_class: v })} />
              <SelectField label="Acero" value={slab.steel_grade} options={catalog.steel_grades.map((c) => ({ value: c, label: c }))} onChange={(v) => update({ steel_grade: v })} />
            </div>
          </section>
          <section className="card space-y-3">
            <h2 className="h2">Solicitaciones por metro</h2>
            <div className="grid grid-cols-2 gap-2">
              <NumberField label="m_Ed" unit="kN·m/m" value={slab.m_Ed_kNm} onChange={(v) => update({ m_Ed_kNm: v })} hint="+ tracción inferior" />
              <NumberField label="v_Ed" unit="kN/m" value={slab.v_Ed_kN} onChange={(v) => update({ v_Ed_kN: v })} />
            </div>
          </section>
          <section className="card space-y-3">
            <h2 className="h2">Armaduras</h2>
            <div className="grid grid-cols-2 gap-2">
              <SelectField label="φ principal [mm]" value={slab.bar_diameter} options={DIAMS.map((d) => ({ value: d, label: String(d) }))} onChange={(v) => update({ bar_diameter: v })} />
              {slab.mode === "check" && <NumberField label="Separación s" unit="mm" value={slab.bar_spacing ?? undefined} onChange={(v) => update({ bar_spacing: v })} />}
              <SelectField label="φ reparto [mm]" value={slab.secondary_diameter ?? 8} options={DIAMS.map((d) => ({ value: d, label: String(d) }))} onChange={(v) => update({ secondary_diameter: v })} />
              <NumberField label="Separación reparto" unit="mm" value={slab.secondary_spacing ?? undefined} onChange={(v) => update({ secondary_spacing: Number.isFinite(v) ? v : null })} hint="Vacío: propuesta" />
            </div>
            <label className="flex items-start gap-2 text-xs text-slate-700">
              <input type="checkbox" className="mt-0.5" checked={slab.low_brittle_risk} onChange={(e) => update({ low_brittle_risk: e.target.checked })} />
              <span>Riesgo de rotura frágil pequeño: A_s,min = 1,2·A_s,nec (nota de 9.3.1.1(1)).</span>
            </label>
          </section>
          <div className="flex flex-wrap gap-2">
            <button className="btn-primary flex-1" onClick={calculate} disabled={busy}>
              {busy ? "Calculando…" : slab.mode === "design" ? "Dimensionar losa" : "Comprobar losa"}
            </button>
            <button className="btn-secondary" onClick={pdf}>
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
          {result && R ? (
            <>
              {stale && <div className="rounded-md border border-amber-200 bg-amber-50 p-2 text-sm text-amber-900">Los datos han cambiado: resultados desactualizados.</div>}
              <section className="card">
                <div className="mb-3 flex flex-wrap items-center gap-2">
                  <h2 className="h2">Resultado</h2>
                  {result.ok === true && <span className="rounded bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-800">Todas las verificaciones se cumplen</span>}
                  {result.ok === false && <span className="rounded bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-800">Hay verificaciones no superadas</span>}
                  {result.ok === null && <span className="rounded bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-800">Verificación incompleta</span>}
                </div>
                {R.phi && (
                  <div className="mb-3 flex justify-center">
                    <StripDrawing h={slab.h} cover={slab.cover} phi={R.phi} s={R.s} top={slab.m_Ed_kNm < 0} />
                  </div>
                )}
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                  <Metric label="d" value={fmt(R.d, 1)} unit="mm" />
                  <Metric label="A_s necesaria" value={fmt(R.As_req, 0)} unit="mm²/m" />
                  <Metric label="A_s,min" value={fmt(R.As_min, 0)} unit="mm²/m" />
                  {R.phi && <Metric label="Armadura" value={`φ${R.phi} c/${R.s}`} />}
                  {R.As && <Metric label="A_s dispuesta" value={fmt(R.As, 0)} unit="mm²/m" />}
                  {R.m_Rd && <Metric label="m_Rd" value={fmt(R.m_Rd / 1e6, 1)} unit="kN·m/m" />}
                  {R.secondary && <Metric label="Reparto" value={`φ${R.secondary.diameter} c/${R.secondary.spacing}`} />}
                  {R.v_Rd_c && <Metric label="V_Rd,c" value={fmt(R.v_Rd_c / 1000, 1)} unit="kN/m" />}
                </div>
                {R.alternatives && R.alternatives.length > 0 && (
                  <p className="mt-3 text-xs text-slate-600">
                    Alternativas: {R.alternatives.map((a: { diameter: number; spacing: number; As: number }) => `φ${a.diameter} c/${a.spacing} (${fmt(a.As, 0)} mm²/m)`).join(" · ")}
                  </p>
                )}
              </section>
              <section className="card">
                <h2 className="h2 mb-2">Verificaciones</h2>
                <ChecksTable checks={result.trace.checks} />
              </section>
              <TracePanel trace={result.trace} />
            </>
          ) : (
            <div className="card text-sm text-slate-500">Introduzca los datos y pulse calcular.</div>
          )}
        </div>
      </div>
    </>
  );
}
