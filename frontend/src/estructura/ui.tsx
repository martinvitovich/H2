import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fmt } from "../components/ui";
import { sapi, type Affected } from "./api";
import type { CalcStatus, ElementType, FieldDef, Schema } from "./types";

let schemaCache: Promise<Schema> | null = null;
export function useSchema(): Schema | null {
  const [s, setS] = useState<Schema | null>(null);
  useEffect(() => {
    if (!schemaCache) schemaCache = sapi.schema().catch((e) => {
      schemaCache = null;
      throw e;
    });
    schemaCache.then(setS).catch(() => setS(null));
  }, []);
  return s;
}

export const TYPE_LABEL: Record<ElementType, string> = { losa: "Losa", viga: "Viga", pilar: "Pilar", zapata: "Zapata" };
export const TYPE_PLURAL: Record<ElementType, string> = { losa: "Losas", viga: "Vigas", pilar: "Pilares", zapata: "Fundaciones" };
export const TAB_OF_TYPE: Record<ElementType, string> = { losa: "losas", viga: "vigas", pilar: "pilares", zapata: "fundaciones" };

export const STATUS: Record<CalcStatus, { label: string; cls: string }> = {
  actual: { label: "Actualizado", cls: "bg-emerald-50 text-emerald-800 ring-emerald-200" },
  desactualizado: { label: "Desactualizado", cls: "bg-orange-50 text-orange-800 ring-orange-300" },
  sin_calcular: { label: "Sin calcular", cls: "bg-slate-100 text-slate-700 ring-slate-200" },
  faltan_datos: { label: "Faltan datos", cls: "bg-amber-50 text-amber-800 ring-amber-200" },
  error: { label: "Error de cálculo", cls: "bg-red-50 text-red-800 ring-red-200" },
  error_datos: { label: "Error en los datos", cls: "bg-red-50 text-red-800 ring-red-200" },
  no_aplica: { label: "No aplica", cls: "bg-slate-50 text-slate-500 ring-slate-200" },
};

export function StatusPill({ status, small }: { status: CalcStatus; small?: boolean }) {
  const s = STATUS[status] ?? { label: status, cls: "bg-slate-100" };
  return (
    <span className={`inline-flex items-center whitespace-nowrap rounded-full px-2 py-0.5 font-medium ring-1 ${small ? "text-[10px]" : "text-[11px]"} ${s.cls}`}>
      {s.label}
    </span>
  );
}

export function ComplianceBadge({ c }: { c: "cumple" | "no_cumple" | "no_evaluable" | null | undefined }) {
  if (!c) return <span className="text-xs text-slate-400">—</span>;
  const m = {
    cumple: ["CUMPLE", "bg-emerald-50 text-emerald-700"],
    no_cumple: ["NO CUMPLE", "bg-red-50 text-red-700"],
    no_evaluable: ["NO EVALUABLE", "bg-amber-50 text-amber-700"],
  }[c];
  return <span className={`rounded px-1.5 py-0.5 text-[11px] font-semibold ${m[1]}`}>{m[0]}</span>;
}

export function OkBadge({ ok }: { ok: boolean | null | undefined }) {
  return <ComplianceBadge c={ok === true ? "cumple" : ok === false ? "no_cumple" : "no_evaluable"} />;
}

export function num(v: unknown, nd = 2): string {
  return typeof v === "number" ? fmt(v, nd) : v === null || v === undefined || v === "" ? "—" : String(v);
}

/** Editor de un campo escalar del esquema. Guarda al confirmar (blur / Enter / cambio en selects). */
export function FieldInput({
  f,
  value,
  onCommit,
  compact,
  disabled,
}: {
  f: FieldDef;
  value: any;
  onCommit: (v: any) => void;
  compact?: boolean;
  disabled?: boolean;
}) {
  const [txt, setTxt] = useState<string>(value === null || value === undefined ? "" : String(value));
  useEffect(() => setTxt(value === null || value === undefined ? "" : String(value)), [value]);
  const cls = `input ${compact ? "px-1.5 py-1 text-xs" : ""}`;
  if (f.kind === "bool")
    return <input type="checkbox" disabled={disabled} checked={!!value} onChange={(e) => onCommit(e.target.checked)} aria-label={f.label} />;
  if (f.kind === "select")
    return (
      <select className={cls} disabled={disabled} value={value ?? ""} onChange={(e) => onCommit(e.target.value)} aria-label={f.label}>
        {(f.options ?? []).map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    );
  const commit = () => {
    const cur = value === null || value === undefined ? "" : String(value);
    if (txt === cur) return;
    if (f.kind === "number" || f.kind === "int") {
      if (txt.trim() === "") return onCommit(null);
      const n = Number(txt.replace(",", "."));
      if (!Number.isFinite(n)) {
        setTxt(cur);
        return;
      }
      onCommit(f.kind === "int" ? Math.round(n) : n);
    } else onCommit(txt);
  };
  return (
    <input
      className={cls}
      disabled={disabled}
      inputMode={f.kind === "text" ? "text" : "decimal"}
      value={txt}
      placeholder={f.default === null || f.default === undefined ? "" : String(f.default)}
      onChange={(e) => setTxt(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === "Enter") (e.target as HTMLInputElement).blur();
        if (e.key === "Escape") setTxt(value === null || value === undefined ? "" : String(value));
      }}
      aria-label={f.label}
      title={f.help || f.label}
    />
  );
}

export function AffectedBanner({ pid, affected, onClose }: { pid: string; affected: Affected[] | null; onClose: () => void }) {
  if (!affected || affected.length === 0) return null;
  const stale = affected.filter((a) => a.status === "desactualizado");
  return (
    <div className="mb-3 flex items-start gap-3 rounded-md border border-orange-200 bg-orange-50 p-3 text-sm text-orange-900" role="status">
      <div className="flex-1">
        <b>Cambio guardado.</b> Elementos afectados por este cambio ({affected.length}):{" "}
        {affected.map((a, i) => (
          <span key={a.id}>
            {i > 0 && ", "}
            {a.id ? (
              <Link className="underline" to={`/p/${pid}/e/${a.id}`}>
                {a.code}
              </Link>
            ) : (
              <b>{a.code}</b>
            )}{" "}
            <span className="text-[11px]">({STATUS[a.status as CalcStatus]?.label ?? a.status})</span>
          </span>
        ))}
        .{" "}
        {stale.length > 0 && <>Sus resultados anteriores quedan marcados como desactualizados hasta que los recalcule.</>}
      </div>
      <button className="text-xs underline" onClick={onClose}>
        Cerrar
      </button>
    </div>
  );
}
