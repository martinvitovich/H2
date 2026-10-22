import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { PageHeader, StatusBadge } from "../components/ui";
import type { ProjectSummary } from "../types";
import type { AppInfo } from "../App";

const LINKS: Record<string, string> = {
  materiales: "/materiales",
  secciones: "/secciones",
  vigas_flexion: "/vigas",
  proyectos: "/proyectos",
  informes: "/informes",
};

export default function Home({ info }: { info: AppInfo | null }) {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  useEffect(() => {
    api.projects().then(setProjects).catch(() => setProjects([]));
  }, []);
  return (
    <>
      <PageHeader
        title="Cálculo de estructuras de hormigón armado"
        subtitle="Dimensionado y verificación según el Anejo 19 del Código Estructural (RD 470/2021). Los cálculos se ejecutan en el motor Python del servidor y cada resultado incluye su procedimiento, referencias y advertencias."
      >
        <Link to="/vigas" className="btn-primary">
          Nueva viga a flexión
        </Link>
        <Link to="/proyectos" className="btn-secondary">
          Proyectos
        </Link>
      </PageHeader>

      <div className="grid gap-4 lg:grid-cols-3">
        <section className="card lg:col-span-2">
          <h2 className="h2 mb-3">Módulos y estado de implementación</h2>
          <div className="divide-y divide-slate-100">
            {(info?.modules ?? []).map((m) => (
              <div key={m.id} className="flex flex-col gap-1 py-2.5 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0">
                  <div className="text-sm font-medium">{m.name}</div>
                  <div className="text-xs text-slate-500">{m.detail}</div>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <StatusBadge status={m.status} />
                  {m.status !== "no_disponible" && LINKS[m.id] && (
                    <Link to={LINKS[m.id]} className="text-xs font-medium text-brand hover:underline">
                      Abrir →
                    </Link>
                  )}
                </div>
              </div>
            ))}
            {!info && <p className="text-sm text-slate-500">Cargando estado de los módulos…</p>}
          </div>
          <p className="mt-3 text-xs text-slate-500">
            «Validación pendiente» significa que el método está implementado y superado por pruebas matemáticas
            internas, pero sus parámetros no se han cotejado todavía con el texto oficial del Anejo 19.
          </p>
        </section>

        <section className="card">
          <h2 className="h2 mb-3">Últimos proyectos</h2>
          {projects.length === 0 ? (
            <p className="text-sm text-slate-500">No hay proyectos guardados.</p>
          ) : (
            <ul className="space-y-2">
              {projects.slice(0, 6).map((p) => (
                <li key={p.id}>
                  <Link to={`/proyectos?id=${p.id}`} className="block rounded-md border border-slate-100 p-2 hover:bg-slate-50">
                    <div className="text-sm font-medium">{p.name}</div>
                    <div className="text-[11px] text-slate-500">
                      {p.n_elements} elemento(s) · {new Date(p.modified).toLocaleString("es-ES")}
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
          {info && (
            <div className="mt-4 rounded-md bg-brand-soft p-3 text-xs text-slate-700">
              <div className="font-semibold text-brand">Norma de referencia</div>
              <div>{info.norm.name}</div>
              <div className="mt-1 text-slate-500">{info.norm.edition}</div>
            </div>
          )}
        </section>
      </div>
    </>
  );
}
