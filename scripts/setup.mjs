// Instala las dependencias del backend (entorno virtual) y del frontend.
import { spawnSync } from "node:child_process";
import { join } from "node:path";
import { BACKEND, ROOT, VENV, systemPython, venvPython } from "./python.mjs";

function run(cmd, args, opts = {}) {
  console.log(`\n> ${cmd} ${args.join(" ")}`);
  const r = spawnSync(cmd, args, { stdio: "inherit", shell: process.platform === "win32", ...opts });
  if (r.status !== 0) {
    console.error(`\nError ejecutando: ${cmd} ${args.join(" ")}`);
    process.exit(r.status ?? 1);
  }
}

if (!venvPython()) run(systemPython(), ["-m", "venv", VENV]);
const py = venvPython();
run(py, ["-m", "pip", "install", "--upgrade", "pip"]);
run(py, ["-m", "pip", "install", "-r", join(BACKEND, "requirements-dev.txt")]);
run("npm", ["install"], { cwd: join(ROOT, "frontend") });
console.log("\nInstalación completada. Inicie la aplicación con: npm run dev");
