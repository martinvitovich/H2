import { Suspense, lazy, useEffect, useState } from "react";
import { NavLink, Route, Routes, useLocation } from "react-router-dom";
import { api } from "./api/client";
import { Disclaimer } from "./components/ui";
import { useAppState } from "./state/AppState";
import type { ModuleInfo, NormInfo } from "./types";
import Home from "./pages/Home";

const Materials = lazy(() => import("./pages/Materials"));
const Sections = lazy(() => import("./pages/Sections"));
const Beams = lazy(() => import("./pages/Beams"));
const Projects = lazy(() => import("./pages/Projects"));
const ProjectsPanel = lazy(() => import("./pages/ProjectsPanel"));
const Workspace = lazy(() => import("./pages/Workspace"));
const Reports = lazy(() => import("./pages/Reports"));
const NormConfig = lazy(() => import("./pages/NormConfig"));
const Columns = lazy(() => import("./pages/Columns"));
const ELS = lazy(() => import("./pages/ELS"));
const Slabs = lazy(() => import("./pages/Slabs"));
const ELU = lazy(() => import("./pages/Placeholders").then((m) => ({ default: m.ELU })));

const NAV = [
  { to: "/", label: "Inicio" },
  { to: "/proyectos", label: "Proyectos" },
  { to: "/materiales", label: "Materiales" },
  { to: "/secciones", label: "Secciones" },
  { to: "/vigas", label: "Vigas" },
  { to: "/losas", label: "Losas" },
  { to: "/pilares", label: "Pilares" },
  { to: "/elu", label: "Estados Límite Últimos (ELU)" },
  { to: "/els", label: "Estados Límite de Servicio (ELS)" },
  { to: "/proyectos/calculos", label: "Cálculos independientes" },
  { to: "/informes", label: "Informes de cálculo" },
  { to: "/normativa", label: "Configuración normativa" },
];

export interface AppInfo {
  version: string;
  norm: NormInfo;
  modules: ModuleInfo[];
}

export default function App() {
  const [open, setOpen] = useState(false);
  const [info, setInfo] = useState<AppInfo | null>(null);
  const [backendError, setBackendError] = useState<string | null>(null);
  const { activeProject } = useAppState();
  const loc = useLocation();

  useEffect(() => setOpen(false), [loc.pathname]);
  useEffect(() => {
    api
      .info()
      .then((i) => {
        setInfo(i);
        setBackendError(null);
      })
      .catch((e) => setBackendError(e.message));
  }, []);

  return (
    <div className="flex min-h-full">
      <aside
        className={`fixed inset-y-0 left-0 z-30 flex w-64 shrink-0 transform flex-col border-r border-slate-200 bg-white transition-transform lg:sticky lg:top-0 lg:h-screen lg:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex h-14 items-center gap-2 border-b border-slate-200 px-4">
          <img src="/favicon.svg" alt="" className="h-7 w-7" />
          <div>
            <div className="text-sm font-semibold">HA-Anejo19</div>
            <div className="text-[11px] text-slate-500">Hormigón armado · Código Estructural</div>
          </div>
        </div>
        <nav className="flex-1 space-y-0.5 overflow-y-auto p-2">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === "/"}
              className={({ isActive }) =>
                `block rounded-md px-3 py-1.5 text-sm ${isActive ? "bg-brand-soft font-medium text-brand" : "text-slate-700 hover:bg-slate-100"}`
              }
            >
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-slate-200 p-3">
          <Disclaimer />
          {info && <div className="mt-1 text-[11px] text-slate-400">v{info.version}</div>}
        </div>
      </aside>
      {open && <div className="fixed inset-0 z-20 bg-black/20 lg:hidden" onClick={() => setOpen(false)} />}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-10 flex h-14 items-center gap-3 border-b border-slate-200 bg-white/90 px-4 backdrop-blur">
          <button className="btn-secondary px-2 py-1 lg:hidden" onClick={() => setOpen(true)} aria-label="Abrir menú">
            ☰
          </button>
          <div className="min-w-0 flex-1 truncate text-xs text-slate-500">
            {info ? (
              <>
                <span className="font-medium text-slate-700">{info.norm.short ?? "Código Estructural, Anejo 19"}</span> ·{" "}
                <span className="hidden sm:inline">{info.norm.edition}</span>
              </>
            ) : (
              "Conectando con el servidor de cálculo…"
            )}
          </div>
          <div className="truncate text-xs text-slate-600">
            Proyecto: <span className="font-medium">{activeProject?.name ?? "ninguno"}</span>
          </div>
        </header>
        {backendError && (
          <div className="border-b border-red-200 bg-red-50 px-4 py-2 text-sm text-red-800">
            {backendError} Inicie la aplicación con <code className="font-mono">npm run dev</code> desde la raíz del repositorio.
          </div>
        )}
        <main className="mx-auto w-full max-w-7xl flex-1 p-4 sm:p-6">
          <Suspense fallback={<div className="text-sm text-slate-500">Cargando…</div>}>
          <Routes>
            <Route path="/" element={<Home info={info} />} />
            <Route path="/materiales" element={<Materials />} />
            <Route path="/secciones" element={<Sections />} />
            <Route path="/vigas" element={<Beams />} />
            <Route path="/losas" element={<Slabs />} />
            <Route path="/pilares" element={<Columns />} />
            <Route path="/elu" element={<ELU modules={info?.modules ?? []} />} />
            <Route path="/els" element={<ELS />} />
            <Route path="/proyectos" element={<ProjectsPanel />} />
            <Route path="/proyectos/calculos" element={<Projects />} />
            <Route path="/p/:pid" element={<Workspace />} />
            <Route path="/p/:pid/e/:eid" element={<Workspace />} />
            <Route path="/p/:pid/:tab" element={<Workspace />} />
            <Route path="/informes" element={<Reports />} />
            <Route path="/normativa" element={<NormConfig />} />
            <Route path="*" element={<div className="card">Página no encontrada.</div>} />
          </Routes>
          </Suspense>
        </main>
      </div>
    </div>
  );
}
