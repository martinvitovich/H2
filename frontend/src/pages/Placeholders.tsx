import { Link } from "react-router-dom";
import { NotAvailable, PageHeader, StatusBadge } from "../components/ui";
import type { ModuleInfo } from "../types";

export function Slabs() {
  return (
    <>
      <PageHeader title="Losas" subtitle="Cálculo de losas de hormigón armado." />
      <NotAvailable
        title="Losas"
        planned={[
          "Flexión por unidad de ancho en losas unidireccionales (reutilizando el motor de flexión).",
          "Disposiciones constructivas de losas (9.3).",
          "Punzonamiento (6.4).",
          "Flechas mediante el módulo de ELS — deformaciones.",
        ]}
      />
    </>
  );
}

export function ELU({ modules }: { modules: ModuleInfo[] }) {
  const st = (id: string) => modules.find((m) => m.id === id)?.status ?? "no_disponible";
  const rows: { id: string; name: string; ref: string; link: string | null }[] = [
    { id: "vigas_flexion", name: "Flexión simple (vigas)", ref: "6.1", link: "/vigas" },
    { id: "vigas_cortante", name: "Cortante y cercos (vigas)", ref: "6.2, 9.2.2", link: "/vigas?calc=cortante" },
    { id: "pilares", name: "Flexocompresión y segundo orden (pilares)", ref: "6.1, 5.2, 5.8, 9.5", link: "/pilares" },
  ];
  return (
    <>
      <PageHeader title="Estados Límite Últimos (ELU)" subtitle="Resumen de las comprobaciones en ELU disponibles." />
      <div className="card divide-y divide-slate-100">
        {rows.map((r) => (
          <div key={r.id} className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="font-medium">{r.name}</div>
              <div className="text-xs text-slate-500">Anejo 19, {r.ref}</div>
            </div>
            <div className="flex items-center gap-3">
              <StatusBadge status={st(r.id)} />
              {r.link && st(r.id) !== "no_disponible" && (
                <Link to={r.link} className="btn-primary">
                  Abrir
                </Link>
              )}
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
