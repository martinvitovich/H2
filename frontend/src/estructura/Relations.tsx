import { useState } from "react";
import { Link } from "react-router-dom";
import { ErrorBox } from "../components/ui";
import { sapi, type Affected } from "./api";
import type { ElementRow, ElementType, LinkKind, Overview, Relation, Schema } from "./types";
import { FieldInput, TYPE_LABEL } from "./ui";

/** Relaciones que puede crear un elemento según su tipo y su papel (origen o destino de la carga). */
export const RELATION_OPTIONS: Record<ElementType, { kind: LinkKind; role: "source" | "target"; label: string; other: ElementType[] }[]> = {
  losa: [{ kind: "losa_viga", role: "source", label: "Transmite carga a la viga", other: ["viga"] }],
  viga: [
    { kind: "losa_viga", role: "target", label: "Recibe carga de la losa", other: ["losa"] },
    { kind: "viga_apoyo", role: "source", label: "Apoya en (pilar o viga)", other: ["pilar", "viga"] },
    { kind: "viga_apoyo", role: "target", label: "Recibe la viga apoyada", other: ["viga"] },
  ],
  pilar: [
    { kind: "viga_apoyo", role: "target", label: "Recibe la viga", other: ["viga"] },
    { kind: "pilar_pilar", role: "target", label: "Recibe el pilar superior", other: ["pilar"] },
    { kind: "pilar_pilar", role: "source", label: "Continúa en el pilar inferior", other: ["pilar"] },
    { kind: "pilar_zapata", role: "source", label: "Apoya en la zapata", other: ["zapata"] },
  ],
  zapata: [{ kind: "pilar_zapata", role: "target", label: "Recibe el pilar", other: ["pilar"] }],
};

export const KIND_LABEL: Record<LinkKind, string> = {
  losa_viga: "Losa → viga",
  viga_apoyo: "Viga → apoyo",
  pilar_pilar: "Pilar → pilar inferior",
  pilar_zapata: "Pilar → zapata",
};

function dataText(d: Record<string, any>): string {
  return Object.entries(d)
    .filter(([, v]) => v !== null && v !== "" && v !== undefined)
    .map(([k, v]) => `${k} = ${typeof v === "number" ? v.toLocaleString("es-ES") : v}`)
    .join("; ");
}

export function RelationsPanel({
  pid,
  el,
  relations,
  ov,
  schema,
  onChanged,
}: {
  pid: string;
  el: ElementRow;
  relations: Relation[];
  ov: Overview;
  schema: Schema;
  onChanged: (a: Affected[] | null) => Promise<void>;
}) {
  const opts = RELATION_OPTIONS[el.type];
  const [sel, setSel] = useState(0);
  const [other, setOther] = useState("");
  const [data, setData] = useState<Record<string, any>>({});
  const [error, setError] = useState<string | null>(null);
  const opt = opts[sel];
  const fields = schema.links[opt.kind];
  const candidates = ov.elements.filter((e) => opt.other.includes(e.type) && e.id !== el.id);

  async function add() {
    if (!other) return setError("Seleccione el elemento relacionado.");
    try {
      const b = opt.role === "source" ? { source_id: el.id, target_id: other } : { source_id: other, target_id: el.id };
      const r = await sapi.createLink(pid, { kind: opt.kind, ...b, data });
      setError(null);
      setOther("");
      setData({});
      await onChanged(r.affected);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="space-y-3">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
            <th className="py-1 pr-2 font-medium">Sentido</th>
            <th className="py-1 pr-2 font-medium">Elemento</th>
            <th className="py-1 pr-2 font-medium">Datos de la relación</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {relations.map((r) => (
            <RelationRow key={r.id} pid={pid} r={r} schema={schema} onChanged={onChanged} onError={setError} />
          ))}
          {relations.length === 0 && (
            <tr>
              <td colSpan={4} className="py-2 text-xs text-slate-500">
                Sin relaciones. Las cargas solo se transmiten a través de relaciones explícitas.
              </td>
            </tr>
          )}
        </tbody>
      </table>
      <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
        <div className="mb-2 text-xs font-semibold text-slate-600">Añadir relación</div>
        <div className="grid gap-2 sm:grid-cols-2">
          <label className="block">
            <span className="label">Tipo</span>
            <select
              className="input"
              value={sel}
              onChange={(e) => {
                setSel(Number(e.target.value));
                setOther("");
                setData({});
              }}
            >
              {opts.map((o, i) => (
                <option key={i} value={i}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="label">Elemento</span>
            <select className="input" value={other} onChange={(e) => setOther(e.target.value)}>
              <option value="">— seleccionar —</option>
              {candidates.map((c) => (
                <option key={c.id} value={c.id}>
                  {TYPE_LABEL[c.type]} {c.code}
                  {c.level_code ? ` (${c.level_code})` : ""}
                </option>
              ))}
            </select>
          </label>
          {fields
            .filter((f) => !(f.key === "posicion" && !(opt.kind === "viga_apoyo" && (opt.role === "target" || ov.elements.find((x) => x.id === other)?.type === "viga"))))
            .filter((f) => !(f.key === "area" && (data.metodo ?? "area") !== "area") && !(f.key === "ancho" && (data.metodo ?? "area") !== "ancho"))
            .map((f) => (
              <label key={f.key} className="block">
                <span className="label">
                  {f.label}
                  {f.unit && <span className="ml-1 font-normal text-slate-400">[{f.unit}]</span>}
                </span>
                <FieldInput f={f} value={data[f.key] ?? (f.kind === "select" ? f.default : null)} onCommit={(v) => setData({ ...data, [f.key]: v })} />
                {f.help && <span className="text-[11px] text-slate-500">{f.help}</span>}
              </label>
            ))}
        </div>
        <ErrorBox error={error} />
        <button className="btn-primary mt-2" onClick={add}>
          Añadir relación
        </button>
      </div>
    </div>
  );
}

function RelationRow({
  pid,
  r,
  schema,
  onChanged,
  onError,
}: {
  pid: string;
  r: Relation;
  schema: Schema;
  onChanged: (a: Affected[] | null) => Promise<void>;
  onError: (e: string | null) => void;
}) {
  const [edit, setEdit] = useState(false);
  const fields = schema.links[r.kind];
  return (
    <tr className="border-b border-slate-100 align-top">
      <td className="py-1.5 pr-2 text-xs">
        {r.direction === "entrada" ? "← recibe de" : "→ transmite a"}
        <div className="text-[11px] text-slate-500">{KIND_LABEL[r.kind]}</div>
      </td>
      <td className="py-1.5 pr-2">
        <Link className="font-medium text-brand underline" to={`/p/${pid}/e/${r.other_id}`}>
          {TYPE_LABEL[r.other_type]} {r.other_code}
        </Link>
      </td>
      <td className="py-1.5 pr-2 text-xs">
        {!edit && <span className="font-mono">{dataText(r.data) || "—"}</span>}
        {edit && (
          <div className="grid gap-1 sm:grid-cols-2">
            {fields.map((f) => (
              <label key={f.key} className="block">
                <span className="text-[11px] text-slate-500">
                  {f.label} {f.unit && `[${f.unit}]`}
                </span>
                <FieldInput
                  compact
                  f={f}
                  value={r.data[f.key]}
                  onCommit={async (v) => {
                    try {
                      const res = await sapi.patchLink(pid, r.id, { [f.key]: v });
                      onError(null);
                      await onChanged(res.affected);
                    } catch (e) {
                      onError((e as Error).message);
                    }
                  }}
                />
              </label>
            ))}
          </div>
        )}
      </td>
      <td className="py-1.5 whitespace-nowrap">
        {fields.length > 0 && (
          <button className="btn-secondary px-2 py-1 text-xs" onClick={() => setEdit(!edit)}>
            {edit ? "Hecho" : "Editar"}
          </button>
        )}{" "}
        <button
          className="btn-secondary px-2 py-1 text-xs text-red-700"
          onClick={async () => {
            if (!confirm(`¿Eliminar la relación con ${r.other_code}?`)) return;
            try {
              const res = await sapi.deleteLink(pid, r.id);
              onError(null);
              await onChanged(res.affected);
            } catch (e) {
              onError((e as Error).message);
            }
          }}
        >
          ✕
        </button>
      </td>
    </tr>
  );
}
