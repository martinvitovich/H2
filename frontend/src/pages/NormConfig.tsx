import { useEffect, useState } from "react";
import { api } from "../api/client";
import { ErrorBox, PageHeader, ParamStatus } from "../components/ui";
import { useAppState } from "../state/AppState";
import type { NormInfo, Parameter } from "../types";

export default function NormConfig() {
  const { overrides, setOverrides } = useAppState();
  const [norm, setNorm] = useState<NormInfo | null>(null);
  const [params, setParams] = useState<Parameter[]>([]);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.parameters().then((r) => setNorm(r.norm)).catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    api
      .validateParameters(overrides)
      .then((r) => {
        setParams(r.parameters);
        setDraft(Object.fromEntries(r.parameters.map((p) => [p.key, Array.isArray(p.value) ? p.value.join(", ") : String(p.value)])));
      })
      .catch((e) => setError(e.message));
  }, [overrides]);

  async function apply() {
    setSaved(false);
    const ov: Record<string, unknown> = {};
    const defaults = (await api.parameters()).parameters;
    for (const p of defaults) {
      const raw = draft[p.key];
      const v = Array.isArray(p.value) ? raw.split(/[,;\s]+/).filter(Boolean).map(Number) : Number(raw.replace(",", "."));
      const same = Array.isArray(p.value) ? JSON.stringify(v) === JSON.stringify(p.value) : v === p.value;
      if (!same) ov[p.key] = v;
    }
    try {
      const r = await api.validateParameters(ov);
      setOverrides(r.overrides);
      setError(null);
      setSaved(true);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <>
      <PageHeader title="Configuración normativa" subtitle="Parámetros normativos centralizados. Cada valor indica su referencia y su estado de verificación. Los cambios se validan en el servidor y se aplican a todos los cálculos (y se guardan con el proyecto activo al guardar un elemento).">
        <button className="btn-secondary" onClick={() => setOverrides({})}>
          Restablecer valores por defecto
        </button>
        <button className="btn-primary" onClick={apply}>
          Aplicar cambios
        </button>
      </PageHeader>
      {norm && (
        <div className="card mb-4 text-sm">
          <div className="font-semibold">{norm.name}</div>
          <div className="text-slate-600">{norm.edition}</div>
          <p className="mt-2 text-xs text-slate-600">
            Los parámetros normativos se han cotejado con el texto oficial publicado en el BOE (la referencia indica la página). Los valores que dependen de otras disposiciones no consultadas figuran como «pendiente de verificación»; la matriz completa está en docs/normativa.md.
          </p>
        </div>
      )}
      <ErrorBox error={error} />
      {saved && <div className="mb-2 rounded-md border border-emerald-200 bg-emerald-50 p-2 text-sm text-emerald-800">Parámetros aplicados.</div>}
      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-xs text-slate-500">
              <th className="py-1.5 pr-2 font-medium">Parámetro</th>
              <th className="py-1.5 pr-2 font-medium">Valor</th>
              <th className="py-1.5 pr-2 font-medium">Referencia</th>
              <th className="py-1.5 font-medium">Estado</th>
            </tr>
          </thead>
          <tbody>
            {params.map((p) => (
              <tr key={p.key} className="border-b border-slate-100 align-top">
                <td className="py-1.5 pr-2">
                  <div>
                    <span className="font-mono">{p.symbol}</span> — {p.description}
                  </div>
                  {p.note && <div className="text-[11px] text-slate-500">{p.note}</div>}
                </td>
                <td className="w-40 py-1.5 pr-2">
                  <div className="flex items-center gap-1">
                    <input className="input" value={draft[p.key] ?? ""} onChange={(e) => setDraft({ ...draft, [p.key]: e.target.value })} />
                    {p.unit !== "-" && <span className="text-xs text-slate-500">{p.unit}</span>}
                  </div>
                  {p.min_value !== null && (
                    <div className="text-[10px] text-slate-400">
                      rango {p.min_value} – {p.max_value}
                    </div>
                  )}
                </td>
                <td className="py-1.5 pr-2 text-xs">{p.reference}</td>
                <td className="py-1.5">
                  <ParamStatus status={p.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
