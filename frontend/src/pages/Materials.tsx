import { useEffect, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api/client";
import { ErrorBox, PageHeader, SelectField, StatusBadge, fmt } from "../components/ui";
import { useAppState } from "../state/AppState";

type Pt = { eps_permil: number; sigma: number };

function Curve({ title, series, xLabel }: { title: string; series: { name: string; data: Pt[]; color: string }[]; xLabel: string }) {
  return (
    <div className="card">
      <h3 className="mb-2 text-sm font-semibold">{title}</h3>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart margin={{ top: 5, right: 16, bottom: 20, left: 4 }}>
            <CartesianGrid stroke="#e2e8f0" />
            <XAxis type="number" dataKey="eps_permil" tickFormatter={(v) => fmt(v, 1)} label={{ value: xLabel, position: "insideBottom", offset: -10, fontSize: 11 }} fontSize={11} />
            <YAxis type="number" fontSize={11} label={{ value: "σ [MPa]", angle: -90, position: "insideLeft", fontSize: 11 }} />
            <Tooltip formatter={(v: number) => fmt(v, 2) + " MPa"} labelFormatter={(l) => `ε = ${fmt(Number(l), 3)} ‰`} />
            <Legend verticalAlign="top" height={24} wrapperStyle={{ fontSize: 11 }} />
            {series.map((s) => (
              <Line key={s.name} data={s.data} dataKey="sigma" name={s.name} stroke={s.color} dot={false} strokeWidth={2} isAnimationActive={false} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function Row({ k, v, ref_ }: { k: string; v: string; ref_?: string }) {
  return (
    <tr className="border-b border-slate-100">
      <td className="py-1 pr-2">{k}</td>
      <td className="py-1 pr-2 text-right font-mono">{v}</td>
      <td className="py-1 text-[11px] text-slate-500">{ref_}</td>
    </tr>
  );
}

export default function Materials() {
  const { overrides } = useAppState();
  const [cat, setCat] = useState<{ concrete_classes: string[]; steel_grades: string[] }>({ concrete_classes: [], steel_grades: [] });
  const [sel, setSel] = useState({ concrete_class: "C25/30", steel_grade: "B500S", steel_branch: "horizontal", situation: "persistente" });
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.catalog().then(setCat).catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    api
      .materials({ ...sel, parameter_overrides: overrides })
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e) => setError(e.message));
  }, [sel, overrides]);

  const c = data?.concrete;
  const s = data?.steel;
  return (
    <>
      <PageHeader title="Materiales" subtitle="Propiedades del hormigón (tabla 3.1, 3.1.6, 3.1.7) y del acero para armaduras pasivas (3.2.7), calculadas en el servidor con los parámetros normativos activos.">
        <StatusBadge status="pendiente_validacion" />
      </PageHeader>
      <div className="card mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <SelectField label="Hormigón" value={sel.concrete_class} options={cat.concrete_classes.map((x) => ({ value: x, label: x }))} onChange={(v) => setSel({ ...sel, concrete_class: v })} />
        <SelectField label="Acero" value={sel.steel_grade} options={cat.steel_grades.map((x) => ({ value: x, label: x }))} onChange={(v) => setSel({ ...sel, steel_grade: v })} />
        <SelectField
          label="Rama superior del acero"
          value={sel.steel_branch}
          options={[
            { value: "horizontal", label: "Horizontal" },
            { value: "inclinada", label: "Inclinada" },
          ]}
          onChange={(v) => setSel({ ...sel, steel_branch: v })}
        />
        <SelectField
          label="Situación"
          value={sel.situation}
          options={["persistente", "transitoria", "accidental"].map((x) => ({ value: x, label: x }))}
          onChange={(v) => setSel({ ...sel, situation: v })}
        />
      </div>
      <ErrorBox error={error} />
      {c && s && (
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="card overflow-x-auto">
            <h2 className="h2 mb-2">Hormigón {c.name}</h2>
            <table className="w-full text-sm">
              <tbody>
                <Row k="f_ck" v={`${fmt(c.fck)} MPa`} ref_="Tabla 3.1" />
                <Row k="f_cm = f_ck + 8" v={`${fmt(c.fcm)} MPa`} ref_="Tabla 3.1" />
                <Row k="f_ctm" v={`${fmt(c.fctm, 3)} MPa`} ref_="Tabla 3.1" />
                <Row k="f_ctk,0,05 / f_ctk,0,95" v={`${fmt(c.fctk_005, 3)} / ${fmt(c.fctk_095, 3)} MPa`} ref_="Tabla 3.1" />
                <Row k="E_cm" v={`${fmt(c.Ecm, 0)} MPa`} ref_="Tabla 3.1" />
                <Row k="ε_c1 / ε_cu1" v={`${fmt(c.eps_c1 * 1000, 3)} / ${fmt(c.eps_cu1 * 1000, 3)} ‰`} ref_="Tabla 3.1" />
                <Row k="ε_c2 / ε_cu2 / n" v={`${fmt(c.eps_c2 * 1000, 3)} / ${fmt(c.eps_cu2 * 1000, 3)} ‰ / ${fmt(c.n, 3)}`} ref_="Tabla 3.1" />
                <Row k="ε_c3 / ε_cu3" v={`${fmt(c.eps_c3 * 1000, 3)} / ${fmt(c.eps_cu3 * 1000, 3)} ‰`} ref_="Tabla 3.1" />
                <Row k="γ_c · α_cc · α_ct" v={`${fmt(c.gamma_c)} · ${fmt(c.alpha_cc)} · ${fmt(c.alpha_ct)}`} ref_="2.4.2.4; 3.1.6" />
                <Row k="f_cd = α_cc·f_ck/γ_c" v={`${fmt(c.fcd, 3)} MPa`} ref_="3.1.6 (3.15)" />
                <Row k="f_ctd = α_ct·f_ctk,0,05/γ_c" v={`${fmt(c.fctd, 3)} MPa`} ref_="3.1.6 (3.16)" />
                <Row k="λ / η (bloque rectangular)" v={`${fmt(c.lambda, 3)} / ${fmt(c.eta, 3)}`} ref_="3.1.7(3)" />
              </tbody>
            </table>
          </div>
          <div className="card overflow-x-auto">
            <h2 className="h2 mb-2">Acero {s.name}</h2>
            <table className="w-full text-sm">
              <tbody>
                <Row k="f_yk" v={`${fmt(s.fyk)} MPa`} />
                <Row k="ε_uk / k = (f_t/f_y)_k" v={`${fmt(s.eps_uk * 100, 2)} % / ${fmt(s.k, 2)}`} ref_="Pendiente de verificación" />
                <Row k="E_s" v={`${fmt(s.Es, 0)} MPa`} ref_="3.2.7(4)" />
                <Row k="γ_s" v={fmt(s.gamma_s)} ref_="2.4.2.4" />
                <Row k="f_yd = f_yk/γ_s" v={`${fmt(s.fyd, 3)} MPa`} ref_="3.2.7(2)" />
                <Row k="ε_yd = f_yd/E_s" v={`${fmt(s.eps_yd * 1000, 3)} ‰`} ref_="3.2.7(2)" />
                <Row k="ε_ud" v={s.eps_ud ? `${fmt(s.eps_ud * 1000, 2)} ‰` : "sin límite (rama horizontal)"} ref_="3.2.7(2)" />
              </tbody>
            </table>
            <ul className="mt-2 text-[11px] text-amber-800">
              {(data.notes as string[]).map((n) => (
                <li key={n}>⚠ {n}</li>
              ))}
            </ul>
          </div>
          <Curve
            title="Hormigón: diagramas tensión-deformación"
            xLabel="ε_c [‰] (acortamiento)"
            series={[
              { name: "Cálculo de secciones: parábola-rectángulo (3.17)", data: data.curves.concrete_design, color: "#1f3a5f" },
              { name: "Análisis estructural no lineal (3.14), valores medios", data: data.curves.concrete_nonlinear, color: "#c8892a" },
            ]}
          />
          <Curve title="Acero: diagrama de cálculo (3.2.7)" xLabel="ε_s [‰]" series={[{ name: "Diagrama de cálculo", data: data.curves.steel_design, color: "#b03a2e" }]} />
        </div>
      )}
    </>
  );
}
