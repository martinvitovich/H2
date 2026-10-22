import { useEffect, useState } from "react";
import { api } from "../api/client";
import { LayersEditor } from "../components/LayersEditor";
import { SectionDrawing } from "../components/SectionDrawing";
import { ErrorBox, NumberField, PageHeader, SelectField, StatusBadge, fmt } from "../components/ui";
import { useAppState } from "../state/AppState";
import type { Geometry, LayerIn, ShapeIn } from "../types";

export default function Sections() {
  const { overrides } = useAppState();
  const [shape, setShape] = useState<ShapeIn>({ kind: "rectangular", b: 300, h: 500, bf: 800, hf: 120, bw: 300 });
  const [cover, setCover] = useState(30);
  const [st, setSt] = useState(8);
  const [dg, setDg] = useState(20);
  const [layers, setLayers] = useState<LayerIn[]>([
    { face: "inferior", n: 4, diameter: 20 },
    { face: "inferior", n: 2, diameter: 20 },
    { face: "superior", n: 2, diameter: 12 },
  ]);
  const [geom, setGeom] = useState<Geometry | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const t = setTimeout(() => {
      const s = shape.kind === "rectangular" ? { kind: shape.kind, b: shape.b, h: shape.h } : { kind: shape.kind, bf: shape.bf, hf: shape.hf, bw: shape.bw, h: shape.h };
      api
        .sectionProperties({ shape: s, cover, stirrup_diameter: st, dg, layers, parameter_overrides: overrides })
        .then((g) => {
          setGeom(g);
          setError(null);
        })
        .catch((e) => {
          setGeom(null);
          setError(e.message);
        });
    }, 200);
    return () => clearTimeout(t);
  }, [shape, cover, st, dg, layers, overrides]);

  return (
    <>
      <PageHeader title="Secciones" subtitle="Definición de la geometría y de las armaduras longitudinales. Las posiciones de las barras, las propiedades geométricas y las separaciones (8.2) se calculan en el servidor.">
        <StatusBadge status="pendiente_validacion" />
      </PageHeader>
      <div className="grid gap-4 lg:grid-cols-[minmax(320px,420px)_1fr]">
        <div className="card space-y-3">
          <SelectField
            label="Tipo"
            value={shape.kind}
            options={[
              { value: "rectangular", label: "Rectangular" },
              { value: "T", label: "En T" },
            ]}
            onChange={(v) => setShape({ ...shape, kind: v })}
          />
          <div className="grid grid-cols-2 gap-2">
            {shape.kind === "rectangular" ? (
              <NumberField label="b" unit="mm" value={shape.b} onChange={(v) => setShape({ ...shape, b: v })} />
            ) : (
              <>
                <NumberField label="b_f" unit="mm" value={shape.bf} onChange={(v) => setShape({ ...shape, bf: v })} />
                <NumberField label="h_f" unit="mm" value={shape.hf} onChange={(v) => setShape({ ...shape, hf: v })} />
                <NumberField label="b_w" unit="mm" value={shape.bw} onChange={(v) => setShape({ ...shape, bw: v })} />
              </>
            )}
            <NumberField label="h" unit="mm" value={shape.h} onChange={(v) => setShape({ ...shape, h: v })} />
            <NumberField label="c_nom" unit="mm" value={cover} onChange={setCover} />
            <NumberField label="φ estribo" unit="mm" value={st} onChange={setSt} />
            <NumberField label="d_g" unit="mm" value={dg} onChange={setDg} />
          </div>
          <LayersEditor layers={layers} onChange={setLayers} />
        </div>
        <div className="space-y-4">
          <ErrorBox error={error} />
          {geom && (
            <>
              <div className="card flex justify-center">
                <SectionDrawing shape={geom.shape} bars={geom.bars} cover={cover} />
              </div>
              <div className="card overflow-x-auto">
                <h2 className="h2 mb-2">Propiedades geométricas</h2>
                <table className="w-full text-sm">
                  <tbody className="font-mono">
                    <tr><td className="py-0.5 font-sans">Área bruta A_c</td><td className="text-right">{fmt(geom.Ac, 0)} mm²</td></tr>
                    <tr><td className="py-0.5 font-sans">C.d.g. desde la fibra superior y_g</td><td className="text-right">{fmt(geom.yg, 2)} mm</td></tr>
                    <tr><td className="py-0.5 font-sans">Inercia bruta I_g</td><td className="text-right">{fmt(geom.Ig, 3)} mm⁴</td></tr>
                    <tr><td className="py-0.5 font-sans">A_s inferior / superior</td><td className="text-right">{fmt(geom.As_inferior, 1)} / {fmt(geom.As_superior, 1)} mm²</td></tr>
                    <tr><td className="py-0.5 font-sans">d (armadura inferior)</td><td className="text-right">{fmt(geom.d_inferior, 1)} mm</td></tr>
                    <tr><td className="py-0.5 font-sans">d (armadura superior, momento negativo)</td><td className="text-right">{fmt(geom.d_superior, 1)} mm</td></tr>
                    <tr><td className="py-0.5 font-sans">Cuantía geométrica total A_s/A_c</td><td className="text-right">{fmt((geom.As_total / geom.Ac) * 1000, 3)} ‰</td></tr>
                  </tbody>
                </table>
                <h3 className="mt-3 text-xs font-semibold text-slate-500 uppercase">Separación libre mínima (8.2(2))</h3>
                <p className="font-mono text-xs">
                  {Object.entries(geom.min_clear_spacing).map(([d, s]) => `φ${d}: ${fmt(s, 1)} mm`).join(" · ")}
                </p>
                {geom.issues.length > 0 ? (
                  <ul className="mt-2 space-y-1 text-xs text-amber-800">
                    {geom.issues.map((i) => <li key={i}>⚠ {i}</li>)}
                  </ul>
                ) : (
                  <p className="mt-2 text-xs text-emerald-700">Separaciones y recubrimientos coherentes con los datos introducidos.</p>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </>
  );
}
