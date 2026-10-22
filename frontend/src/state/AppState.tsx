import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import type { ColumnRequest, ElsState, FlexureRequest, ShearRequest } from "../types";

/** Estado global de la interfaz. Solo datos de conveniencia del usuario (borradores y
 * parámetros editados); los cálculos se ejecutan siempre en el backend. */

export const DEFAULT_BEAM: FlexureRequest = {
  element_name: "V-1",
  mode: "design",
  shape: { kind: "rectangular", b: 300, h: 500, bf: 800, hf: 120, bw: 300 },
  cover: 30,
  stirrup_diameter: 8,
  dg: 20,
  concrete_class: "C25/30",
  steel_grade: "B500S",
  steel_branch: "horizontal",
  situation: "persistente",
  M_Ed_kNm: 150,
  assumed_bar_diameter: 16,
  layers: [
    { face: "inferior", n: 4, diameter: 16 },
    { face: "superior", n: 2, diameter: 12 },
  ],
  parameter_overrides: {},
  secondary_element: false,
  stirrup_spacing: 150,
};

export const DEFAULT_SHEAR: ShearRequest = {
  element_name: "V-1",
  mode: "design",
  shape: { kind: "rectangular", b: 300, h: 500, bf: 800, hf: 120, bw: 300 },
  cover: 30,
  stirrup_diameter: 8,
  stirrup_legs: 2,
  stirrup_spacing: 200,
  alpha_deg: 90,
  dg: 20,
  layers: [
    { face: "inferior", n: 3, diameter: 20 },
    { face: "superior", n: 2, diameter: 12 },
  ],
  tension_face: "inferior",
  V_Ed_kN: 150,
  N_Ed_kN: 0,
  concrete_class: "C25/30",
  stirrup_grade: "B500S",
  situation: "persistente",
  cot_theta: null,
  nu1_simplified: false,
  parameter_overrides: {},
};

export const DEFAULT_COLUMN: ColumnRequest = {
  element_name: "P-1",
  b: 400,
  h: 400,
  cover: 35,
  stirrup_diameter: 8,
  stirrup_spacing: 200,
  dg: 20,
  layers: [
    { face: "inferior", n: 3, diameter: 16 },
    { face: "superior", n: 3, diameter: 16 },
    { face: "lateral", n: 1, diameter: 16 },
  ],
  N_Ed_kN: 1500,
  M01_kNm: 20,
  M02_kNm: 40,
  length: 3500,
  braced: true,
  l0_mode: "beta",
  beta: 1.0,
  k1: 0.4,
  k2: 0.4,
  transverse_load: false,
  M0_span_kNm: null,
  phi_ef: null,
  phi_inf: 2.0,
  m0eqp_ratio: 0.6,
  ei_simplified: false,
  intermediate_bars_tied: false,
  concrete_class: "C25/30",
  steel_grade: "B500S",
  steel_branch: "horizontal",
  situation: "persistente",
  parameter_overrides: {},
};

export const DEFAULT_ELS: ElsState = {
  element_name: "V-1",
  shape: { kind: "rectangular", b: 300, h: 500, bf: 800, hf: 120, bw: 300 },
  cover: 30,
  stirrup_diameter: 8,
  dg: 20,
  layers: [
    { face: "inferior", n: 3, diameter: 20 },
    { face: "superior", n: 2, diameter: 12 },
  ],
  concrete_class: "C25/30",
  steel_grade: "B500S",
  M_qp_kNm: 90,
  M_char_kNm: 120,
  exposure: "XC1",
  w_max: null,
  long_term: true,
  span: 6000,
  system: "biapoyada",
  M_qp_defl_kNm: 90,
  RH: 60,
  t0: 28,
  cement: "N",
  perimeter: null,
  phi_override: null,
  eps_cs_override: null,
  camber: 0,
  kM: null,
  kcs: null,
  As_req: 800,
  As2_req: 0,
  fragile_partitions: false,
};

interface AppState {
  overrides: Record<string, unknown>;
  setOverrides: (o: Record<string, unknown>) => void;
  beam: FlexureRequest;
  setBeam: (b: FlexureRequest) => void;
  shear: ShearRequest;
  setShear: (s: ShearRequest) => void;
  column: ColumnRequest;
  setColumn: (c: ColumnRequest) => void;
  els: ElsState;
  setEls: (e: ElsState) => void;
  activeProject: { id: string; name: string } | null;
  setActiveProject: (p: { id: string; name: string } | null) => void;
}

const Ctx = createContext<AppState | null>(null);

function load<T>(key: string, fallback: T): T {
  try {
    const v = localStorage.getItem(key);
    return v ? (JSON.parse(v) as T) : fallback;
  } catch {
    return fallback;
  }
}

function save(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* almacenamiento no disponible */
  }
}

export function AppStateProvider({ children }: { children: ReactNode }) {
  const [overrides, setOv] = useState<Record<string, unknown>>(() => load("ha.overrides", {}));
  const [beam, setB] = useState<FlexureRequest>(() => ({ ...DEFAULT_BEAM, ...load("ha.beam", {}) }));
  const [shear, setSh] = useState<ShearRequest>(() => ({ ...DEFAULT_SHEAR, ...load("ha.shear", {}) }));
  const [column, setCol] = useState<ColumnRequest>(() => ({ ...DEFAULT_COLUMN, ...load("ha.column", {}) }));
  const [els, setE] = useState<ElsState>(() => ({ ...DEFAULT_ELS, ...load("ha.els", {}) }));
  const [activeProject, setAP] = useState<{ id: string; name: string } | null>(() => load("ha.project", null));

  useEffect(() => save("ha.overrides", overrides), [overrides]);
  useEffect(() => save("ha.beam", beam), [beam]);
  useEffect(() => save("ha.project", activeProject), [activeProject]);
  useEffect(() => save("ha.shear", shear), [shear]);
  useEffect(() => save("ha.column", column), [column]);
  useEffect(() => save("ha.els", els), [els]);

  const setOverrides = useCallback((o: Record<string, unknown>) => setOv(o), []);
  const setBeam = useCallback((b: FlexureRequest) => setB(b), []);
  const setShear = useCallback((x: ShearRequest) => setSh(x), []);
  const setColumn = useCallback((x: ColumnRequest) => setCol(x), []);
  const setEls = useCallback((x: ElsState) => setE(x), []);
  const setActiveProject = useCallback((p: { id: string; name: string } | null) => setAP(p), []);

  return (
    <Ctx.Provider value={{ overrides, setOverrides, beam, setBeam, shear, setShear, column, setColumn, els, setEls, activeProject, setActiveProject }}>
      {children}
    </Ctx.Provider>
  );
}

export function useAppState(): AppState {
  const c = useContext(Ctx);
  if (!c) throw new Error("AppStateProvider ausente");
  return c;
}
