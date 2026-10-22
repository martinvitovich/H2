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

export type Face = "inferior" | "superior" | "lateral";

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

export interface ShearRequest {
  element_name: string;
  mode: "design" | "check";
  shape: ShapeIn;
  cover: number;
  stirrup_diameter: number;
  stirrup_legs: number;
  stirrup_spacing: number | null;
  alpha_deg: number;
  dg: number;
  layers: LayerIn[];
  tension_face: Face;
  V_Ed_kN: number;
  N_Ed_kN: number;
  concrete_class: string;
  stirrup_grade: string;
  situation: "persistente" | "transitoria" | "accidental";
  cot_theta: number | null;
  nu1_simplified: boolean;
  parameter_overrides: Record<string, unknown>;
}

export interface StirrupOption {
  diameter: number;
  legs: number;
  spacing: number;
  Asw_s_mm2_m?: number;
  s_t?: number;
}

export interface ShearResult {
  mode: "design" | "check";
  ok: boolean | null;
  trace: Trace;
  materials: { concrete: Record<string, number | string>; stirrups: Record<string, number | string | null> };
  result: {
    VRdc: { k: number; rho_l: number; sigma_cp: number; VRdc: number; VRdc_a: number; VRdc_b: number; vmin: number };
    z: number;
    nu1: number;
    fywd: number;
    rho_w_min: number;
    s_l_max: number;
    s_t_max: number;
    s_t_legs: number;
    Asw: number;
    needs_shear_reinforcement: boolean;
    cot_theta?: number;
    theta_deg?: number;
    VRd_max?: number;
    VRd_s?: number;
    Asw_s_req?: number;
    Asw_s_design?: number;
    Asw_s_provided?: number;
    rho_w?: number;
    Delta_Ftd?: number;
    proposal?: StirrupOption | null;
    alternatives?: StirrupOption[];
    geometry: Geometry;
  };
  request: ShearRequest;
}

export interface ColumnRequest {
  element_name: string;
  b: number;
  h: number;
  cover: number;
  stirrup_diameter: number;
  stirrup_spacing: number | null;
  dg: number;
  layers: LayerIn[];
  N_Ed_kN: number;
  M01_kNm: number;
  M02_kNm: number;
  length: number;
  braced: boolean;
  l0_mode: "beta" | "k";
  beta: number | null;
  k1: number | null;
  k2: number | null;
  transverse_load: boolean;
  M0_span_kNm: number | null;
  phi_ef: number | null;
  phi_inf: number | null;
  m0eqp_ratio: number | null;
  ei_simplified: boolean;
  intermediate_bars_tied: boolean;
  concrete_class: string;
  steel_grade: string;
  steel_branch: "horizontal" | "inclinada";
  situation: "persistente" | "transitoria" | "accidental";
  parameter_overrides: Record<string, unknown>;
}

export interface ColumnResult {
  ok: boolean | null;
  trace: Trace;
  materials: { concrete: Record<string, number | string>; steel: Record<string, number | string | null> };
  result: {
    l0: number;
    i: number;
    lambda: number;
    lambda_lim: number;
    second_order: boolean;
    omega: number;
    n: number;
    phi_ef: number | null;
    e_i: number;
    e_0: number;
    M0e: number;
    M0Ed: number;
    M2: number;
    MEd_crit: number;
    MEd_end: number;
    N_Rd_max: number;
    MRd?: number;
    MRd_domain?: string;
    s_cl_max?: number;
    geometry: Geometry;
    diagram: { N_kN: number; M_kNm: number; domain: string }[];
    design_points: { label: string; N_kN: number; M_kNm: number }[];
  };
  request: ColumnRequest;
}

export interface SlabRequest {
  element_name: string;
  mode: "design" | "check";
  h: number;
  cover: number;
  m_Ed_kNm: number;
  v_Ed_kN: number;
  span: number | null;
  bar_diameter: number;
  bar_spacing: number | null;
  secondary_diameter: number | null;
  secondary_spacing: number | null;
  compression_bar_diameter: number | null;
  compression_bar_spacing: number | null;
  low_brittle_risk: boolean;
  concrete_class: string;
  steel_grade: string;
  situation: "persistente" | "transitoria" | "accidental";
  dg: number;
  parameter_overrides: Record<string, unknown>;
}

export interface ElsState {
  element_name: string;
  shape: ShapeIn;
  cover: number;
  stirrup_diameter: number;
  dg: number;
  layers: LayerIn[];
  concrete_class: string;
  steel_grade: string;
  // fisuración
  M_qp_kNm: number;
  M_char_kNm: number | null;
  exposure: string;
  w_max: number | null;
  long_term: boolean;
  // deformaciones
  span: number;
  system: "biapoyada" | "continua_extremo" | "continua_interior" | "losa_plana" | "voladizo";
  M_qp_defl_kNm: number;
  RH: number;
  t0: number;
  cement: "S" | "N" | "R";
  perimeter: number | null;
  phi_override: number | null;
  eps_cs_override: number | null;
  camber: number;
  kM: number | null;
  kcs: number | null;
  As_req: number | null;
  As2_req: number;
  fragile_partitions: boolean;
}

export interface ElsResult {
  ok: boolean | null;
  trace: Trace;
  result: Record<string, any> & { geometry: Geometry };
  request: Record<string, unknown>;
}

export type ProjectElement =
  | { id?: string; type: "viga_flexion"; name: string; input: FlexureRequest; result?: { ok: boolean | null; summary?: string } | null }
  | { id?: string; type: "viga_cortante"; name: string; input: ShearRequest; result?: { ok: boolean | null; summary?: string } | null }
  | { id?: string; type: "pilar"; name: string; input: ColumnRequest; result?: { ok: boolean | null; summary?: string } | null }
  | { id?: string; type: "losa"; name: string; input: SlabRequest; result?: { ok: boolean | null; summary?: string } | null }
  | { id?: string; type: "els_fisuracion" | "els_deformaciones"; name: string; input: Record<string, any>; result?: { ok: boolean | null; summary?: string } | null };

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
