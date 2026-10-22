# Publicar la aplicación en Internet (Render)

La forma más sencilla: **un único servicio en [Render](https://render.com)** construido con el
`Dockerfile` del repositorio. La misma máquina compila la interfaz y sirve la interfaz y la API, así que
no hay nada que conectar entre servicios.

## Pasos (unos 10 minutos)

1. Entrar en <https://render.com> con la cuenta de GitHub (botón *GitHub*).
2. **New + → Blueprint**.
3. Elegir el repositorio **martinvitovich/h2**. Si no aparece: *Configure account* y dar acceso a ese repositorio.
4. Elegir la rama donde está el código (`claude/concrete-calculation-app-357fgp`, o `main` si ya se fusionó).
5. Render lee `render.yaml` y propone el servicio **ha-anejo19** (plan *Free*). Pulsar **Apply** / **Deploy Blueprint**.
6. Esperar a que termine la construcción (5–10 minutos la primera vez). Render muestra la dirección,
   por ejemplo `https://ha-anejo19.onrender.com`.
7. Comprobar: `https://…onrender.com/api/health` debe responder `{"status":"ok", …}` y la dirección raíz
   abre la aplicación.

Cada `git push` a esa rama vuelve a desplegar la aplicación automáticamente (`autoDeploy: true`).

## Alternativa sin Blueprint

**New + → Web Service** → repositorio → rama → *Language/Runtime: Docker* → plan *Free* →
*Health Check Path:* `/api/health` → **Create Web Service**.

## Limitaciones del plan gratuito (importante)

- **Arranque lento:** el servicio se suspende tras ~15 minutos sin uso; la primera visita posterior tarda
  ~30–60 s.
- **Los proyectos guardados no son permanentes:** el disco del plan gratuito se borra en cada reinicio o
  despliegue. Use «Exportar JSON» en *Proyectos* para conservarlos. Para guardarlos de forma fiable:
  plan de pago con **disco persistente** montado en `/data` (la aplicación guarda en `/data/projects`,
  variable `HA_DATA_DIR`), o migrar a una base de datos.
- **Sin autenticación:** cualquiera con el enlace puede usar la aplicación y ver, modificar o borrar los
  proyectos guardados. No publique datos confidenciales.

## Probar la imagen en local

```bash
docker build -t ha-anejo19 .
docker run -p 8000:8000 ha-anejo19      # http://localhost:8000
```
