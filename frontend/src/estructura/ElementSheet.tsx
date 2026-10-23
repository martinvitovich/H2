import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { LayersEditor } from "../components/LayersEditor";
import { ChecksTable, TracePanel } from "../components/TracePanel";
import { ErrorBox } from "../components/ui";
import type { LayerIn } from "../types";
import { sapi, type Affected } from "./api";
import { RelationsPanel } from "./Relations";
import type { CalcEntry, ElementDetail, FieldDef, Overview, Schema } from "./types";
import { AffectedBanner, ComplianceBadge, FieldInput, OkBadge, StatusPill, TAB_OF_TYPE, TYPE_LABEL, TYPE_PLURAL, num } from "./ui";

const ACTION_LABEL: Record<string, string> = {
  elemento_creado: "Creado",
  elemento_modificado: "Modificado",
  elemento_duplicado: "Creado por duplicación",
  elemento_importado: "Importado",
  relacion_creada: "Relación creada",
  relacion_modificada: "Relación modificada",
  relacion_eliminada: "Relación eliminada",
  calculo: "Cálculo",
};

function histText(d: Record<string, any>): string {
  if (d.cambios)
    return Object.entries(d.cambios as Record<string, { antes: unknown; despues: unknown }>)
      .map(([k, v]) => `${k}: ${short(v.antes)} → ${short(v.despues)}`)
      .join("; ");
  return Object.entries(d)
    .filter(([, v]) => typeof v !== "object")
    .map(([k, v]) => `${k}: ${v}`)
    .join("; ");
}
function short(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  if (Array.isArray(v)) return `[${v.length}]`;
  if (typeof v === "object") return "{…}";
  return String(v);
}

export function ElementSheet({
  pid,
  eid,
  ov,
  schema,
  reloadOverview,
}: {
  pid: string;
  eid: string;
  ov: Overview;
  schema: Schema;
  reloadOverview: () => Promise<void>;
}) {
  const [d, setD] = useState<ElementDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [affected, setAffected] = useState<Affected[] | null>(null);
  const [busy, setBusy] = useState(false);
  const nav = useNavigate();

  const load = useCallback(async () => {
    try {
      setD(await sapi.element(pid, eid));
    } catch (e) {
      setError((e as Error).message);
    }
  }, [pid, eid]);
  useEffect(() => {
    setD(null);
    setAffected(null);
    setError(null);
    load();
  }, [load]);

  const refresh = async (aff: Affected[] | null) => {
    if (aff) setAffected(aff.filter((a) => a.id !== eid));
    await Promise.all([load(), reloadOverview()]);
  };
  async function patch(b: Record<string, unknown>) {
    try {
      const r = await sapi.patchElement(pid, eid, b);
      setError(null);
      await refresh(r.affected);
    } catch (e) {
      setError((e as Error).message);
      await load();
    }
  }
  async function act(fn: () => Promise<unknown>) {
    setBusy(true);
    try {
      await fn();
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      await Promise.all([load(), reloadOverview()]);
      setBusy(false);
    }
  }

  if (!d) return <div className="text-sm text-slate-500">{error ?? "Cargando ficha…"}</div>;
  const fields = schema.elements[d.type];
  const groups = [...new Set(fields.map((f) => f.group))];
  const pending = d.calc_list.filter((c) => ["sin_calcular", "desactualizado", "error"].includes(c.status)).length;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <Link className="text-brand underline" to={`/p/${pid}/${TAB_OF_TYPE[d.type]}`}>
          ← {TYPE_PLURAL[d.type]}
        </Link>
      </div>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-xl font-semibold">
            {TYPE_LABEL[d.type]} {d.code}{" "}
            <span className="text-sm font-normal text-slate-500">{d.level_code ? `· nivel ${d.level_code}` : ""}</span>
          </h2>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <StatusPill status={d.status} /> <ComplianceBadge c={d.compliance} />
            {d.affects.length > 0 && <span className="text-xs text-slate-500">Dependen de este elemento: {d.affects.join(", ")}</span>}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="btn-primary" disabled={busy} onClick={() => act(() => sapi.calculate(pid, { element_ids: [eid], only_stale: true }))}>
            {busy ? "Calculando…" : `Calcular${pending ? ` (${pending} pendientes)` : ""}`}
          </button>
          <button className="btn-secondary" disabled={busy} onClick={() => act(() => sapi.calculate(pid, { element_ids: [eid], only_stale: false }))} title="Repite todos los cálculos del elemento">
            Recalcular todo
          </button>
          {(d.type === "viga" || d.type === "losa") && (
            <button
              className="btn-secondary"
              disabled={busy}
              title="Copia en los datos del elemento la armadura propuesta por un dimensionado vigente (no sustituye armadura ya definida)"
              onClick={() =>
                act(async () => {
                  const r = await sapi.adopt(pid, eid);
                  setAffected(r.affected.filter((a) => a.id !== eid));
                })
              }
            >
              Adoptar armadura propuesta
            </button>
          )}
          <button className="btn-secondary" onClick={() => act(() => sapi.downloadElementPdf(pid, eid))}>
            Ficha PDF
          </button>
          <button className="btn-secondary" disabled={busy} onClick={() => act(async () => nav(`/p/${pid}/e/${(await sapi.duplicateElement(pid, eid)).id}`))}>
            Duplicar
          </button>
          <button
            className="btn-secondary text-red-700"
            disabled={busy}
            onClick={async () => {
              if (!confirm(`¿Eliminar ${TYPE_LABEL[d.type].toLowerCase()} ${d.code} y sus ${d.relations.length} relaciones?`)) return;
              try {
                await sapi.deleteElement(pid, eid);
                await reloadOverview();
                nav(`/p/${pid}/${TAB_OF_TYPE[d.type]}`);
              } catch (e) {
                setError((e as Error).message);
              }
            }}
          >
            Eliminar
          </button>
        </div>
      </div>
      <AffectedBanner pid={pid} affected={affected} onClose={() => setAffected(null)} />
      <ErrorBox error={error} />
      {d.missing.length > 0 && (
        <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          <b>Datos necesarios para calcular:</b>
          <ul className="mt-1 list-disc pl-5">
            {d.missing.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        </div>
      )}
      {d.errors.length > 0 && <ErrorBox error={d.errors.join("\n")} />}

      <div className="grid gap-4 xl:grid-cols-2">
        <section className="card space-y-3">
          <h3 className="h2">Identificación y datos de entrada</h3>
          <div className="grid gap-2 sm:grid-cols-3">
            <label className="block">
              <span className="label">Código</span>
              <FieldInput f={{ key: "code", label: "Código", kind: "text" } as FieldDef} value={d.code} onCommit={(v) => patch({ code: v })} />
            </label>
            <label className="block">
              <span className="label">Nivel</span>
              <select className="input" value={d.level_id ?? ""} onChange={(e) => patch({ level_id: e.target.value || null })}>
                <option value="">—</option>
                {ov.levels.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.code} {l.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="label">Descripción</span>
              <FieldInput f={{ key: "description", label: "Descripción", kind: "text" } as FieldDef} value={d.description} onCommit={(v) => patch({ description: v })} />
            </label>
          </div>
          {groups.map((g) => (
            <fieldset key={g} className="rounded-md border border-slate-200 p-3">
              <legend className="px-1 text-xs font-semibold text-slate-600">{g}</legend>
              <div className="grid gap-2 sm:grid-cols-2">
                {fields
                  .filter((f) => f.group === g)
                  .map((f) =>
                    f.kind === "layers" ? (
                      <div key={f.key} className="sm:col-span-2">
                        <span className="label">{f.label}</span>
                        <LayersBox value={d.data[f.key] ?? []} onSave={(v) => patch({ data: { [f.key]: v } })} />
                      </div>
                    ) : f.kind === "pointloads" ? (
                      <div key={f.key} className="sm:col-span-2">
                        <span className="label">{f.label}</span>
                        <PointLoadsBox value={d.data[f.key] ?? []} onSave={(v) => patch({ data: { [f.key]: v } })} />
                        <span className="text-[11px] text-slate-500">{f.help}</span>
                      </div>
                    ) : (
                      <label key={f.key} className={`block ${f.kind === "bool" ? "flex items-center gap-2" : ""}`}>
                        {f.kind !== "bool" && (
                          <span className="label">
                            {f.label}
                            {f.unit && <span className="ml-1 font-normal text-slate-400">[{f.unit}]</span>}
                          </span>
                        )}
                        <FieldInput f={f} value={d.data[f.key]} onCommit={(v) => patch({ data: { [f.key]: v } })} />
                        {f.kind === "bool" && <span className="text-sm">{f.label}</span>}
                        {f.help && f.kind !== "bool" && <span className="mt-0.5 block text-[11px] text-slate-500">{f.help}</span>}
                      </label>
                    ),
                  )}
              </div>
            </fieldset>
          ))}
          <p className="text-[11px] text-slate-500">Los cambios se guardan automáticamente y quedan registrados en el historial.</p>
        </section>

        <div className="space-y-4">
          <section className="card">
            <h3 className="h2 mb-2">Relaciones</h3>
            <RelationsPanel pid={pid} el={d} relations={d.relations} ov={ov} schema={schema} onChanged={refresh} />
          </section>
          <section className="card">
            <h3 className="h2 mb-1">Cargas y procedencia</h3>
            <p className="mb-2 text-[11px] text-slate-500">Valores característicos: G permanente, Q variable. Cada fila indica el elemento o dato de origen.</p>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-slate-200 text-left text-slate-500">
                    <th className="py-1 pr-2 font-medium">Concepto</th>
                    <th className="py-1 pr-2 font-medium">Regla / expresión</th>
                    <th className="py-1 pr-2 text-right font-medium">G</th>
                    <th className="py-1 pr-2 text-right font-medium">Q</th>
                    <th className="py-1 pr-2 font-medium">Unidad</th>
                    <th className="py-1 font-medium">Origen</th>
                  </tr>
                </thead>
                <tbody>
                  {d.loads_detail.rows.map((r, i) => (
                    <tr key={i} className={`border-b border-slate-100 ${r.concepto.startsWith("Total") ? "font-semibold" : ""}`}>
                      <td className="py-1 pr-2">{r.concepto}</td>
                      <td className="py-1 pr-2 font-mono text-[11px] text-slate-600">{r.expresion}</td>
                      <td className="py-1 pr-2 text-right font-mono">{num(r.G)}</td>
                      <td className="py-1 pr-2 text-right font-mono">{num(r.Q)}</td>
                      <td className="py-1 pr-2">{r.unidad}</td>
                      <td className="py-1">
                        {r.element_id ? (
                          <Link className="text-brand underline" to={`/p/${pid}/e/${r.element_id}`}>
                            {r.origen}
                          </Link>
                        ) : (
                          r.origen
                        )}
                      </td>
                    </tr>
                  ))}
                  {d.loads_detail.rows.length === 0 && (
                    <tr>
                      <td colSpan={6} className="py-2 text-slate-500">
                        Sin cargas obtenidas todavía.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            {[...d.loads_detail.warnings].map((w) => (
              <p key={w} className="mt-1 text-xs text-orange-800">
                ⚠ {w}
              </p>
            ))}
            {d.loads_detail.notes.map((w) => (
              <p key={w} className="mt-1 text-[11px] text-slate-500">
                {w}
              </p>
            ))}
          </section>
        </div>
      </div>

      <section className="card">
        <h3 className="h2 mb-2">Cálculos, resultados y verificaciones</h3>
        <div className="space-y-2">
          {d.calc_list.map((c) => (
            <CalcCard key={c.calc_type} pid={pid} eid={eid} c={c} onError={setError} />
          ))}
        </div>
      </section>

      <section className="card">
        <h3 className="h2 mb-2">Historial de cambios</h3>
        <div className="max-h-72 overflow-y-auto">
          <table className="w-full text-xs">
            <tbody>
              {d.history.map((h, i) => (
                <tr key={i} className="border-b border-slate-100 align-top">
                  <td className="py-1 pr-2 whitespace-nowrap text-slate-500">{new Date(h.ts).toLocaleString("es-ES")}</td>
                  <td className="py-1 pr-2 whitespace-nowrap">{ACTION_LABEL[h.action] ?? h.action}</td>
                  <td className="py-1 font-mono text-[11px] text-slate-600">{histText(h.detail)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function CalcCard({ pid, eid, c, onError }: { pid: string; eid: string; c: CalcEntry; onError: (e: string | null) => void }) {
  const [open, setOpen] = useState(false);
  const out = c.stored?.output;
  const current = c.status === "actual";
  if (c.status === "no_aplica")
    return (
      <div className="rounded-md border border-slate-100 px-3 py-2 text-xs text-slate-400">
        {c.label} — no aplica ({c.reason})
      </div>
    );
  return (
    <div className={`rounded-md border px-3 py-2 ${current ? "border-slate-200" : "border-dashed border-slate-300 bg-slate-50/50"}`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">{c.label}</span>
        <StatusPill status={c.status} />
        {current && <OkBadge ok={out?.ok} />}
        <span className="flex-1" />
        {c.stored && (
          <span className="text-[11px] text-slate-500">
            Calculado el {new Date(c.stored.computed_at).toLocaleString("es-ES")} · motor v{c.stored.engine_version}
          </span>
        )}
        {current && out && (
          <>
            <button className="btn-secondary px-2 py-1 text-xs" onClick={() => setOpen(!open)}>
              {open ? "Ocultar detalle" : "Ver detalle"}
            </button>
            {c.calc_type !== "zapata_terreno" && (
              <button
                className="btn-secondary px-2 py-1 text-xs"
                onClick={() => sapi.downloadCalcPdf(pid, eid, c.calc_type).catch((e) => onError((e as Error).message))}
              >
                Informe PDF
              </button>
            )}
          </>
        )}
      </div>
      {c.status === "faltan_datos" && <div className="mt-1 text-xs text-amber-800">Faltan datos: {c.missing?.join("; ")}</div>}
      {(c.status === "error" || c.status === "error_datos") && <div className="mt-1 text-xs text-red-700">{c.reason}</div>}
      {c.status === "desactualizado" && (
        <div className="mt-1 text-xs text-orange-800">
          {c.reason}. Resultado anterior (no vigente, solo como referencia): <span className="line-through">{out?.summary?.texto ?? "—"}</span>
        </div>
      )}
      {c.status === "sin_calcular" && <div className="mt-1 text-xs text-slate-500">Datos completos: pendiente de cálculo.</div>}
      {current && out && <div className="mt-1 text-sm">{out.summary?.texto}</div>}
      {current && open && out && (
        <div className="mt-3 space-y-3">
          <ChecksTable checks={out.result.trace.checks} />
          <TracePanel trace={out.result.trace} />
        </div>
      )}
    </div>
  );
}

function LayersBox({ value, onSave }: { value: LayerIn[]; onSave: (v: LayerIn[]) => void }) {
  const [v, setV] = useState<LayerIn[]>(value);
  useEffect(() => setV(value), [value]);
  const dirty = JSON.stringify(v) !== JSON.stringify(value);
  return (
    <div className="rounded-md border border-slate-200 p-2">
      {v.length === 0 && <p className="mb-1 text-xs text-slate-500">Sin armadura dispuesta (los cálculos de flexión se hacen en modo dimensionado).</p>}
      <LayersEditor layers={v} onChange={setV} />
      {dirty && (
        <div className="mt-2 flex gap-2">
          <button className="btn-primary px-2 py-1 text-xs" onClick={() => onSave(v.map((l) => ({ ...l, depth: l.depth ?? undefined })))}>
            Guardar armadura
          </button>
          <button className="btn-secondary px-2 py-1 text-xs" onClick={() => setV(value)}>
            Descartar
          </button>
        </div>
      )}
    </div>
  );
}

interface PL {
  pos: number;
  G: number;
  Q: number;
  desc: string;
}
function PointLoadsBox({ value, onSave }: { value: PL[]; onSave: (v: PL[]) => void }) {
  const [v, setV] = useState<PL[]>(value);
  useEffect(() => setV(value), [value]);
  const dirty = JSON.stringify(v) !== JSON.stringify(value);
  const set = (i: number, p: Partial<PL>) => setV(v.map((x, j) => (j === i ? { ...x, ...p } : x)));
  return (
    <div className="rounded-md border border-slate-200 p-2">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-left text-slate-500">
            <th className="font-medium">x [m]</th>
            <th className="font-medium">G [kN]</th>
            <th className="font-medium">Q [kN]</th>
            <th className="font-medium">Descripción</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {v.map((p, i) => (
            <tr key={i}>
              {(["pos", "G", "Q"] as const).map((k) => (
                <td key={k} className="pr-1 pb-1">
                  <input className="input px-1.5 py-1 text-xs" type="number" value={p[k]} onChange={(e) => set(i, { [k]: Number(e.target.value) })} />
                </td>
              ))}
              <td className="pr-1 pb-1">
                <input className="input px-1.5 py-1 text-xs" value={p.desc} onChange={(e) => set(i, { desc: e.target.value })} />
              </td>
              <td>
                <button className="btn-secondary px-2 py-1 text-xs" onClick={() => setV(v.filter((_, j) => j !== i))}>
                  ✕
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-1 flex gap-2">
        <button className="btn-secondary px-2 py-1 text-xs" onClick={() => setV([...v, { pos: 0, G: 0, Q: 0, desc: "" }])}>
          + Carga puntual
        </button>
        {dirty && (
          <>
            <button className="btn-primary px-2 py-1 text-xs" onClick={() => onSave(v)}>
              Guardar cargas
            </button>
            <button className="btn-secondary px-2 py-1 text-xs" onClick={() => setV(value)}>
              Descartar
            </button>
          </>
        )}
      </div>
    </div>
  );
}
