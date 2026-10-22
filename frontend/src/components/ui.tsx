import type { ReactNode } from "react";
import type { ModuleStatus } from "../types";

export function fmt(v: number | null | undefined, nd = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  if (v !== 0 && (Math.abs(v) >= 1e7 || Math.abs(v) < 1e-3)) return v.toExponential(nd).replace(".", ",");
  return v.toLocaleString("es-ES", { maximumFractionDigits: nd, minimumFractionDigits: 0 });
}

const STATUS: Record<ModuleStatus, { label: string; cls: string }> = {
  verificado: { label: "Implementado y verificado", cls: "bg-emerald-50 text-emerald-800 ring-emerald-200" },
  pendiente_validacion: {
    label: "Implementado · validación pendiente",
    cls: "bg-amber-50 text-amber-800 ring-amber-200",
  },
  no_disponible: { label: "No disponible", cls: "bg-slate-100 text-slate-600 ring-slate-200" },
};

export function StatusBadge({ status }: { status: ModuleStatus }) {
  const s = STATUS[status];
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ${s.cls}`}>
      {s.label}
    </span>
  );
}

const PARAM_STATUS: Record<string, { label: string; cls: string }> = {
  confirmado_fuente_secundaria: { label: "Confirmado (fuente secundaria)", cls: "bg-emerald-50 text-emerald-800" },
  pendiente_verificacion: { label: "Pendiente de verificación", cls: "bg-amber-50 text-amber-800" },
  definido_por_usuario: { label: "Definido por el usuario", cls: "bg-sky-50 text-sky-800" },
};

export function ParamStatus({ status }: { status: string }) {
  const s = PARAM_STATUS[status] ?? { label: status, cls: "bg-slate-100" };
  return <span className={`rounded px-1.5 py-0.5 text-[11px] font-medium ${s.cls}`}>{s.label}</span>;
}

export function PageHeader({ title, subtitle, children }: { title: string; subtitle?: string; children?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-ink sm:text-2xl">{title}</h1>
        {subtitle && <p className="mt-1 max-w-3xl text-sm text-slate-600">{subtitle}</p>}
      </div>
      {children && <div className="flex flex-wrap gap-2">{children}</div>}
    </div>
  );
}

export function NumberField(props: {
  label: string;
  value: number | undefined;
  onChange: (v: number) => void;
  unit?: string;
  step?: number;
  min?: number;
  max?: number;
  hint?: string;
}) {
  const { label, value, onChange, unit, step = 1, min, max, hint } = props;
  return (
    <label className="block">
      <span className="label">
        {label}
        {unit && <span className="ml-1 font-normal text-slate-400">[{unit}]</span>}
      </span>
      <input
        type="number"
        className="input"
        value={Number.isFinite(value) ? value : ""}
        step={step}
        min={min}
        max={max}
        onChange={(e) => onChange(e.target.value === "" ? NaN : Number(e.target.value))}
      />
      {hint && <span className="mt-0.5 block text-[11px] text-slate-500">{hint}</span>}
    </label>
  );
}

export function SelectField<T extends string | number>(props: {
  label: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
}) {
  return (
    <label className="block">
      <span className="label">{props.label}</span>
      <select
        className="input"
        value={String(props.value)}
        onChange={(e) => {
          const opt = props.options.find((o) => String(o.value) === e.target.value);
          if (opt) props.onChange(opt.value);
        }}
      >
        {props.options.map((o) => (
          <option key={String(o.value)} value={String(o.value)}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function ErrorBox({ error }: { error: string | null }) {
  if (!error) return null;
  return (
    <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm whitespace-pre-line text-red-800" role="alert">
      {error}
    </div>
  );
}

export function NotAvailable({ title, planned }: { title: string; planned: string[] }) {
  return (
    <div className="card">
      <div className="mb-2 flex items-center gap-2">
        <h2 className="h2">{title}</h2>
        <StatusBadge status="no_disponible" />
      </div>
      <p className="text-sm text-slate-600">
        Este módulo todavía no está implementado. No se ofrece ningún cálculo hasta que su
        procedimiento haya sido implementado y contrastado con el Anejo 19.
      </p>
      <h3 className="mt-3 text-xs font-semibold tracking-wide text-slate-500 uppercase">Alcance previsto</h3>
      <ul className="mt-1 list-disc pl-5 text-sm text-slate-700">
        {planned.map((p) => (
          <li key={p}>{p}</li>
        ))}
      </ul>
    </div>
  );
}

export function Disclaimer() {
  return (
    <p className="text-[11px] leading-snug text-slate-500">
      Herramienta de apoyo académico y profesional. Los resultados deben ser revisados de forma
      independiente por un ingeniero estructural responsable antes de su uso en un proyecto real.
    </p>
  );
}
