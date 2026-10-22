// Inicia backend (FastAPI/uvicorn, puerto 8000) y frontend (Vite, puerto 5173) con un único comando.
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { BACKEND, ROOT, venvPython } from "./python.mjs";

const py = venvPython();
if (!py) {
  console.error("No se encontró el entorno virtual del backend (backend/.venv).\nEjecute primero: npm run setup");
  process.exit(1);
}
if (!existsSync(join(ROOT, "frontend", "node_modules"))) {
  console.error("Faltan las dependencias del frontend. Ejecute primero: npm run setup");
  process.exit(1);
}

const port = process.env.HA_BACKEND_PORT ?? "8000";
const procs = [];

function start(name, color, cmd, args, opts) {
  const p = spawn(cmd, args, { ...opts, shell: process.platform === "win32", env: { ...process.env, ...(opts.env ?? {}), FORCE_COLOR: "1" } });
  const tag = `\x1b[${color}m[${name}]\x1b[0m `;
  const pipe = (stream, out) => {
    let buf = "";
    stream.on("data", (d) => {
      buf += d.toString();
      const lines = buf.split(/\r?\n/);
      buf = lines.pop();
      for (const l of lines) out.write(tag + l + "\n");
    });
  };
  pipe(p.stdout, process.stdout);
  pipe(p.stderr, process.stderr);
  p.on("exit", (code) => {
    console.log(`${tag}finalizado (código ${code}).`);
    shutdown(code ?? 0);
  });
  procs.push(p);
}

let stopping = false;
function shutdown(code) {
  if (stopping) return;
  stopping = true;
  for (const p of procs) if (!p.killed) p.kill();
  setTimeout(() => process.exit(code), 300);
}
process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));

start("backend", "36", py, ["-m", "uvicorn", "main:app", "--reload", "--host", "127.0.0.1", "--port", port], { cwd: BACKEND });
start("frontend", "35", "npm", ["run", "dev"], {
  cwd: join(ROOT, "frontend"),
  env: { ...process.env, HA_BACKEND_URL: `http://127.0.0.1:${port}` },
});
console.log(`\nAplicación: http://localhost:5173  ·  API: http://127.0.0.1:${port}/docs\n`);
