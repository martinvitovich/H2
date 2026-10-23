import type { Trace } from "../types";

export type ElementType = "losa" | "viga" | "pilar" | "zapata";
export type LinkKind = "losa_viga" | "viga_apoyo" | "pilar_pilar" | "pilar_zapata";
export type CalcStatus = "actual" | "desactualizado" | "sin_calcular" | "faltan_datos" | "error" | "error_datos" | "no_aplica";

export interface FieldDef {
  key: string;
  label: string;
  kind: "number" | "int" | "text" | "select" | "bool" | "layers" | "pointloads";
  unit: string;
  default: unknown;
  min: number | null;
  max: number | null;
  options: { value: string; label: string }[] | null;
  help: string;
  group: string;
  table: boolean;
}

export interface Schema {
  settings: FieldDef[];
  settings_origin: Record<string, string>;
  elements: Record<ElementType, FieldDef[]>;
  links: Record<LinkKind, FieldDef[]>;
  link_kinds: Record<LinkKind, { source: ElementType[]; target: ElementType[]; label: string }>;
  types: Record<ElementType, { label: string; prefix: string }>;
}

export interface ProjectInfo {
  id: string;
  name: string;
  description: string;
  location: string;
  client: string;
  project_date: string;
  structural_system: string;
  status: "activo" | "archivado";
  norm: { id: string; name: string; edition: string };
  settings: Record<string, any>;
  parameter_overrides: Record<string, unknown>;
  software_version: string;
  created: string;
  modified: string;
}

export interface Level {
  id: string;
  code: string;
  name: string;
  elevation_m: number | null;
  height_m: number | null;
  sort_order: number;
}

export interface Link {
  id: string;
  kind: LinkKind;
  source_id: string;
  target_id: string;
  data: Record<string, any>;
}

export interface CalcCell {
  status: CalcStatus;
  ok?: boolean | null;
  texto?: string | null;
  summary?: Record<string, any> | null;
}

export interface ElementRow {
  id: string;
  type: ElementType;
  code: string;
  level_id: string | null;
  level_code: string | null;
  description: string;
  data: Record<string, any>;
  modified: string;
  status: CalcStatus;
  compliance: "cumple" | "no_cumple" | "no_evaluable" | null;
  calcs: Record<string, CalcCell>;
  loads: {
    g: number | null;
    q: number | null;
    efforts: Record<string, any> | null;
    reactions: Record<string, [number, number] | null> | null;
    N_G: number | null;
    N_Q: number | null;
  };
  missing: string[];
  errors: string[];
  warnings: string[];
  upstream: string[];
  downstream: string[];
}

export interface Verification {
  level: string;
  text: string;
  pending: string[];
  failing: string[];
  not_evaluable: string[];
  disclaimer: string;
}

export interface Overview {
  project: ProjectInfo;
  levels: Level[];
  elements: ElementRow[];
  links: Link[];
  summary: {
    by_status: Record<string, number>;
    by_compliance: Record<string, number>;
    calcs: Record<string, number>;
    n_elements: number;
    verification: Verification;
  };
  engine_version: string;
}

export interface ProjectListItem extends ProjectInfo {
  counts: Record<ElementType, number>;
  n_documents: number;
  summary: Overview["summary"];
}

export interface LoadRow {
  concepto: string;
  expresion: string;
  G: number | null;
  Q: number | null;
  unidad: string;
  origen: string;
  element_id: string | null;
}

export interface CalcEntry {
  calc_type: string;
  label: string;
  status: CalcStatus;
  ok?: boolean | null;
  reason?: string;
  missing?: string[];
  has_result: boolean;
  computed_at?: string;
  engine_version?: string;
  input_hash?: string;
  request: Record<string, any> | null;
  stored: null | {
    status: "ok" | "error";
    computed_at: string;
    engine_version: string;
    error: string | null;
    input: { request: Record<string, any>; procedencia: any; configuracion: any };
    output: null | { ok: boolean | null; summary: Record<string, any>; result: { ok: boolean | null; trace: Trace; [k: string]: any } };
  };
}

export interface Relation extends Link {
  direction: "entrada" | "salida";
  other_id: string;
  other_code: string;
  other_type: ElementType;
}

export interface HistoryEntry {
  ts: string;
  action: string;
  element_id: string | null;
  element_code: string | null;
  detail: Record<string, any>;
}

export interface ElementDetail extends ElementRow {
  loads_detail: {
    rows: LoadRow[];
    missing: string[];
    errors: string[];
    warnings: string[];
    notes: string[];
    efforts: Record<string, any> | null;
    reactions: Record<string, [number, number] | null> | null;
  };
  calc_list: CalcEntry[];
  relations: Relation[];
  affects: string[];
  history: HistoryEntry[];
}

export interface CalcReport {
  report: { element_id: string; code: string; calc_type: string; result: string; ok?: boolean | null; detail?: string }[];
  n_calculated: number;
  n_errors: number;
  n_missing: number;
}
