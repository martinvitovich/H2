import { ApiError, downloadBlob } from "../api/client";
import type { CalcReport, ElementDetail, ElementType, Overview, ProjectListItem, Schema } from "./types";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api/estructuras${path}`, { headers: { "Content-Type": "application/json" }, ...init });
  } catch {
    throw new ApiError(0, "No se pudo conectar con el servidor (backend). ¿Está en ejecución?");
  }
  if (!res.ok) {
    let msg = `Error ${res.status}`;
    try {
      const b = await res.json();
      const d = b.detail ?? b;
      msg = typeof d === "string" ? d : Array.isArray(d) ? d.map((x: any) => `${(x.loc ?? []).filter((y: any) => y !== "body").join(" › ")}: ${x.msg}`).join("\n") : JSON.stringify(d);
    } catch {
      /* sin JSON */
    }
    throw new ApiError(res.status, msg);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}
const body = (method: string, b: unknown): RequestInit => ({ method, body: JSON.stringify(b) });

export interface Affected {
  id: string;
  code: string;
  type: ElementType;
  status: string;
}

async function download(path: string, fallbackName: string) {
  let res: Response;
  try {
    res = await fetch(`/api/estructuras${path}`);
  } catch {
    throw new ApiError(0, "No se pudo conectar con el servidor.");
  }
  if (!res.ok) {
    const b = await res.json().catch(() => ({}));
    throw new ApiError(res.status, typeof b.detail === "string" ? b.detail : `Error ${res.status}`);
  }
  const cd = res.headers.get("Content-Disposition") ?? "";
  const m = /filename="([^"]+)"/.exec(cd);
  downloadBlob(await res.blob(), m ? m[1] : fallbackName);
}

export const sapi = {
  schema: () => req<Schema>("/esquema"),
  list: () => req<ProjectListItem[]>(""),
  create: (b: Record<string, unknown>) => req<Overview>("", body("POST", b)),
  importJson: (data: unknown) => req<Overview>("/importar", body("POST", data)),
  get: (pid: string) => req<Overview>(`/${pid}`),
  patch: (pid: string, b: Record<string, unknown>) => req<Overview & { affected?: Affected[] }>(`/${pid}`, body("PATCH", b)),
  archive: (pid: string, archived: boolean) => req<unknown>(`/${pid}/archivar`, body("POST", { archived })),
  duplicate: (pid: string, name?: string) => req<Overview>(`/${pid}/duplicar`, body("POST", { name })),
  remove: (pid: string) => req<void>(`/${pid}`, { method: "DELETE" }),
  exportJson: (pid: string) => req<Record<string, unknown>>(`/${pid}/exportar`),
  history: (pid: string) => req<any[]>(`/${pid}/historial`),
  createLevel: (pid: string, b: Record<string, unknown>) => req<unknown>(`/${pid}/niveles`, body("POST", b)),
  patchLevel: (pid: string, lid: string, b: Record<string, unknown>) =>
    req<{ affected: Affected[] }>(`/${pid}/niveles/${lid}`, body("PATCH", b)),
  deleteLevel: (pid: string, lid: string) => req<void>(`/${pid}/niveles/${lid}`, { method: "DELETE" }),
  createElement: (pid: string, b: Record<string, unknown>) => req<ElementDetail>(`/${pid}/elementos`, body("POST", b)),
  createElements: (pid: string, rows: Record<string, unknown>[]) => req<{ created: string[] }>(`/${pid}/elementos/lote`, body("POST", rows)),
  element: (pid: string, eid: string) => req<ElementDetail>(`/${pid}/elementos/${eid}`),
  patchElement: (pid: string, eid: string, b: Record<string, unknown>) =>
    req<{ element: ElementDetail; affected: Affected[] }>(`/${pid}/elementos/${eid}`, body("PATCH", b)),
  deleteElement: (pid: string, eid: string) =>
    req<{ affected: string[]; links_removed_with: string[] }>(`/${pid}/elementos/${eid}`, { method: "DELETE" }),
  duplicateElement: (pid: string, eid: string, code?: string) => req<ElementDetail>(`/${pid}/elementos/${eid}/duplicar`, body("POST", { code })),
  adopt: (pid: string, eid: string) =>
    req<{ adopted: Record<string, unknown>; element: ElementDetail; affected: Affected[] }>(`/${pid}/elementos/${eid}/adoptar-propuesta`, { method: "POST" }),
  createLink: (pid: string, b: Record<string, unknown>) => req<{ id: string; affected: Affected[] }>(`/${pid}/relaciones`, body("POST", b)),
  patchLink: (pid: string, lid: string, data: Record<string, unknown>) =>
    req<{ affected: Affected[] }>(`/${pid}/relaciones/${lid}`, body("PATCH", { data })),
  deleteLink: (pid: string, lid: string) => req<{ affected: Affected[] }>(`/${pid}/relaciones/${lid}`, { method: "DELETE" }),
  calculate: (pid: string, b: { element_ids?: string[]; calc_types?: string[]; only_stale?: boolean }) =>
    req<CalcReport>(`/${pid}/calcular`, body("POST", b)),
  downloadExcel: (pid: string) => download(`/${pid}/planilla.xlsx`, "planilla.xlsx"),
  downloadPdf: (pid: string) => download(`/${pid}/informe.pdf`, "memoria.pdf"),
  downloadElementPdf: (pid: string, eid: string) => download(`/${pid}/elementos/${eid}/ficha.pdf`, "ficha.pdf"),
  downloadCalcPdf: (pid: string, eid: string, calc: string) =>
    download(`/${pid}/elementos/${eid}/informe.pdf?calc=${encodeURIComponent(calc)}`, "informe.pdf"),
};

export interface SummaryTable {
  key: string;
  title: string;
  headers: string[];
  rows: (string | number | null)[][];
}
export const tablesApi = (pid: string) => req<SummaryTable[]>(`/${pid}/planillas`);
