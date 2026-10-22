// Localiza el intérprete de Python del entorno virtual del backend (multiplataforma).
import { existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

export const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
export const BACKEND = join(ROOT, "backend");
export const VENV = join(BACKEND, ".venv");

export function venvPython() {
  const win = join(VENV, "Scripts", "python.exe");
  const nix = join(VENV, "bin", "python");
  if (existsSync(win)) return win;
  if (existsSync(nix)) return nix;
  return null;
}

export function systemPython() {
  return process.platform === "win32" ? "python" : "python3";
}
