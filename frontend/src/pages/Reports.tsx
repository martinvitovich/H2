import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, downloadBlob } from "../api/client";
import { ErrorBox, PageHeader } from "../components/ui";
import { useAppState } from "../state/AppState";
import type { FlexureRequest, Project } from "../types";

export default function Reports() {
  const { beam, overrides, activeProject } = useAppState();
  const [project, setProject] = useState<Project | null>(null);
  const [author, setAuthor] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    if (activeProject) api.project(activeProject.id).then(setProject).catch(() => setProject(null));
  }, [activeProject]);

  async function generate(req: FlexureRequest, key: string) {
    setBusy(key);
    setError(null);
    try {
      const blob = await api.flexureReport({ project_name: project?.name ?? activeProject?.name ?? "Sin proyecto", author, request: req });
      downloadBlob(blob, `informe_${req.element_name.replace(/[^A-Za-z0-9_-]+/g, "_")}.pdf`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  const currentReq: FlexureRequest = {
    ...beam,
    shape: beam.shape.kind === "rectangular" ? { kind: "rectangular", b: beam.shape.b, h: beam.shape.h } : { kind: "T", bf: beam.shape.bf, hf: beam.shape.hf, bw: beam.shape.bw, h: beam.shape.h },
    parameter_overrides: overrides,
  };

  return (
    <>
      <PageHeader title="Informes de cálculo" subtitle="Informes PDF generados en el servidor a partir del cálculo: identificación, norma y edición, datos y unidades, materiales, geometría, hipótesis, ecuaciones con sustituciones, resultados intermedios, armaduras, verificaciones, advertencias, fecha y versión del software." />
      <ErrorBox error={error} />
      <div className="mt-2 grid gap-4 lg:grid-cols-2">
        <section className="card space-y-3">
          <h2 className="h2">Viga actual (módulo Vigas)</h2>
          <p className="text-sm text-slate-600">
            {beam.element_name} · {beam.mode === "design" ? "dimensionado" : "comprobación"} · M_Ed = {beam.M_Ed_kNm} kN·m · {beam.concrete_class} · {beam.steel_grade}
          </p>
          <label className="block">
            <span className="label">Autor (opcional)</span>
            <input className="input" value={author} onChange={(e) => setAuthor(e.target.value)} />
          </label>
          <button className="btn-primary" disabled={busy !== null} onClick={() => generate(currentReq, "current")}>
            {busy === "current" ? "Generando…" : "Generar informe PDF"}
          </button>
          <p className="text-[11px] text-slate-500">
            Para modificar los datos, vaya a{" "}
            <Link className="text-brand underline" to="/vigas">
              Vigas
            </Link>
            .
          </p>
        </section>
        <section className="card">
          <h2 className="h2 mb-2">Elementos del proyecto activo</h2>
          {!project ? (
            <p className="text-sm text-slate-500">
              No hay un proyecto abierto.{" "}
              <Link to="/proyectos" className="text-brand underline">
                Abrir proyecto
              </Link>
            </p>
          ) : project.elements.length === 0 ? (
            <p className="text-sm text-slate-500">El proyecto «{project.name}» no tiene elementos.</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {project.elements.map((el, i) => (
                <li key={el.id ?? i} className="flex items-center justify-between py-2">
                  <span className="text-sm">
                    {el.name} <span className="text-xs text-slate-500">· M_Ed = {el.input.M_Ed_kNm} kN·m</span>
                  </span>
                  <button className="btn-secondary text-xs" disabled={busy !== null} onClick={() => generate({ ...el.input, parameter_overrides: project.parameter_overrides }, el.id ?? String(i))}>
                    {busy === (el.id ?? String(i)) ? "Generando…" : "PDF"}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </>
  );
}
