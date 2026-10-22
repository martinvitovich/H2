import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { ErrorBox, PageHeader } from "../components/ui";
import { DEFAULT_BEAM, DEFAULT_COLUMN, DEFAULT_ELS, DEFAULT_SHEAR, DEFAULT_SLAB, useAppState } from "../state/AppState";
import type { Project, ProjectSummary } from "../types";

export default function Projects() {
  const { activeProject, setActiveProject, setBeam, setShear, setColumn, setEls, setSlab, setOverrides } = useAppState();
  const [list, setList] = useState<ProjectSummary[]>([]);
  const [current, setCurrent] = useState<Project | null>(null);
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [params] = useSearchParams();
  const nav = useNavigate();
  const fileRef = useRef<HTMLInputElement>(null);

  const refresh = () =>
    api
      .projects()
      .then(setList)
      .catch((e) => setError(e.message));

  useEffect(() => {
    refresh();
  }, []);
  useEffect(() => {
    const id = params.get("id") ?? activeProject?.id;
    if (id) open(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params]);

  async function open(id: string) {
    try {
      const p = await api.project(id);
      setCurrent(p);
      setActiveProject({ id: p.id, name: p.name });
      setOverrides(p.parameter_overrides ?? {});
      setError(null);
    } catch (e) {
      setError((e as Error).message);
      if (activeProject?.id === id) setActiveProject(null);
    }
  }

  async function create() {
    if (!name.trim()) return setError("Indique un nombre para el proyecto.");
    try {
      const p = await api.createProject({ name: name.trim(), description: desc, parameter_overrides: {}, elements: [] });
      setName("");
      setDesc("");
      await refresh();
      await open(p.id);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function remove(id: string) {
    if (!confirm("¿Eliminar definitivamente el proyecto?")) return;
    try {
      await api.deleteProject(id);
      if (activeProject?.id === id) setActiveProject(null);
      if (current?.id === id) setCurrent(null);
      refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function saveMeta() {
    if (!current) return;
    try {
      const p = await api.updateProject(current.id, { ...current });
      setCurrent(p);
      setActiveProject({ id: p.id, name: p.name });
      refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function removeElement(idx: number) {
    if (!current) return;
    const p = await api.updateProject(current.id, { ...current, elements: current.elements.filter((_, i) => i !== idx) });
    setCurrent(p);
  }

  function exportJson() {
    if (!current) return;
    const blob = new Blob([JSON.stringify(current, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${current.name.replace(/[^A-Za-z0-9_-]+/g, "_")}.ha19.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  async function importJson(f: File) {
    try {
      const data = JSON.parse(await f.text());
      const p = await api.importProject(data);
      await refresh();
      await open(p.id);
    } catch (e) {
      setError(e instanceof SyntaxError ? "El fichero no es un JSON válido." : (e as Error).message);
    }
  }

  return (
    <>
      <PageHeader title="Proyectos" subtitle="Los proyectos se guardan en el servidor local como ficheros JSON versionados (formato 1) e incluyen geometría, materiales, armaduras, solicitaciones y parámetros normativos.">
        <button className="btn-secondary" onClick={() => fileRef.current?.click()}>
          Importar JSON
        </button>
        <input ref={fileRef} type="file" accept=".json,application/json" className="hidden" onChange={(e) => e.target.files?.[0] && importJson(e.target.files[0])} />
      </PageHeader>
      <ErrorBox error={error} />
      <div className="mt-2 grid gap-4 lg:grid-cols-[360px_1fr]">
        <div className="space-y-4">
          <section className="card space-y-2">
            <h2 className="h2">Nuevo proyecto</h2>
            <input className="input" placeholder="Nombre" value={name} onChange={(e) => setName(e.target.value)} />
            <textarea className="input" placeholder="Descripción (opcional)" rows={2} value={desc} onChange={(e) => setDesc(e.target.value)} />
            <button className="btn-primary w-full" onClick={create}>
              Crear y abrir
            </button>
          </section>
          <section className="card">
            <h2 className="h2 mb-2">Proyectos guardados</h2>
            {list.length === 0 && <p className="text-sm text-slate-500">No hay proyectos.</p>}
            <ul className="divide-y divide-slate-100">
              {list.map((p) => (
                <li key={p.id} className="flex items-center justify-between gap-2 py-2">
                  <button className="min-w-0 text-left" onClick={() => open(p.id)}>
                    <div className={`truncate text-sm font-medium ${activeProject?.id === p.id ? "text-brand" : ""}`}>{p.name}</div>
                    <div className="text-[11px] text-slate-500">
                      {p.n_elements} elemento(s) · {new Date(p.modified).toLocaleString("es-ES")}
                    </div>
                  </button>
                  <button className="text-xs text-red-700 hover:underline" onClick={() => remove(p.id)}>
                    Eliminar
                  </button>
                </li>
              ))}
            </ul>
          </section>
        </div>
        <section className="card">
          {!current ? (
            <p className="text-sm text-slate-500">Seleccione o cree un proyecto.</p>
          ) : (
            <div className="space-y-3">
              <div className="grid gap-2 sm:grid-cols-2">
                <label>
                  <span className="label">Nombre</span>
                  <input className="input" value={current.name} onChange={(e) => setCurrent({ ...current, name: e.target.value })} />
                </label>
                <label>
                  <span className="label">Descripción</span>
                  <input className="input" value={current.description} onChange={(e) => setCurrent({ ...current, description: e.target.value })} />
                </label>
              </div>
              <div className="text-[11px] text-slate-500">
                Formato {current.format_version} · software {current.software_version} · {current.norm.name} · creado {new Date(current.created).toLocaleString("es-ES")}
              </div>
              <div className="text-[11px] text-slate-500">
                Parámetros normativos modificados: {Object.keys(current.parameter_overrides).length === 0 ? "ninguno" : JSON.stringify(current.parameter_overrides)}
              </div>
              <div className="flex flex-wrap gap-2">
                <button className="btn-primary" onClick={saveMeta}>
                  Guardar cambios
                </button>
                <button className="btn-secondary" onClick={exportJson}>
                  Exportar JSON
                </button>
                <button
                  className="btn-secondary"
                  onClick={() => {
                    setBeam({ ...DEFAULT_BEAM, element_name: `V-${current.elements.length + 1}` });
                    nav("/vigas");
                  }}
                >
                  + Nueva viga
                </button>
              </div>
              <h3 className="pt-2 text-sm font-semibold">Elementos</h3>
              {current.elements.length === 0 && <p className="text-sm text-slate-500">Sin elementos. Calcule una viga y pulse «Guardar en proyecto».</p>}
              <ul className="divide-y divide-slate-100">
                {current.elements.map((el, i) => (
                  <li key={el.id ?? i} className="flex flex-col gap-1 py-2 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <div className="text-sm font-medium">
                        {el.name}{" "}
                        <span className="text-xs font-normal text-slate-500">
                          ·{" "}
                          {el.type === "viga_flexion"
                            ? "flexión ELU"
                            : el.type === "viga_cortante"
                              ? "cortante ELU"
                              : el.type === "pilar"
                                ? "pilar"
                                : el.type === "losa"
                                  ? "losa"
                                : el.type === "els_fisuracion"
                                  ? "ELS fisuración"
                                  : "ELS deformaciones"}
                          {(el.type === "viga_flexion" || el.type === "viga_cortante") && ` · ${el.input.mode === "design" ? "dimensionado" : "comprobación"}`}
                        </span>
                      </div>
                      <div className="text-[11px] text-slate-500">
                        {el.type === "viga_flexion"
                          ? `M_Ed = ${el.input.M_Ed_kNm} kN·m · ${el.input.concrete_class} · ${el.input.steel_grade}`
                          : el.type === "viga_cortante"
                            ? `V_Ed = ${el.input.V_Ed_kN} kN · ${el.input.concrete_class} · cercos ${el.input.stirrup_grade}`
                            : el.type === "pilar"
                              ? `N_Ed = ${el.input.N_Ed_kN} kN · M02 = ${el.input.M02_kNm} kN·m · ${el.input.b}×${el.input.h} mm`
                              : el.type === "losa"
                                ? `m_Ed = ${el.input.m_Ed_kNm} kN·m/m · h = ${el.input.h} mm`
                              : `M_qp = ${el.input.M_qp_kNm} kN·m · ${el.input.concrete_class}`}
                        {el.result?.summary ? ` · ${el.result.summary}` : ""}
                        {el.result?.ok === true && " · cumple"}
                        {el.result?.ok === false && " · NO cumple"}
                      </div>
                    </div>
                    <div className="flex gap-3 text-xs">
                      <button
                        className="text-brand hover:underline"
                        onClick={() => {
                          if (el.type === "viga_flexion") {
                            setBeam({ ...DEFAULT_BEAM, ...el.input, shape: { ...DEFAULT_BEAM.shape, ...el.input.shape } });
                            nav("/vigas");
                          } else if (el.type === "viga_cortante") {
                            setShear({ ...DEFAULT_SHEAR, ...el.input, shape: { ...DEFAULT_SHEAR.shape, ...el.input.shape } });
                            nav("/vigas?calc=cortante");
                          } else if (el.type === "losa") {
                            setSlab({ ...DEFAULT_SLAB, ...el.input });
                            nav("/losas");
                          } else if (el.type === "pilar") {
                            setColumn({ ...DEFAULT_COLUMN, ...el.input });
                            nav("/pilares");
                          } else {
                            const inp = el.input;
                            const base = { ...DEFAULT_ELS, ...inp, shape: { ...DEFAULT_ELS.shape, ...inp.shape } };
                            if (el.type === "els_deformaciones") {
                              setEls({ ...base, M_qp_defl_kNm: inp.M_qp_kNm, M_qp_kNm: DEFAULT_ELS.M_qp_kNm });
                              nav("/els?calc=deformaciones");
                            } else {
                              setEls(base);
                              nav("/els");
                            }
                          }
                        }}
                      >
                        Abrir
                      </button>
                      <button className="text-red-700 hover:underline" onClick={() => removeElement(i)}>
                        Quitar
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      </div>
    </>
  );
}
