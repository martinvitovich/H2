export type ModuleStatus = "verificado" | "pendiente_validacion" | "no_disponible";

export interface ModuleInfo {
  id: string;
  name: string;
  status: ModuleStatus;
  detail: string;
}

export interface NormInfo {
  id: string;
  name: string;
  edition: string;
  short?: string;
}

export interface Parameter {
  key: string;
  symbol: string;
  value: number | number[];
  unit: string;
  description: string;
  reference: string;
  status:
    | "verificado_texto_oficial"
    | "confirmado_fuente_secundaria"
    | "pendiente_verificacion"
    | "definido_por_usuario"
    | "no_normativo";
  note: string;
  min_value: number | null;
  max_value: number | null;
}

export type Face = "inferior" | "superior";

export interface LayerIn {
  face: Face;
  n: number;
  diameter: number;
  depth?: number | null;
}

export interface ShapeIn {
  kind: "rectangular" | "T";
  b?: number;
  h: number;
  bf?: number;
  hf?: number;
  bw?: number;
}

export interface FlexureRequest {
  element_name: string;
  mode: "design" | "check";
  shape: ShapeIn;
  cover: number;
  stirrup_diameter: number;
  dg: number;
  concrete_class: string;
  steel_grade: string;
  steel_branch: "horizontal" | "inclinada";
  situation: "persistente" | "transitoria" | "accidental";
  M_Ed_kNm: number;
  assumed_bar_diameter: number;
  layers: LayerIn[];
  parameter_overrides: Record<string, unknown>;
  secondary_element: boolean;
  stirrup_spacing: number | null;
}

export interface Bar {
  x: number;
  y: number;
  diameter: number;
  layer: number;
  face: Face;
}

export interface Geometry {
  shape: ShapeIn & { kind: string };
  Ac: number;
  yg: number;
  Ig: number;
  As_inferior: number;
  As_superior: number;
  As_total: number;
  d_inferior: number | null;
  d_superior: number | null;
  bars: Bar[];
  issues: string[];
  min_clear_spacing: Record<string, number>;
}

export interface Step {
  title: string;
  reference: string;
  equation: string;
  substitution: string;
  result: number | null;
  unit: string;
  symbol: string;
  note: string;
}

export interface Check {
  name: string;
  reference: string;
  demand: string;
  capacity: string;
  ok: boolean | null;
  note: string;
}

export interface Trace {
  norm: NormInfo;
  calculation: string;
  method: string;
  validation_status: string;
  inputs: Record<string, unknown>;
  units: Record<string, string>;
  assumptions: string[];
  parameters_used: Parameter[];
  steps: Step[];
  checks: Check[];
  warnings: string[];
  limitations: string[];
  all_checks_ok: boolean | null;
}

export interface BarState {
  y: number;
  area: number;
  diameter: number;
  face: Face;
  strain: number;
  stress: number;
  force: number;
  yielded: boolean;
}

export interface Verification {
  diagram: string;
  sign: number;
  x: number;
  d: number;
  xi: number;
  eps_top: number;
  pivot: string;
  Fc: number;
  zc: number;
  M_Rd: number;
  residual_N: number;
  bars: BarState[];
}

export interface Alternative {
  text_tension: string;
  text_compression: string | null;
  As_tension: number;
  As_compression: number;
  d: number;
  M_Rd_kNm: number;
  xi: number;
  layers: LayerIn[];
}

export interface FlexureResult {
  mode: "design" | "check";
  ok: boolean | null;
  trace: Trace;
  materials: { concrete: Record<string, number | string>; steel: Record<string, number | string | null> };
  design?: Record<string, number | boolean | string> | null;
  proposal?: {
    layers: LayerIn[];
    text_tension: string;
    text_compression: string | null;
    As_tension: number;
    As_compression: number;
    d: number;
    geometry: Geometry;
    alternatives: Alternative[];
  } | null;
  geometry?: Geometry;
  verification: Verification | null;
  comparison?: Verification | null;
  request: FlexureRequest;
}

export interface ProjectElement {
  id?: string;
  type: "viga_flexion";
  name: string;
  input: FlexureRequest;
  result?: { ok: boolean | null; summary?: string } | null;
}

export interface Project {
  id: string;
  name: string;
  description: string;
  created: string;
  modified: string;
  format_version: number;
  software_version: string;
  norm: NormInfo;
  parameter_overrides: Record<string, unknown>;
  elements: ProjectElement[];
}

export interface ProjectSummary {
  id: string;
  name: string;
  description: string;
  modified: string;
  created: string;
  n_elements: number;
}
