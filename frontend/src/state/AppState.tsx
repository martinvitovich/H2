import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import type { FlexureRequest } from "../types";

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
};

interface AppState {
  overrides: Record<string, unknown>;
  setOverrides: (o: Record<string, unknown>) => void;
  beam: FlexureRequest;
  setBeam: (b: FlexureRequest) => void;
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
  const [activeProject, setAP] = useState<{ id: string; name: string } | null>(() => load("ha.project", null));

  useEffect(() => save("ha.overrides", overrides), [overrides]);
  useEffect(() => save("ha.beam", beam), [beam]);
  useEffect(() => save("ha.project", activeProject), [activeProject]);

  const setOverrides = useCallback((o: Record<string, unknown>) => setOv(o), []);
  const setBeam = useCallback((b: FlexureRequest) => setB(b), []);
  const setActiveProject = useCallback((p: { id: string; name: string } | null) => setAP(p), []);

  return (
    <Ctx.Provider value={{ overrides, setOverrides, beam, setBeam, activeProject, setActiveProject }}>
      {children}
    </Ctx.Provider>
  );
}

export function useAppState(): AppState {
  const c = useContext(Ctx);
  if (!c) throw new Error("AppStateProvider ausente");
  return c;
}
