import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { downloadBlob } from "../api/client";
import { ErrorBox, PageHeader } from "../components/ui";
import { sapi } from "../estructura/api";
import type { ProjectListItem } from "../estructura/types";
import { useSchema } from "../estructura/ui";

const TEMPLATES: Record<string, { label: string; levels: { code: string; name: string; elevation_m: number; height_m: number }[] }> = {
  vacio: { label: "Sin niveles", levels: [] },
  vivienda1: { label: "Vivienda de una planta", levels: [{ code: "N100", name: "Cubierta", elevation_m: 3, height_m: 3 }] },
  vivienda2: {
    label: "Vivienda de dos plantas",
    levels: [
      { code: "N100", name: "Forjado planta alta", elevation_m: 3, height_m: 3 },
      { code: "N200", name: "Cubierta", elevation_m: 5.8, height_m: 2.8 },
    ],
  },
};

export default function ProjectsPanel() {
  const [list, setList] = useState<ProjectListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [showArchived, setShowArchived] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", location: "", client: "", project_date: new Date().toISOString().slice(0, 10), structural_system: "Pórticos de hormigón armado con losas macizas", template: "vivienda2", concrete_class: "C25/30", steel_grade: "B500S" });
  const [creating, setCreating] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const nav = useNavigate();
  const schema = useSchema();

  const refresh = () =>
    sapi
      .list()
      .then((l) => {
        setList(l);
        setError(null);
      })
      .catch((e) => setError(e.message));
  useEffect(() => {
    refresh();
  }, []);

  const shown = useMemo(
    () =>
      (list ?? [])
        .filter((p) => showArchived || p.status !== "archivado")
        .filter((p) => !q || `${p.name} ${p.location} ${p.client} ${p.description}`.toLowerCase().includes(q.toLowerCase())),
    [list, q, showArchived],
  );

  async function create() {
    if (!form.name.trim()) return setError("Indique un nombre para el proyecto.");
    try {
      const o = await sapi.create({
        name: form.name.trim(),
        description: form.description,
        location: form.location,
        client: form.client,
        project_date: form.project_date,
        structural_system: form.structural_system,
        settings: { concrete_class: form.concrete_class, steel_grade: form.steel_grade },
        levels: TEMPLATES[form.template].levels,
      });
      nav(`/p/${o.project.id}/resumen`);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function act(fn: () => Promise<unknown>) {
    try {
      await fn();
    } catch (e) {
      setError((e as Error).message);
    }
    await refresh();
  }
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value });
  const opts = (key: string) => schema?.settings.find((f) => f.key === key)?.options ?? [];

  return (
    <div>
      <PageHeader title="Proyectos" subtitle="Proyectos estructurales integrales: datos generales, niveles, losas, vigas, pilares y fundaciones relacionados, con sus cargas, resultados y control de cambios. Los datos se guardan automáticamente en la base de datos del servidor.">
        <button className="btn-primary" onClick={() => setCreating(!creating)}>
          + Nuevo proyecto
        </button>
        <button className="btn-secondary" onClick={() => fileRef.current?.click()}>
          Importar JSON
        </button>
        <input
          ref={fileRef}
          type="file"
          accept="application/json,.json"
          className="hidden"
          onChange={async (e) => {
            const f = e.target.files?.[0];
            e.target.value = "";
            if (!f) return;
            try {
              const o = await sapi.importJson(JSON.parse(await f.text()));
              nav(`/p/${o.project.id}/resumen`);
            } catch (err) {
              setError(`No se pudo importar: ${(err as Error).message}`);
            }
          }}
        />
      </PageHeader>
      <ErrorBox error={error} />
      {creating && (
        <section className="card mb-4">
          <h2 className="h2 mb-3">Nuevo proyecto</h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <label className="block">
              <span className="label">Nombre *</span>
              <input className="input" value={form.name} onChange={set("name")} placeholder="Vivienda unifamiliar …" />
            </label>
            <label className="block">
              <span className="label">Ubicación</span>
              <input className="input" value={form.location} onChange={set("location")} />
            </label>
            <label className="block">
              <span className="label">Cliente (opcional)</span>
              <input className="input" value={form.client} onChange={set("client")} />
            </label>
            <label className="block">
              <span className="label">Fecha</span>
              <input className="input" type="date" value={form.project_date} onChange={set("project_date")} />
            </label>
            <label className="block sm:col-span-2">
              <span className="label">Sistema estructural</span>
              <input className="input" value={form.structural_system} onChange={set("structural_system")} />
            </label>
            <label className="block sm:col-span-2 lg:col-span-3">
              <span className="label">Descripción</span>
              <textarea className="input h-16" value={form.description} onChange={set("description")} />
            </label>
            <label className="block">
              <span className="label">Hormigón</span>
              <select className="input" value={form.concrete_class} onChange={set("concrete_class")}>
                {opts("concrete_class").map((o) => (
                  <option key={o.value}>{o.value}</option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="label">Acero</span>
              <select className="input" value={form.steel_grade} onChange={set("steel_grade")}>
                {opts("steel_grade").map((o) => (
                  <option key={o.value}>{o.value}</option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="label">Niveles iniciales</span>
              <select className="input" value={form.template} onChange={set("template")}>
                {Object.entries(TEMPLATES).map(([k, t]) => (
                  <option key={k} value={k}>
                    {t.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <p className="mt-2 text-[11px] text-slate-500">
            Norma: Código Estructural, Anejo 19. El resto de datos (acciones, recubrimientos, exposición, terreno) se completan en el proyecto.
          </p>
          <div className="mt-3 flex gap-2">
            <button className="btn-primary" onClick={create}>
              Crear y abrir
            </button>
            <button className="btn-secondary" onClick={() => setCreating(false)}>
              Cancelar
            </button>
          </div>
        </section>
      )}
      <section className="card">
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <input className="input w-64" placeholder="Buscar proyecto…" value={q} onChange={(e) => setQ(e.target.value)} />
          <label className="flex items-center gap-1.5 text-sm">
            <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} /> Mostrar archivados
          </label>
          <span className="flex-1" />
          <Link className="text-xs text-brand underline" to="/proyectos/calculos">
            Cálculos independientes de las calculadoras →
          </Link>
        </div>
        {list === null && !error && <p className="text-sm text-slate-500">Cargando…</p>}
        {list && shown.length === 0 && <p className="text-sm text-slate-500">No hay proyectos{q ? " que coincidan" : ""}. Cree uno nuevo para empezar.</p>}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            {shown.length > 0 && (
              <thead>
                <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                  <th className="py-1.5 pr-3 font-medium">Proyecto</th>
                  <th className="py-1.5 pr-3 font-medium">Elementos</th>
                  <th className="py-1.5 pr-3 font-medium">Estado de cálculo</th>
                  <th className="py-1.5 pr-3 font-medium">Última modificación</th>
                  <th />
                </tr>
              </thead>
            )}
            <tbody>
              {shown.map((p) => {
                const s = p.summary.by_status;
                const pend = p.summary.n_elements - (s.actual ?? 0) - (s.no_aplica ?? 0);
                return (
                  <tr key={p.id} className="border-b border-slate-100 align-top">
                    <td className="py-2 pr-3">
                      <Link className="font-medium text-brand underline" to={`/p/${p.id}/resumen`}>
                        {p.name}
                      </Link>
                      {p.status === "archivado" && <span className="ml-2 rounded bg-slate-200 px-1.5 py-0.5 text-[10px]">Archivado</span>}
                      <div className="text-xs text-slate-500">{[p.location, p.client, p.project_date].filter(Boolean).join(" · ")}</div>
                      {p.n_documents > 0 && <div className="text-[11px] text-slate-400">{p.n_documents} cálculos independientes</div>}
                    </td>
                    <td className="py-2 pr-3 text-xs whitespace-nowrap">
                      {p.counts.losa} losas · {p.counts.viga} vigas
                      <br />
                      {p.counts.pilar} pilares · {p.counts.zapata} zapatas
                    </td>
                    <td className="py-2 pr-3 text-xs">
                      {p.summary.n_elements === 0 ? (
                        <span className="text-slate-400">Sin elementos</span>
                      ) : pend === 0 ? (
                        <span className="text-emerald-700">Todos actualizados{p.summary.by_compliance.no_cumple ? ` · ${p.summary.by_compliance.no_cumple} no cumplen` : ""}</span>
                      ) : (
                        <span className="text-amber-800">
                          {pend} de {p.summary.n_elements} pendientes
                          {s.desactualizado ? ` · ${s.desactualizado} desactualizados` : ""}
                        </span>
                      )}
                    </td>
                    <td className="py-2 pr-3 text-xs whitespace-nowrap text-slate-600">{new Date(p.modified).toLocaleString("es-ES")}</td>
                    <td className="py-2 text-right whitespace-nowrap">
                      <Link className="btn-primary px-2 py-1 text-xs" to={`/p/${p.id}/resumen`}>
                        Abrir
                      </Link>{" "}
                      <button className="btn-secondary px-2 py-1 text-xs" onClick={() => act(() => sapi.duplicate(p.id, `${p.name} (copia)`))}>
                        Duplicar
                      </button>{" "}
                      <button className="btn-secondary px-2 py-1 text-xs" onClick={() => act(() => sapi.archive(p.id, p.status !== "archivado"))}>
                        {p.status === "archivado" ? "Reactivar" : "Archivar"}
                      </button>{" "}
                      <button
                        className="btn-secondary px-2 py-1 text-xs"
                        onClick={() =>
                          act(async () => {
                            const data = await sapi.exportJson(p.id);
                            downloadBlob(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }), `${p.name.replace(/[^A-Za-z0-9_-]+/g, "_")}.json`);
                          })
                        }
                      >
                        JSON
                      </button>{" "}
                      <button
                        className="btn-secondary px-2 py-1 text-xs text-red-700"
                        onClick={() => {
                          if (prompt(`Para eliminar definitivamente «${p.name}» escriba su nombre:`) === p.name) act(() => sapi.remove(p.id));
                        }}
                      >
                        Eliminar
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
