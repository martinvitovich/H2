import type { LayerIn } from "../types";

export const DIAMETERS = [6, 8, 10, 12, 14, 16, 20, 25, 32, 40];

export function LayersEditor({ layers, onChange }: { layers: LayerIn[]; onChange: (l: LayerIn[]) => void }) {
  const set = (i: number, patch: Partial<LayerIn>) => onChange(layers.map((l, j) => (j === i ? { ...l, ...patch } : l)));
  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-slate-500">
              <th className="pb-1 font-medium">Cara</th>
              <th className="pb-1 font-medium">N.º barras</th>
              <th className="pb-1 font-medium">φ [mm]</th>
              <th className="pb-1 font-medium" title="Distancia desde la cara al centro de las barras; vacío = automática">
                Prof. [mm]
              </th>
              <th />
            </tr>
          </thead>
          <tbody>
            {layers.map((l, i) => (
              <tr key={i}>
                <td className="pr-1 pb-1">
                  <select className="input min-w-[96px]" value={l.face} onChange={(e) => set(i, { face: e.target.value as LayerIn["face"] })}>
                    <option value="inferior">inferior</option>
                    <option value="superior">superior</option>
                  </select>
                </td>
                <td className="pr-1 pb-1">
                  <input className="input min-w-[56px]" type="number" min={1} max={30} value={l.n} onChange={(e) => set(i, { n: Number(e.target.value) })} />
                </td>
                <td className="pr-1 pb-1">
                  <select className="input min-w-[60px]" value={l.diameter} onChange={(e) => set(i, { diameter: Number(e.target.value) })}>
                    {DIAMETERS.map((d) => (
                      <option key={d} value={d}>
                        {d}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="pr-1 pb-1">
                  <input
                    className="input min-w-[64px]"
                    type="number"
                    placeholder="auto"
                    value={l.depth ?? ""}
                    onChange={(e) => set(i, { depth: e.target.value === "" ? null : Number(e.target.value) })}
                  />
                </td>
                <td className="pb-1">
                  <button className="btn-secondary px-2 py-1" onClick={() => onChange(layers.filter((_, j) => j !== i))} aria-label="Eliminar capa">
                    ✕
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <button className="btn-secondary mt-1 text-xs" onClick={() => onChange([...layers, { face: "inferior", n: 2, diameter: 16 }])}>
        + Añadir capa
      </button>
      <p className="mt-1 text-[11px] text-slate-500">
        Capas sucesivas de la misma cara se apilan hacia el interior con la separación libre mínima de 8.2(2).
      </p>
    </div>
  );
}
