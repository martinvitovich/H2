// Ejecuta el Python del entorno virtual dentro de backend/ con los argumentos recibidos.
import { spawnSync } from "node:child_process";
import { BACKEND, venvPython } from "./python.mjs";

const py = venvPython();
if (!py) {
  console.error("No se encontró backend/.venv. Ejecute primero: npm run setup");
  process.exit(1);
}
const r = spawnSync(py, process.argv.slice(2), { cwd: BACKEND, stdio: "inherit" });
process.exit(r.status ?? 1);
