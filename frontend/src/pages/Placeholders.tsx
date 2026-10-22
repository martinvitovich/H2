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

export function Columns() {
  return (
    <>
      <PageHeader title="Pilares" subtitle="Flexocompresión y efectos de segundo orden." />
      <NotAvailable
        title="Pilares — flexocompresión (fase 4)"
        planned={[
          "Diagramas de interacción N–M por compatibilidad de deformaciones (6.1).",
          "Esbeltez, longitud efectiva y efectos de segundo orden (5.8).",
          "Excentricidades e imperfecciones geométricas (5.2, 6.1(4)).",
          "No se declarará conforme un pilar si faltan datos de apoyo, longitud efectiva o excentricidades.",
        ]}
      />
    </>
  );
}

export function ELS() {
  return (
    <>
      <PageHeader title="Estados Límite de Servicio (ELS)" subtitle="Fisuración y deformaciones (apartado 7)." />
      <div className="grid gap-4 md:grid-cols-2">
        <NotAvailable
          title="Fisuración (fase 5)"
          planned={["Abertura característica de fisura w_k (7.3.4).", "Armadura mínima de fisuración (7.3.2).", "Comprobación frente al límite del proyecto."]}
        />
        <NotAvailable
          title="Deformaciones (fase 5)"
          planned={["Flechas con rigidez fisurada/no fisurada (7.4.3).", "Fluencia y retracción (3.1.4).", "Diferenciación entre estimación simplificada (7.4.2) y cálculo detallado."]}
        />
      </div>
    </>
  );
}

export function ELU({ modules }: { modules: ModuleInfo[] }) {
  const st = (id: string) => modules.find((m) => m.id === id)?.status ?? "no_disponible";
  const rows = [
    { id: "vigas_flexion", name: "Flexión simple (vigas)", ref: "6.1", link: "/vigas" },
    { id: "vigas_cortante", name: "Cortante y estribos", ref: "6.2", link: null },
    { id: "pilares", name: "Flexocompresión y segundo orden", ref: "6.1, 5.8", link: null },
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
