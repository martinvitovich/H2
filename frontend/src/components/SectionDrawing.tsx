import type { Bar, ShapeIn, Verification } from "../types";
import { fmt } from "./ui";

/** Dibujo a escala de la sección transversal. Refleja exactamente los datos recibidos
 * (geometría y posiciones de barras calculadas en el backend). */
export function SectionDrawing({
  shape,
  bars,
  cover,
  verification,
}: {
  shape: ShapeIn;
  bars: Bar[];
  cover?: number;
  verification?: Verification | null;
}) {
  const h = shape.h;
  const B = shape.kind === "rectangular" ? shape.b ?? 0 : shape.bf ?? 0;
  if (!(h > 0 && B > 0)) return <div className="text-sm text-slate-500">Geometría no válida</div>;
  const strainW = verification ? 140 : 0;
  const pad = 46;
  const maxW = 300;
  const maxH = 340;
  const s = Math.min(maxW / B, maxH / h);
  const W = B * s + pad * 2 + strainW;
  const H = h * s + pad * 2;
  const X = (x: number) => pad + x * s;
  const Y = (y: number) => pad + y * s;

  let outline: string;
  if (shape.kind === "rectangular") {
    outline = `M${X(0)},${Y(0)} H${X(B)} V${Y(h)} H${X(0)} Z`;
  } else {
    const bf = shape.bf!, hf = shape.hf!, bw = shape.bw!;
    const x0 = (bf - bw) / 2;
    outline = `M${X(0)},${Y(0)} H${X(bf)} V${Y(hf)} H${X(x0 + bw)} V${Y(h)} H${X(x0)} V${Y(hf)} H${X(0)} Z`;
  }
  const bw = shape.kind === "rectangular" ? B : shape.bw!;
  const xw0 = (B - bw) / 2;

  // diagrama de deformaciones
  let strain = null;
  if (verification) {
    const sign = verification.sign;
    const xna = sign > 0 ? verification.x : h - verification.x; // posición de la fibra neutra (desde arriba)
    const ox = pad * 2 + B * s + 30;
    const epsTop = verification.eps_top;
    const yComp = sign > 0 ? 0 : h;
    const yFar = sign > 0 ? h : 0;
    const epsFar = (epsTop * (verification.x - h)) / verification.x; // acortamiento + en la fibra opuesta
    const maxE = Math.max(Math.abs(epsTop), Math.abs(epsFar));
    const k = 50 / maxE;
    strain = (
      <g fontSize={10}>
        <line x1={ox} x2={ox} y1={Y(0)} y2={Y(h)} stroke="#334155" />
        <polygon
          points={`${ox},${Y(yComp)} ${ox - epsTop * k},${Y(yComp)} ${ox},${Y(xna)}`}
          fill="#bfdbfe"
          stroke="#1d4ed8"
        />
        <polygon
          points={`${ox},${Y(xna)} ${ox - epsFar * k},${Y(yFar)} ${ox},${Y(yFar)}`}
          fill="#fecaca"
          stroke="#b91c1c"
        />
        <text x={ox - epsTop * k} y={Y(yComp) + (sign > 0 ? -6 : 14)} textAnchor="middle" fill="#1d4ed8">
          {fmt(epsTop * 1000, 2)}‰
        </text>
        <text x={ox - epsFar * k} y={Y(yFar) + (sign > 0 ? 14 : -6)} textAnchor="middle" fill="#b91c1c">
          {fmt(-epsFar * 1000, 2)}‰
        </text>
        <text x={ox + 4} y={Y(xna) - 3} fill="#334155">
          x = {fmt(verification.x, 1)}
        </text>
        <text x={ox - 40} y={H - 8} fill="#64748b">
          deformaciones
        </text>
      </g>
    );
  }

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full max-w-[520px]" role="img" aria-label="Sección transversal">
      <defs>
        <marker id="arr" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
          <path d="M0,0 L10,5 L0,10 z" fill="#64748b" />
        </marker>
      </defs>
      <path d={outline} fill="#e2e8f0" stroke="#1e293b" strokeWidth={1.5} />
      {cover !== undefined && cover > 0 && (
        <rect
          x={X(xw0 + cover)}
          y={Y(cover)}
          width={Math.max(bw - 2 * cover, 0) * s}
          height={Math.max(h - 2 * cover, 0) * s}
          fill="none"
          stroke="#94a3b8"
          strokeDasharray="4 3"
          rx={3}
        />
      )}
      {verification && (
        <line
          x1={X(0) - 8}
          x2={X(B) + 8}
          y1={Y(verification.sign > 0 ? verification.x : h - verification.x)}
          y2={Y(verification.sign > 0 ? verification.x : h - verification.x)}
          stroke="#7c3aed"
          strokeDasharray="6 4"
        />
      )}
      {bars.map((b, i) => (
        <circle key={i} cx={X(b.x)} cy={Y(b.y)} r={Math.max((b.diameter / 2) * s, 1.5)} fill="#b03a2e" stroke="#1e293b" strokeWidth={0.6} />
      ))}
      {/* cotas */}
      <g fontSize={11} fill="#475569">
        <line x1={X(0)} x2={X(B)} y1={Y(0) - 18} y2={Y(0) - 18} stroke="#64748b" markerStart="url(#arr)" markerEnd="url(#arr)" />
        <text x={X(B / 2)} y={Y(0) - 23} textAnchor="middle">
          {shape.kind === "rectangular" ? "b" : "b_f"} = {fmt(B, 0)}
        </text>
        <line x1={X(0) - 18} x2={X(0) - 18} y1={Y(0)} y2={Y(h)} stroke="#64748b" markerStart="url(#arr)" markerEnd="url(#arr)" />
        <text x={X(0) - 24} y={Y(h / 2)} textAnchor="middle" transform={`rotate(-90 ${X(0) - 24} ${Y(h / 2)})`}>
          h = {fmt(h, 0)}
        </text>
        {shape.kind === "T" && (
          <text x={X(B / 2)} y={Y(h) + 16} textAnchor="middle">
            b_w = {fmt(shape.bw, 0)} · h_f = {fmt(shape.hf, 0)}
          </text>
        )}
      </g>
      {strain}
    </svg>
  );
}
