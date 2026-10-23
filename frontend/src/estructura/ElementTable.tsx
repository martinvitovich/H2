import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ErrorBox } from "../components/ui";
import { sapi, type Affected } from "./api";
import type { CalcStatus, ElementRow, ElementType, Overview, Schema } from "./types";
import { ComplianceBadge, FieldInput, STATUS, StatusPill, TYPE_LABEL, num } from "./ui";

const PLURAL: Record<ElementType, string> = { losa: "losas", viga: "vigas", pilar: "pilares", zapata: "zapatas" };

/** Columnas de resultados (solo lectura) por tipo de elemento. */
function derivedCols(type: ElementType): { label: string; get: (e: ElementRow) => string }[] {
  const ef = (e: ElementRow, k: string) => num(e.loads.efforts?.[k]);
  switch (type) {
    case "losa":
      return [
        { label: "g [kN/m²]", get: (e) => num(e.loads.g) },
        { label: "q [kN/m²]", get: (e) => num(e.loads.q) },
        { label: "m_Ed⁺ [kN·m/m]", get: (e) => ef(e, "m_pos") },
        { label: "Armado", get: (e) => e.calcs.losa_flexion?.texto ?? "—" },
      ];
    case "viga":
      return [
        { label: "g / q [kN/m]", get: (e) => `${num(e.loads.g)} / ${num(e.loads.q)}` },
        { label: "M_Ed [kN·m]", get: (e) => (e.loads.efforts?.M_pos != null ? ef(e, "M_pos") : e.loads.efforts?.M_neg != null ? "−" + ef(e, "M_neg") : "—") },
        { label: "V_Ed [kN]", get: (e) => ef(e, "V_ed") },
        { label: "Flexión", get: (e) => e.calcs.viga_flexion?.texto ?? e.calcs.viga_flexion_neg?.texto ?? "—" },
      ];
    case "pilar":
      return [
        { label: "N_G / N_Q [kN]", get: (e) => `${num(e.loads.N_G)} / ${num(e.loads.N_Q)}` },
        { label: "N_Ed [kN]", get: (e) => ef(e, "N_Ed") },
      ];
    case "zapata":
      return [
        { label: "N_k [kN]", get: (e) => (e.loads.N_G != null ? num((e.loads.N_G ?? 0) + (e.loads.N_Q ?? 0)) : "—") },
        { label: "Terreno", get: (e) => e.calcs.zapata_terreno?.texto ?? "—" },
      ];
  }
}

export function ElementTable({
  pid,
  type,
  ov,
  schema,
  reload,
  onAffected,
}: {
  pid: string;
  type: ElementType;
  ov: Overview;
  schema: Schema;
  reload: () => Promise<void>;
  onAffected: (a: Affected[] | null) => void;
}) {
  const [q, setQ] = useState("");
  const [lv, setLv] = useState("");
  const [st, setSt] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [nNew, setNNew] = useState(1);
  const fields = schema.elements[type].filter((f) => f.table);
  const rows = useMemo(
    () =>
      ov.elements
        .filter((e) => e.type === type)
        .filter((e) => !lv || e.level_id === lv)
        .filter((e) => !st || e.status === st)
        .filter((e) => !q || `${e.code} ${e.description}`.toLowerCase().includes(q.toLowerCase())),
    [ov, type, q, lv, st],
  );
  const all = ov.elements.filter((e) => e.type === type);

  async function run(fn: () => Promise<unknown>) {
    setBusy(true);
    try {
      await fn();
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      await reload();
      setBusy(false);
    }
  }
  const patch = (e: ElementRow, b: Record<string, unknown>) =>
    run(async () => {
      const r = await sapi.patchElement(pid, e.id, b);
      onAffected(r.affected.filter((a) => a.id !== e.id || a.status !== "sin_calcular"));
    });
  const add = () =>
    run(async () => {
      const lvl = lv || ov.levels[ov.levels.length - 1]?.id || null;
      if (nNew <= 1) await sapi.createElement(pid, { type, level_id: type === "zapata" ? null : lvl });
      else await sapi.createElements(pid, Array.from({ length: nNew }, () => ({ type, level_id: type === "zapata" ? null : lvl })));
    });
  const counts = all.reduce<Record<string, number>>((a, e) => ({ ...a, [e.status]: (a[e.status] ?? 0) + 1 }), {});

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-2">
        <label className="block">
          <span className="label">Buscar</span>
          <input className="input w-44" placeholder="Código o descripción" value={q} onChange={(e) => setQ(e.target.value)} />
        </label>
        {type !== "zapata" && (
          <label className="block">
            <span className="label">Nivel</span>
            <select className="input w-36" value={lv} onChange={(e) => setLv(e.target.value)}>
              <option value="">Todos</option>
              {ov.levels.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.code} {l.name}
                </option>
              ))}
            </select>
          </label>
        )}
        <label className="block">
          <span className="label">Estado</span>
          <select className="input w-40" value={st} onChange={(e) => setSt(e.target.value)}>
            <option value="">Todos</option>
            {Object.entries(STATUS).map(([k, v]) => (
              <option key={k} value={k}>
                {v.label} {counts[k] ? `(${counts[k]})` : ""}
              </option>
            ))}
          </select>
        </label>
        <div className="flex-1" />
        <label className="block">
          <span className="label">Cantidad</span>
          <input className="input w-16" type="number" min={1} max={50} value={nNew} onChange={(e) => setNNew(Math.max(1, Math.min(50, Number(e.target.value) || 1)))} />
        </label>
        <button className="btn-primary" disabled={busy} onClick={add}>
          + Añadir {nNew > 1 ? `${PLURAL[type]} (${nNew})` : TYPE_LABEL[type].toLowerCase()}
        </button>
        <button
          className="btn-secondary"
          disabled={busy || all.length === 0}
          onClick={() =>
            run(async () => {
              const r = await sapi.calculate(pid, { element_ids: rows.map((e) => e.id), only_stale: true });
              setError(r.n_errors ? `${r.n_errors} cálculos con error; revise las fichas.` : null);
            })
          }
          title="Calcula los resultados sin calcular o desactualizados de los elementos visibles"
        >
          Calcular pendientes ({rows.length})
        </button>
      </div>
      <ErrorBox error={error} />
      {type !== "zapata" && ov.levels.length === 0 && (
        <div className="rounded-md border border-amber-200 bg-amber-50 p-2 text-sm text-amber-900">
          El proyecto no tiene niveles. Defina las plantas en la pestaña «Plantas y niveles» para asignar los elementos.
        </div>
      )}
      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
        <table className="w-full text-xs">
          <thead className="bg-slate-50">
            <tr className="text-left text-slate-600">
              <th className="sticky left-0 z-10 bg-slate-50 px-2 py-2 font-medium">Código</th>
              {type !== "zapata" && <th className="px-2 py-2 font-medium">Nivel</th>}
              {fields.map((f) => (
                <th key={f.key} className="px-2 py-2 font-medium" title={f.help || f.label}>
                  {f.label}
                  {f.unit && <span className="font-normal text-slate-400"> [{f.unit}]</span>}
                </th>
              ))}
              {derivedCols(type).map((c) => (
                <th key={c.label} className="bg-sky-50/60 px-2 py-2 font-medium text-sky-900">
                  {c.label}
                </th>
              ))}
              <th className="px-2 py-2 font-medium">Relaciones</th>
              <th className="px-2 py-2 font-medium">Estado</th>
              <th className="px-2 py-2 font-medium">Resultado</th>
              <th className="px-2 py-2" />
            </tr>
          </thead>
          <tbody>
            {rows.map((e) => (
              <tr key={e.id} className="border-t border-slate-100 align-top hover:bg-slate-50/60">
                <td className="sticky left-0 z-10 bg-white px-1 py-1">
                  <input
                    className="input w-20 px-1.5 py-1 text-xs font-medium"
                    defaultValue={e.code}
                    key={e.code}
                    aria-label="Código"
                    onBlur={(ev) => ev.target.value.trim() !== e.code && patch(e, { code: ev.target.value.trim() })}
                    onKeyDown={(ev) => ev.key === "Enter" && (ev.target as HTMLInputElement).blur()}
                  />
                </td>
                {type !== "zapata" && (
                  <td className="px-1 py-1">
                    <select className="input w-24 px-1 py-1 text-xs" value={e.level_id ?? ""} onChange={(ev) => patch(e, { level_id: ev.target.value || null })} aria-label="Nivel">
                      <option value="">—</option>
                      {ov.levels.map((l) => (
                        <option key={l.id} value={l.id}>
                          {l.code}
                        </option>
                      ))}
                    </select>
                  </td>
                )}
                {fields.map((f) => (
                  <td key={f.key} className="px-1 py-1">
                    <div className={f.kind === "select" ? "min-w-[120px]" : "w-20"}>
                      <FieldInput compact f={f} value={e.data[f.key]} onCommit={(v) => patch(e, { data: { [f.key]: v } })} />
                    </div>
                  </td>
                ))}
                {derivedCols(type).map((c) => (
                  <td key={c.label} className="bg-sky-50/30 px-2 py-1.5 font-mono whitespace-nowrap">
                    {c.get(e)}
                  </td>
                ))}
                <td className="px-2 py-1.5 text-[11px] text-slate-600">
                  {e.upstream.length > 0 && <div>← {e.upstream.join(", ")}</div>}
                  {e.downstream.length > 0 && <div>→ {e.downstream.join(", ")}</div>}
                  {e.upstream.length + e.downstream.length === 0 && <span className="text-slate-400">sin relaciones</span>}
                </td>
                <td className="px-2 py-1.5">
                  <StatusPill status={e.status as CalcStatus} small />
                  {e.missing.length > 0 && (
                    <div className="mt-0.5 max-w-[180px] text-[10px] leading-tight text-amber-800" title={e.missing.join("\n")}>
                      Falta: {e.missing[0]}
                      {e.missing.length > 1 ? ` (+${e.missing.length - 1})` : ""}
                    </div>
                  )}
                  {e.errors.length > 0 && <div className="mt-0.5 max-w-[180px] text-[10px] leading-tight text-red-700">{e.errors[0]}</div>}
                </td>
                <td className="px-2 py-1.5">
                  <ComplianceBadge c={e.compliance} />
                </td>
                <td className="px-2 py-1 whitespace-nowrap">
                  <Link className="btn-secondary px-2 py-1 text-xs" to={`/p/${pid}/e/${e.id}`}>
                    Ficha
                  </Link>{" "}
                  <button className="btn-secondary px-2 py-1 text-xs" title="Duplicar" disabled={busy} onClick={() => run(() => sapi.duplicateElement(pid, e.id))}>
                    ⧉
                  </button>{" "}
                  <button
                    className="btn-secondary px-2 py-1 text-xs text-red-700"
                    title="Eliminar"
                    disabled={busy}
                    onClick={() => {
                      const rel = e.upstream.length + e.downstream.length;
                      if (confirm(`¿Eliminar ${TYPE_LABEL[type].toLowerCase()} ${e.code}?${rel ? ` Se eliminarán también sus ${rel} relaciones.` : ""}`))
                        run(async () => {
                          const r = await sapi.deleteElement(pid, e.id);
                          if (r.affected.length) onAffected(r.affected.map((c) => ({ id: "", code: c, type, status: "desactualizado" })));
                        });
                    }}
                  >
                    ✕
                  </button>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={99} className="px-3 py-6 text-center text-sm text-slate-500">
                  {all.length === 0 ? `No hay ${PLURAL[type]}. Use «+ Añadir» para crearlos.` : "Ningún elemento coincide con el filtro."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="text-[11px] text-slate-500">
        Edición directa en la tabla: los cambios se guardan al salir de cada celda (o con Intro) y se validan en el servidor. Las columnas en azul
        se obtienen de la transmisión de cargas y de los resultados; los campos restantes (armaduras, esfuerzos manuales, cargas puntuales) se
        editan en la ficha del elemento.
      </p>
    </div>
  );
}
