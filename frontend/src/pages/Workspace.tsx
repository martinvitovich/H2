import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, NavLink, useNavigate, useParams } from "react-router-dom";
import { ErrorBox, ParamStatus } from "../components/ui";
import { sapi, tablesApi, type Affected, type SummaryTable } from "../estructura/api";
import { ElementSheet } from "../estructura/ElementSheet";
import { ElementTable } from "../estructura/ElementTable";
import { KIND_LABEL } from "../estructura/Relations";
import type { CalcStatus, ElementType, FieldDef, HistoryEntry, Overview, Schema } from "../estructura/types";
import { AffectedBanner, ComplianceBadge, FieldInput, OkBadge, STATUS, StatusPill, TAB_OF_TYPE, TYPE_LABEL, num, useSchema } from "../estructura/ui";
import { useAppState } from "../state/AppState";

const TABS: { id: string; label: string; type?: ElementType }[] = [
  { id: "resumen", label: "Resumen" },
  { id: "datos", label: "Datos y materiales" },
  { id: "niveles", label: "Plantas y niveles" },
  { id: "losas", label: "Losas", type: "losa" },
  { id: "vigas", label: "Vigas", type: "viga" },
  { id: "pilares", label: "Pilares", type: "pilar" },
  { id: "fundaciones", label: "Fundaciones", type: "zapata" },
  { id: "relaciones", label: "Relaciones y cargas" },
  { id: "resultados", label: "Resultados y verificaciones" },
  { id: "planillas", label: "Planillas y documentación" },
  { id: "configuracion", label: "Configuración" },
];

export default function Workspace() {
  const { pid = "", tab = "resumen", eid } = useParams();
  const [ov, setOv] = useState<Overview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [affected, setAffected] = useState<Affected[] | null>(null);
  const [busy, setBusy] = useState(false);
  const schema = useSchema();
  const { setActiveProject } = useAppState();

  const reload = useCallback(async () => {
    try {
      const o = await sapi.get(pid);
      setOv(o);
      setActiveProject({ id: o.project.id, name: o.project.name });
    } catch (e) {
      setError((e as Error).message);
    }
  }, [pid, setActiveProject]);
  useEffect(() => {
    reload();
  }, [reload]);
  useEffect(() => setAffected(null), [tab, eid]);

  if (!ov || !schema)
    return (
      <div className="space-y-2">
        <ErrorBox error={error} />
        {!error && <div className="text-sm text-slate-500">Cargando proyecto…</div>}
        <Link className="text-sm text-brand underline" to="/proyectos">
          ← Proyectos
        </Link>
      </div>
    );
  const p = ov.project;
  const ver = ov.summary.verification;
  const nPending = (ov.summary.calcs.sin_calcular ?? 0) + (ov.summary.calcs.desactualizado ?? 0) + (ov.summary.calcs.error ?? 0);

  async function calcAll() {
    setBusy(true);
    try {
      const r = await sapi.calculate(pid, { only_stale: true });
      setError(
        r.n_errors || r.n_missing
          ? `Calculados: ${r.n_calculated}. Con error: ${r.n_errors}. Sin calcular por falta de datos: ${r.n_missing}. Consulte «Resultados y verificaciones».`
          : null,
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      await reload();
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-2 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0">
          <Link className="text-xs text-brand underline" to="/proyectos">
            ← Proyectos
          </Link>
          <h1 className="truncate text-xl font-semibold tracking-tight sm:text-2xl">
            {p.name} {p.status === "archivado" && <span className="rounded bg-slate-200 px-2 py-0.5 align-middle text-xs font-medium text-slate-700">Archivado</span>}
          </h1>
          <p className="text-xs text-slate-500">
            {[p.location, p.client, p.structural_system].filter(Boolean).join(" · ") || "Sin datos generales"} · guardado{" "}
            {new Date(p.modified).toLocaleString("es-ES")}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="btn-primary" disabled={busy || nPending === 0} onClick={calcAll} title="Calcula solo los resultados sin calcular, desactualizados o con error">
            {busy ? "Calculando…" : `Calcular pendientes (${nPending})`}
          </button>
          <button className="btn-secondary" onClick={() => sapi.downloadExcel(pid).catch((e) => setError(e.message))}>
            Excel
          </button>
          <button className="btn-secondary" onClick={() => sapi.downloadPdf(pid).catch((e) => setError(e.message))}>
            Memoria PDF
          </button>
        </div>
      </div>
      <div className={`rounded-md border px-3 py-2 text-sm ${ver.level === "cumple_alcance" ? "border-emerald-200 bg-emerald-50 text-emerald-900" : ver.level === "no_cumple" ? "border-red-200 bg-red-50 text-red-900" : "border-amber-200 bg-amber-50 text-amber-900"}`}>
        {ver.text} <span className="text-[11px] opacity-80">{ver.disclaimer}</span>
      </div>
      <nav className="-mx-1 flex gap-1 overflow-x-auto border-b border-slate-200 pb-px">
        {TABS.map((t) => {
          const n = t.type ? ov.elements.filter((e) => e.type === t.type).length : null;
          return (
            <NavLink
              key={t.id}
              to={`/p/${pid}/${t.id}`}
              className={({ isActive }) =>
                `shrink-0 rounded-t-md px-3 py-1.5 text-sm whitespace-nowrap ${isActive && !eid ? "border-b-2 border-brand font-medium text-brand" : "text-slate-600 hover:bg-slate-100"}`
              }
            >
              {t.label}
              {n !== null && <span className="ml-1 text-[11px] text-slate-400">{n}</span>}
            </NavLink>
          );
        })}
      </nav>
      <AffectedBanner pid={pid} affected={affected} onClose={() => setAffected(null)} />
      <ErrorBox error={error} />
      {eid ? (
        <ElementSheet pid={pid} eid={eid} ov={ov} schema={schema} reloadOverview={reload} />
      ) : (
        <TabContent tab={tab} pid={pid} ov={ov} schema={schema} reload={reload} setAffected={setAffected} setError={setError} />
      )}
    </div>
  );
}

function TabContent(props: {
  tab: string;
  pid: string;
  ov: Overview;
  schema: Schema;
  reload: () => Promise<void>;
  setAffected: (a: Affected[] | null) => void;
  setError: (e: string | null) => void;
}) {
  const { tab, pid, ov, schema, reload, setAffected } = props;
  const t = TABS.find((x) => x.id === tab);
  if (t?.type) return <ElementTable key={t.type} pid={pid} type={t.type} ov={ov} schema={schema} reload={reload} onAffected={setAffected} />;
  switch (tab) {
    case "resumen":
      return <Summary {...props} />;
    case "datos":
      return <ProjectData {...props} groups={["Materiales"]} />;
    case "niveles":
      return <Levels {...props} />;
    case "relaciones":
      return <RelationsMap {...props} />;
    case "resultados":
      return <Results {...props} />;
    case "planillas":
      return <Sheets {...props} />;
    case "configuracion":
      return <ProjectData {...props} groups={["Acciones", "Recubrimientos", "Servicio", "Cimentación"]} config />;
    default:
      return <div className="card">Pestaña no encontrada.</div>;
  }
}

function Summary({ pid, ov }: { pid: string; ov: Overview }) {
  const [hist, setHist] = useState<HistoryEntry[]>([]);
  useEffect(() => {
    sapi.history(pid).then((h) => setHist(h.slice(0, 15))).catch(() => setHist([]));
  }, [pid, ov]);
  const types: ElementType[] = ["losa", "viga", "pilar", "zapata"];
  const attention = ov.elements.filter((e) => !["actual", "no_aplica"].includes(e.status) || e.compliance === "no_cumple");
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <section className="card lg:col-span-2">
        <h2 className="h2 mb-2">Estado por tipo de elemento</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                <th className="py-1 pr-2 font-medium">Tipo</th>
                <th className="py-1 pr-2 font-medium">Total</th>
                {(["actual", "desactualizado", "sin_calcular", "faltan_datos", "error"] as CalcStatus[]).map((s) => (
                  <th key={s} className="py-1 pr-2 font-medium">
                    {STATUS[s].label}
                  </th>
                ))}
                <th className="py-1 pr-2 font-medium">No cumplen</th>
              </tr>
            </thead>
            <tbody>
              {types.map((t) => {
                const els = ov.elements.filter((e) => e.type === t);
                return (
                  <tr key={t} className="border-b border-slate-100">
                    <td className="py-1.5 pr-2">
                      <Link className="text-brand underline" to={`/p/${pid}/${TAB_OF_TYPE[t]}`}>
                        {TYPE_LABEL[t]}
                      </Link>
                    </td>
                    <td className="py-1.5 pr-2 font-medium">{els.length}</td>
                    {(["actual", "desactualizado", "sin_calcular", "faltan_datos", "error"] as CalcStatus[]).map((s) => (
                      <td key={s} className="py-1.5 pr-2">
                        {els.filter((e) => e.status === s || (s === "error" && e.status === "error_datos")).length || "—"}
                      </td>
                    ))}
                    <td className="py-1.5 pr-2 text-red-700">{els.filter((e) => e.compliance === "no_cumple").length || "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <h2 className="h2 mt-4 mb-2">Requieren atención ({attention.length})</h2>
        <div className="max-h-80 overflow-y-auto">
          {attention.length === 0 && <p className="text-sm text-slate-500">Ningún elemento pendiente.</p>}
          {attention.map((e) => (
            <div key={e.id} className="flex flex-wrap items-center gap-2 border-b border-slate-100 py-1 text-sm">
              <Link className="w-20 font-medium text-brand underline" to={`/p/${pid}/e/${e.id}`}>
                {e.code}
              </Link>
              <StatusPill status={e.status} small />
              <ComplianceBadge c={e.compliance} />
              <span className="text-xs text-slate-600">{e.missing[0] ?? e.errors[0] ?? ""}</span>
            </div>
          ))}
        </div>
      </section>
      <section className="card">
        <h2 className="h2 mb-2">Datos del proyecto</h2>
        <dl className="grid grid-cols-[110px_1fr] gap-x-2 gap-y-1 text-xs">
          <dt className="text-slate-500">Norma</dt>
          <dd>{ov.project.norm.name}</dd>
          <dt className="text-slate-500">Materiales</dt>
          <dd>
            {ov.project.settings.concrete_class} · {ov.project.settings.steel_grade}
          </dd>
          <dt className="text-slate-500">Niveles</dt>
          <dd>{ov.levels.map((l) => l.code).join(", ") || "—"}</dd>
          <dt className="text-slate-500">Relaciones</dt>
          <dd>{ov.links.length}</dd>
          <dt className="text-slate-500">Motor</dt>
          <dd>v{ov.engine_version}</dd>
        </dl>
        <h2 className="h2 mt-4 mb-2">Actividad reciente</h2>
        <ul className="space-y-1 text-xs">
          {hist.map((h, i) => (
            <li key={i} className="text-slate-600">
              <span className="text-slate-400">{new Date(h.ts).toLocaleString("es-ES")}</span> · {h.element_code ? <b>{h.element_code} </b> : null}
              {h.action.replace(/_/g, " ")}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function ProjectData({
  pid,
  ov,
  schema,
  reload,
  setAffected,
  setError,
  groups,
  config,
}: {
  pid: string;
  ov: Overview;
  schema: Schema;
  reload: () => Promise<void>;
  setAffected: (a: Affected[] | null) => void;
  setError: (e: string | null) => void;
  groups: string[];
  config?: boolean;
}) {
  const nav = useNavigate();
  const p = ov.project;
  const save = async (b: Record<string, unknown>) => {
    try {
      const r = await sapi.patch(pid, b);
      setError(null);
      if (r.affected) setAffected(r.affected.filter((a) => a.status === "desactualizado"));
    } catch (e) {
      setError((e as Error).message);
    }
    await reload();
  };
  const infoFields: [string, string][] = [
    ["name", "Nombre del proyecto"],
    ["description", "Descripción"],
    ["location", "Ubicación"],
    ["client", "Cliente (opcional)"],
    ["project_date", "Fecha"],
    ["structural_system", "Sistema estructural"],
  ];
  const [ovText, setOvText] = useState(JSON.stringify(p.parameter_overrides, null, 2));
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {!config && (
        <section className="card space-y-2">
          <h2 className="h2">Datos generales</h2>
          {infoFields.map(([k, label]) => (
            <label key={k} className="block">
              <span className="label">{label}</span>
              <FieldInput f={{ key: k, label, kind: "text" } as FieldDef} value={(p as any)[k]} onCommit={(v) => save({ [k]: v })} />
            </label>
          ))}
          <p className="text-[11px] text-slate-500">Norma de referencia: {p.norm.name} — {p.norm.edition}</p>
        </section>
      )}
      <section className="card space-y-3">
        {groups.map((g) => (
          <fieldset key={g} className="rounded-md border border-slate-200 p-3">
            <legend className="px-1 text-xs font-semibold text-slate-600">{g}</legend>
            <div className="grid gap-2 sm:grid-cols-2">
              {schema.settings
                .filter((f) => f.group === g)
                .map((f) => (
                  <label key={f.key} className={`block ${f.kind === "bool" ? "flex items-center gap-2" : ""}`}>
                    {f.kind !== "bool" && (
                      <span className="label">
                        {f.label}
                        {f.unit && <span className="ml-1 font-normal text-slate-400">[{f.unit}]</span>}
                      </span>
                    )}
                    <FieldInput f={f} value={p.settings[f.key]} onCommit={(v) => save({ settings: { [f.key]: v } })} />
                    {f.kind === "bool" && <span className="text-sm">{f.label}</span>}
                    {schema.settings_origin[f.key] && (
                      <span className="mt-0.5 block text-[11px] text-amber-800">Origen: {schema.settings_origin[f.key]}</span>
                    )}
                    {f.help && <span className="mt-0.5 block text-[11px] text-slate-500">{f.help}</span>}
                  </label>
                ))}
            </div>
          </fieldset>
        ))}
        <p className="text-[11px] text-slate-500">
          Cambiar un dato general afecta a todos los elementos que lo usan: sus resultados quedan desactualizados hasta recalcular.
        </p>
      </section>
      {config && (
        <section className="card space-y-3">
          <h2 className="h2">Parámetros normativos del proyecto</h2>
          <p className="text-xs text-slate-600">
            Valores modificados respecto a los del Anejo 19 (JSON clave → valor). Consulte las claves, rangos y referencias en{" "}
            <Link className="text-brand underline" to="/normativa">
              Configuración normativa
            </Link>
            . <ParamStatus status="definido_por_usuario" />
          </p>
          <textarea className="input h-32 font-mono text-xs" value={ovText} onChange={(e) => setOvText(e.target.value)} />
          <button
            className="btn-secondary"
            onClick={() => {
              try {
                save({ parameter_overrides: JSON.parse(ovText || "{}") });
              } catch {
                setError("JSON no válido en los parámetros normativos.");
              }
            }}
          >
            Guardar parámetros
          </button>
          <h2 className="h2 pt-2">Acciones del proyecto</h2>
          <div className="flex flex-wrap gap-2">
            <button
              className="btn-secondary"
              onClick={async () => {
                const name = prompt("Nombre de la copia", `${p.name} (copia)`);
                if (!name) return;
                try {
                  const d = await sapi.duplicate(pid, name);
                  nav(`/p/${d.project.id}/resumen`);
                } catch (e) {
                  setError((e as Error).message);
                }
              }}
            >
              Duplicar proyecto
            </button>
            <button className="btn-secondary" onClick={async () => (await sapi.archive(pid, p.status !== "archivado"), reload())}>
              {p.status === "archivado" ? "Reactivar" : "Archivar"}
            </button>
            <button
              className="btn-secondary"
              onClick={async () => {
                const data = await sapi.exportJson(pid);
                const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
                const { downloadBlob } = await import("../api/client");
                downloadBlob(blob, `${p.name.replace(/[^A-Za-z0-9_-]+/g, "_")}.json`);
              }}
            >
              Exportar JSON
            </button>
            <button
              className="btn-secondary text-red-700"
              onClick={async () => {
                if (prompt(`Para eliminar definitivamente el proyecto escriba su nombre: «${p.name}»`) !== p.name) return;
                await sapi.remove(pid);
                nav("/proyectos");
              }}
            >
              Eliminar proyecto
            </button>
          </div>
        </section>
      )}
    </div>
  );
}

function Levels({ pid, ov, reload, setAffected, setError }: { pid: string; ov: Overview; reload: () => Promise<void>; setAffected: (a: Affected[] | null) => void; setError: (e: string | null) => void }) {
  const run = async (fn: () => Promise<unknown>) => {
    try {
      await fn();
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
    await reload();
  };
  const F = (key: string, label: string, kind: "text" | "number" = "number") => ({ key, label, kind }) as FieldDef;
  return (
    <section className="card">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="h2">Plantas y niveles</h2>
        <button
          className="btn-primary"
          onClick={() =>
            run(() => {
              let n = (ov.levels.length + 1) * 100;
              while (ov.levels.some((l) => l.code === `N${n}`)) n += 100;
              const last = ov.levels[ov.levels.length - 1];
              return sapi.createLevel(pid, {
                code: `N${n}`,
                name: "",
                elevation_m: last?.elevation_m != null && last?.height_m != null ? last.elevation_m + last.height_m : null,
                height_m: last?.height_m ?? null,
                sort_order: ov.levels.length,
              });
            })
          }
        >
          + Añadir nivel
        </button>
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
            <th className="py-1 pr-2 font-medium">Código</th>
            <th className="py-1 pr-2 font-medium">Nombre</th>
            <th className="py-1 pr-2 font-medium">Cota [m]</th>
            <th className="py-1 pr-2 font-medium" title="Altura de los pilares de este nivel si no se indica en el pilar">
              Altura de planta [m]
            </th>
            <th className="py-1 pr-2 font-medium">Orden</th>
            <th className="py-1 pr-2 font-medium">Elementos</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {ov.levels.map((l) => (
            <tr key={l.id} className="border-b border-slate-100">
              {(
                [
                  ["code", "Código", "text"],
                  ["name", "Nombre", "text"],
                  ["elevation_m", "Cota", "number"],
                  ["height_m", "Altura", "number"],
                  ["sort_order", "Orden", "number"],
                ] as const
              ).map(([k, lab, kind]) => (
                <td key={k} className="py-1 pr-2">
                  <FieldInput
                    compact
                    f={F(k, lab, kind)}
                    value={(l as any)[k]}
                    onCommit={(v) =>
                      run(async () => {
                        const r = await sapi.patchLevel(pid, l.id, { [k]: v });
                        if (k === "height_m") setAffected(r.affected.filter((a) => a.status === "desactualizado"));
                      })
                    }
                  />
                </td>
              ))}
              <td className="py-1 pr-2 text-xs">{ov.elements.filter((e) => e.level_id === l.id).length}</td>
              <td className="py-1">
                <button className="btn-secondary px-2 py-1 text-xs text-red-700" onClick={() => confirm(`¿Eliminar el nivel ${l.code}?`) && run(() => sapi.deleteLevel(pid, l.id))}>
                  ✕
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {ov.levels.length === 0 && <p className="mt-2 text-sm text-slate-500">Sin niveles. Añada las plantas del edificio (p. ej., N100 planta baja, N200 planta alta).</p>}
    </section>
  );
}

function RelationsMap({ pid, ov }: { pid: string; ov: Overview }) {
  const code = useMemo(() => Object.fromEntries(ov.elements.map((e) => [e.id, e])), [ov]);
  const [k, setK] = useState("");
  const links = ov.links.filter((l) => !k || l.kind === k);
  const unlinked = ov.elements.filter((e) => e.upstream.length + e.downstream.length === 0);
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <section className="card lg:col-span-2">
        <div className="mb-2 flex items-center justify-between gap-2">
          <h2 className="h2">Mapa de dependencias ({ov.links.length} relaciones)</h2>
          <select className="input w-56" value={k} onChange={(e) => setK(e.target.value)}>
            <option value="">Todas</option>
            {Object.entries(KIND_LABEL).map(([kk, v]) => (
              <option key={kk} value={kk}>
                {v}
              </option>
            ))}
          </select>
        </div>
        <p className="mb-2 text-xs text-slate-500">
          Las cargas se transmiten de origen a destino. Para crear o editar relaciones, abra la ficha de cualquiera de los dos elementos.
        </p>
        <div className="max-h-[60vh] overflow-y-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                <th className="py-1 pr-2 font-medium">Tipo</th>
                <th className="py-1 pr-2 font-medium">Origen</th>
                <th className="py-1 pr-2 font-medium">Destino</th>
                <th className="py-1 font-medium">Datos</th>
              </tr>
            </thead>
            <tbody>
              {links.map((l) => (
                <tr key={l.id} className="border-b border-slate-100">
                  <td className="py-1 pr-2 text-xs">{KIND_LABEL[l.kind]}</td>
                  {[l.source_id, l.target_id].map((x) => (
                    <td key={x} className="py-1 pr-2">
                      <Link className="text-brand underline" to={`/p/${pid}/e/${x}`}>
                        {code[x]?.code}
                      </Link>{" "}
                      <StatusPill status={code[x]?.status} small />
                    </td>
                  ))}
                  <td className="py-1 font-mono text-[11px]">
                    {Object.entries(l.data)
                      .filter(([, v]) => v !== null && v !== "")
                      .map(([a, b]) => `${a} = ${b}`)
                      .join("; ")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section className="card">
        <h2 className="h2 mb-2">Elementos sin relaciones ({unlinked.length})</h2>
        <p className="mb-2 text-xs text-slate-500">No reciben ni transmiten cargas a otros elementos.</p>
        <div className="flex flex-wrap gap-1">
          {unlinked.map((e) => (
            <Link key={e.id} className="rounded bg-slate-100 px-2 py-0.5 text-xs text-brand underline" to={`/p/${pid}/e/${e.id}`}>
              {e.code}
            </Link>
          ))}
        </div>
        <h2 className="h2 mt-4 mb-2">Reglas de transmisión</h2>
        <ul className="list-disc space-y-1 pl-4 text-xs text-slate-600">
          <li>Losa: g = h·γ + CM + muros/superficie; q = SCU.</li>
          <li>Losa → viga: w = carga·A/L (área tributaria) o carga·b (ancho tributario).</li>
          <li>Viga: peso propio + muros + otras + losas; reacciones por equilibrio isostático (o manuales).</li>
          <li>Viga → pilar / viga: reacción del extremo indicado (en la viga receptora, como carga puntual).</li>
          <li>Pilar: Σ reacciones + pilar superior + peso propio + adicionales; N_Ed = γ_G·N_G + γ_Q·N_Q.</li>
          <li>Pilar → zapata: N_k = N_G + N_Q en la base del pilar.</li>
        </ul>
      </section>
    </div>
  );
}

function Results({ pid, ov }: { pid: string; ov: Overview }) {
  const [st, setSt] = useState("");
  const [ty, setTy] = useState("");
  const rows = ov.elements
    .filter((e) => !ty || e.type === ty)
    .flatMap((e) => Object.entries(e.calcs).map(([ct, c]) => ({ e, ct, c })))
    .filter((r) => r.c.status !== "no_aplica")
    .filter((r) => !st || r.c.status === st);
  const LABEL: Record<string, string> = {
    losa_flexion: "Flexión y cortante (m⁺)",
    losa_flexion_neg: "Flexión (m⁻)",
    viga_flexion: "Flexión ELU (M⁺)",
    viga_flexion_neg: "Flexión ELU (M⁻)",
    viga_cortante: "Cortante ELU",
    viga_fisuracion: "ELS fisuración",
    viga_flecha: "ELS deformaciones",
    pilar: "Flexocompresión ELU",
    zapata_terreno: "Presión sobre el terreno",
  };
  return (
    <section className="card">
      <div className="mb-3 flex flex-wrap items-end gap-2">
        <h2 className="h2 flex-1">Resultados y verificaciones ({rows.length})</h2>
        <select className="input w-40" value={ty} onChange={(e) => setTy(e.target.value)}>
          <option value="">Todos los tipos</option>
          {(["losa", "viga", "pilar", "zapata"] as ElementType[]).map((t) => (
            <option key={t} value={t}>
              {TYPE_LABEL[t]}
            </option>
          ))}
        </select>
        <select className="input w-44" value={st} onChange={(e) => setSt(e.target.value)}>
          <option value="">Todos los estados</option>
          {Object.entries(STATUS)
            .filter(([k]) => k !== "no_aplica")
            .map(([k, v]) => (
              <option key={k} value={k}>
                {v.label}
              </option>
            ))}
        </select>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
              <th className="py-1 pr-2 font-medium">Elemento</th>
              <th className="py-1 pr-2 font-medium">Cálculo</th>
              <th className="py-1 pr-2 font-medium">Estado</th>
              <th className="py-1 pr-2 font-medium">Resultado</th>
              <th className="py-1 font-medium">Resumen</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ e, ct, c }) => (
              <tr key={e.id + ct} className="border-b border-slate-100 align-top">
                <td className="py-1.5 pr-2">
                  <Link className="font-medium text-brand underline" to={`/p/${pid}/e/${e.id}`}>
                    {e.code}
                  </Link>
                </td>
                <td className="py-1.5 pr-2 text-xs">{LABEL[ct] ?? ct}</td>
                <td className="py-1.5 pr-2">
                  <StatusPill status={c.status} small />
                </td>
                <td className="py-1.5 pr-2">{c.status === "actual" ? <OkBadge ok={c.ok} /> : <span className="text-xs text-slate-400">—</span>}</td>
                <td className={`py-1.5 text-xs ${c.status === "actual" ? "" : "text-slate-400"}`}>
                  {c.status === "actual" ? c.texto : c.status === "desactualizado" ? <span className="line-through">{c.texto}</span> : c.status === "faltan_datos" ? e.missing.join("; ") : ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-[11px] text-slate-500">Los resultados desactualizados se muestran tachados: corresponden a datos de entrada anteriores y no son vigentes.</p>
      <p className="text-[11px] text-slate-500">Valores: {num(ov.summary.calcs.actual ?? 0, 0)} cálculos vigentes.</p>
    </section>
  );
}

function Sheets({ pid, setError }: { pid: string; ov: Overview; setError: (e: string | null) => void }) {
  const [tables, setTables] = useState<SummaryTable[] | null>(null);
  const [sel, setSel] = useState("armaduras");
  useEffect(() => {
    tablesApi(pid).then(setTables).catch((e) => setError(e.message));
  }, [pid, setError]);
  const t = tables?.find((x) => x.key === sel);
  return (
    <div className="space-y-4">
      <section className="card">
        <h2 className="h2 mb-2">Documentación del proyecto</h2>
        <div className="flex flex-wrap gap-2">
          <button className="btn-primary" onClick={() => sapi.downloadPdf(pid).catch((e) => setError(e.message))}>
            Memoria resumen (PDF)
          </button>
          <button className="btn-secondary" onClick={() => sapi.downloadExcel(pid).catch((e) => setError(e.message))}>
            Planilla de datos y resultados (Excel)
          </button>
        </div>
        <p className="mt-2 text-xs text-slate-500">
          Los informes identifican proyecto, fecha, unidades, norma y estado de validación. Los informes por elemento (ficha PDF e informe de
          cálculo completo) se emiten desde la ficha de cada elemento; el informe de cálculo solo se emite para resultados vigentes.
        </p>
      </section>
      <section className="card">
        <div className="mb-2 flex flex-wrap gap-1">
          {tables?.map((x) => (
            <button key={x.key} className={`rounded-md px-2.5 py-1 text-xs ${sel === x.key ? "bg-brand text-white" : "bg-slate-100 text-slate-700"}`} onClick={() => setSel(x.key)}>
              {x.title} ({x.rows.length})
            </button>
          ))}
        </div>
        {t && (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="bg-slate-50">
                <tr>
                  {t.headers.map((h) => (
                    <th key={h} className="px-2 py-1.5 text-left font-medium text-slate-600">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {t.rows.map((r, i) => (
                  <tr key={i} className="border-t border-slate-100">
                    {r.map((v, j) => (
                      <td key={j} className="px-2 py-1 whitespace-nowrap">
                        {typeof v === "number" ? num(v) : (v ?? "—")}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
