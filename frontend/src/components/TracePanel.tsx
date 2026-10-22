import { useState } from "react";
import type { Check, Trace } from "../types";
import { ParamStatus, fmt } from "./ui";

export function ChecksTable({ checks }: { checks: Check[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
            <th className="py-1.5 pr-3 font-medium">Verificación</th>
            <th className="py-1.5 pr-3 font-medium">Valor</th>
            <th className="py-1.5 pr-3 font-medium">Límite / capacidad</th>
            <th className="py-1.5 pr-3 font-medium">Resultado</th>
            <th className="py-1.5 font-medium">Referencia</th>
          </tr>
        </thead>
        <tbody>
          {checks.map((c, i) => (
            <tr key={i} className="border-b border-slate-100 align-top">
              <td className="py-1.5 pr-3">
                {c.name}
                {c.note && <div className="text-[11px] text-slate-500">{c.note}</div>}
              </td>
              <td className="py-1.5 pr-3 font-mono text-xs">{c.demand}</td>
              <td className="py-1.5 pr-3 font-mono text-xs">{c.capacity}</td>
              <td className="py-1.5 pr-3">
                {c.ok === true && <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-xs font-semibold text-emerald-700">CUMPLE</span>}
                {c.ok === false && <span className="rounded bg-red-50 px-1.5 py-0.5 text-xs font-semibold text-red-700">NO CUMPLE</span>}
                {c.ok === null && <span className="rounded bg-amber-50 px-1.5 py-0.5 text-xs font-semibold text-amber-700">NO EVALUABLE</span>}
              </td>
              <td className="py-1.5 text-xs text-slate-600">{c.reference}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const TABS = ["Procedimiento", "Hipótesis", "Parámetros", "Datos de entrada", "Advertencias y limitaciones"] as const;

/** Sección «Normativa y procedimiento»: ecuaciones, sustituciones y referencias. */
export function TracePanel({ trace }: { trace: Trace }) {
  const [tab, setTab] = useState<(typeof TABS)[number]>("Procedimiento");
  return (
    <section className="card">
      <h2 className="h2">Normativa y procedimiento</h2>
      <dl className="mt-2 grid gap-x-4 gap-y-1 text-xs sm:grid-cols-[140px_1fr]">
        <dt className="text-slate-500">Norma</dt>
        <dd>{trace.norm.name}</dd>
        <dt className="text-slate-500">Edición</dt>
        <dd>{trace.norm.edition}</dd>
        <dt className="text-slate-500">Cálculo</dt>
        <dd>{trace.calculation}</dd>
        <dt className="text-slate-500">Método</dt>
        <dd>{trace.method}</dd>
        <dt className="text-slate-500">Estado de validación</dt>
        <dd className="text-amber-800">{trace.validation_status}</dd>
      </dl>
      <div className="mt-3 flex flex-wrap gap-1 border-b border-slate-200">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`-mb-px border-b-2 px-2.5 py-1.5 text-xs font-medium ${
              tab === t ? "border-brand text-brand" : "border-transparent text-slate-500 hover:text-ink"
            }`}
          >
            {t}
            {t === "Advertencias y limitaciones" && trace.warnings.length > 0 && (
              <span className="ml-1 rounded-full bg-amber-100 px-1.5 text-[10px] text-amber-800">{trace.warnings.length}</span>
            )}
          </button>
        ))}
      </div>
      <div className="mt-3">
        {tab === "Procedimiento" && (
          <ol className="space-y-2">
            {trace.steps.map((s, i) => (
              <li key={i} className="rounded-md border border-slate-100 bg-slate-50/60 p-2.5">
                <div className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between">
                  <span className="text-sm font-medium">
                    {i + 1}. {s.title}
                  </span>
                  <span className="text-[11px] text-slate-500">{s.reference}</span>
                </div>
                <div className="mt-1 overflow-x-auto font-mono text-xs text-slate-800">{s.equation}</div>
                {s.substitution && <div className="overflow-x-auto font-mono text-xs text-slate-500">{s.substitution}</div>}
                {s.result !== null && (
                  <div className="mt-1 font-mono text-xs font-semibold text-brand">
                    {s.symbol ? `${s.symbol} = ` : ""}
                    {fmt(s.result, 4)} {s.unit !== "-" ? s.unit : ""}
                  </div>
                )}
                {s.note && <div className="mt-0.5 text-[11px] text-slate-500">{s.note}</div>}
              </li>
            ))}
          </ol>
        )}
        {tab === "Hipótesis" && (
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {trace.assumptions.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        )}
        {tab === "Parámetros" && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs text-slate-500">
                  <th className="py-1 pr-2 font-medium">Parámetro</th>
                  <th className="py-1 pr-2 font-medium">Valor</th>
                  <th className="py-1 pr-2 font-medium">Referencia</th>
                  <th className="py-1 font-medium">Estado</th>
                </tr>
              </thead>
              <tbody>
                {trace.parameters_used.map((p) => (
                  <tr key={p.key} className="border-b border-slate-100 align-top">
                    <td className="py-1 pr-2">
                      <span className="font-mono">{p.symbol}</span> — {p.description}
                    </td>
                    <td className="py-1 pr-2 font-mono text-xs">
                      {Array.isArray(p.value) ? p.value.join(", ") : p.value} {p.unit !== "-" ? p.unit : ""}
                    </td>
                    <td className="py-1 pr-2 text-xs">{p.reference}</td>
                    <td className="py-1">
                      <ParamStatus status={p.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {tab === "Datos de entrada" && (
          <div className="grid gap-3 sm:grid-cols-2">
            <pre className="overflow-x-auto rounded bg-slate-50 p-2 text-[11px]">{JSON.stringify(trace.inputs, null, 2)}</pre>
            <div className="text-sm">
              <h3 className="mb-1 text-xs font-semibold text-slate-500 uppercase">Unidades</h3>
              <ul className="space-y-0.5">
                {Object.entries(trace.units).map(([k, v]) => (
                  <li key={k}>
                    {k}: <span className="font-mono">{v}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
        {tab === "Advertencias y limitaciones" && (
          <div className="space-y-3 text-sm">
            {trace.warnings.length > 0 && (
              <ul className="space-y-1">
                {trace.warnings.map((w) => (
                  <li key={w} className="rounded border border-amber-200 bg-amber-50 p-2 text-amber-900">
                    ⚠ {w}
                  </li>
                ))}
              </ul>
            )}
            <ul className="list-disc space-y-1 pl-5 text-slate-700">
              {trace.limitations.map((l) => (
                <li key={l}>{l}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </section>
  );
}
