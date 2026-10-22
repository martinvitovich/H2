// Modo producción local: compila el frontend y lo sirve desde FastAPI en un solo proceso.
import { spawnSync } from "node:child_process";
import { join } from "node:path";
import { BACKEND, ROOT, venvPython } from "./python.mjs";

const py = venvPython();
if (!py) {
  console.error("Ejecute primero: npm run setup");
  process.exit(1);
}
const b = spawnSync("npm", ["run", "build"], { cwd: join(ROOT, "frontend"), stdio: "inherit", shell: process.platform === "win32" });
if (b.status !== 0) process.exit(b.status ?? 1);
const port = process.env.HA_BACKEND_PORT ?? "8000";
console.log(`\nAplicación: http://127.0.0.1:${port}\n`);
spawnSync(py, ["-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", port], { cwd: BACKEND, stdio: "inherit" });
