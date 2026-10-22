import { Link } from "react-router-dom";
import { PageHeader, StatusBadge } from "../components/ui";
import type { ModuleInfo } from "../types";

export function ELU({ modules }: { modules: ModuleInfo[] }) {
  const st = (id: string) => modules.find((m) => m.id === id)?.status ?? "no_disponible";
  const rows: { id: string; name: string; ref: string; link: string | null }[] = [
    { id: "vigas_flexion", name: "Flexión simple (vigas)", ref: "6.1", link: "/vigas" },
    { id: "vigas_cortante", name: "Cortante y cercos (vigas)", ref: "6.2, 9.2.2", link: "/vigas?calc=cortante" },
    { id: "pilares", name: "Flexocompresión y segundo orden (pilares)", ref: "6.1, 5.2, 5.8, 9.5", link: "/pilares" },
    { id: "losas", name: "Losas macizas unidireccionales (flexión y cortante)", ref: "9.3, 6.1, 6.2.2", link: "/losas" },
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
