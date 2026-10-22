import type {
  ColumnRequest,
  ColumnResult,
  ElsResult,
  FlexureRequest,
  FlexureResult,
  ModuleInfo,
  NormInfo,
  Parameter,
  Project,
  ProjectSummary,
  ShearRequest,
  ShearResult,
} from "../types";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function detailToText(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        const loc = Array.isArray(d?.loc) ? d.loc.filter((x: unknown) => x !== "body").join(" › ") : "";
        return `${loc ? loc + ": " : ""}${d?.msg ?? JSON.stringify(d)}`;
      })
      .join("\n");
  }
  return JSON.stringify(detail);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    throw new ApiError(0, "No se pudo conectar con el servidor de cálculo (backend). ¿Está en ejecución?");
  }
  if (!res.ok) {
    let msg = `Error ${res.status}`;
    try {
      const body = await res.json();
      msg = detailToText(body.detail ?? body);
    } catch {
      /* respuesta sin JSON */
    }
    throw new ApiError(res.status, msg);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

const post = <T>(path: string, body: unknown) => request<T>(path, { method: "POST", body: JSON.stringify(body) });

async function pdf(path: string, body: unknown): Promise<Blob> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "No se pudo conectar con el servidor de cálculo.");
  }
  if (!res.ok) {
    const b = await res.json().catch(() => ({}));
    throw new ApiError(res.status, detailToText(b.detail ?? `Error ${res.status}`));
  }
  return res.blob();
}

export const api = {
  info: () => request<{ software: string; version: string; norm: NormInfo; modules: ModuleInfo[] }>("/info"),
  parameters: () => request<{ norm: NormInfo; parameters: Parameter[] }>("/norma/parametros"),
  validateParameters: (overrides: Record<string, unknown>) =>
    post<{ parameters: Parameter[]; overrides: Record<string, unknown> }>("/norma/parametros", overrides),
  catalog: () => request<{ concrete_classes: string[]; steel_grades: string[] }>("/materiales/catalogo"),
  materials: (body: unknown) => post<any>("/materiales", body),
  sectionProperties: (body: unknown) => post<any>("/secciones/propiedades", body),
  flexure: (body: FlexureRequest) => post<FlexureResult>("/vigas/flexion", body),
  flexureReport: (body: { project_name: string; author: string; request: FlexureRequest }) =>
    pdf("/informes/vigas/flexion", body),
  shear: (body: ShearRequest) => post<ShearResult>("/vigas/cortante", body),
  shearReport: (body: { project_name: string; author: string; request: ShearRequest }) =>
    pdf("/informes/vigas/cortante", body),
  column: (body: ColumnRequest) => post<ColumnResult>("/pilares", body),
  columnReport: (body: { project_name: string; author: string; request: ColumnRequest }) => pdf("/informes/pilares", body),
  slab: (body: unknown) => post<ElsResult>("/losas", body),
  slabReport: (body: { project_name: string; author: string; request: unknown }) => pdf("/informes/losas", body),
  elsCatalog: () => request<{ exposure_wmax: Record<string, number>; systems: Record<string, { K: number; description: string }> }>("/els/catalogo"),
  crack: (body: unknown) => post<ElsResult>("/els/fisuracion", body),
  deflection: (body: unknown) => post<ElsResult>("/els/deformaciones", body),
  elsReport: (kind: "fisuracion" | "deformaciones", body: { project_name: string; author: string; request: unknown }) =>
    pdf(`/informes/els/${kind}`, body),
  projects: () => request<ProjectSummary[]>("/proyectos"),
  project: (id: string) => request<Project>(`/proyectos/${id}`),
  createProject: (body: Partial<Project>) => post<Project>("/proyectos", body),
  updateProject: (id: string, body: Partial<Project>) =>
    request<Project>(`/proyectos/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteProject: (id: string) => request<void>(`/proyectos/${id}`, { method: "DELETE" }),
  importProject: (data: unknown) => post<Project>("/proyectos/importar", data),
};

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
