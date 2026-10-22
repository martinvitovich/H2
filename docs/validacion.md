# Procedimiento de validación

## Niveles

1. **Consistencia matemática (implementado)** — tests en `backend/tests`:
   - Soluciones cerradas independientes del diagrama parábola-rectángulo
     (α = 1 − k/(n+1); para n = 2, β = 99/238 con ε_c2/ε_cu2 = 2/3,5), contrastadas con la
     integración numérica del motor (tolerancia relativa 1e-9, la de `quad`).
   - Cálculos manuales de secciones rectangulares y en T con armadura simple
     (tolerancia relativa 1e-8, la del resolvedor `brentq`).
   - Equilibrio: residuo de fuerzas < 1 mN y momento independiente del punto de
     referencia.
   - Simetría (M_Rd⁺ = −M_Rd⁻ con armado simétrico), monotonía con la cuantía, y
     coherencia entre bloque rectangular y parábola-rectángulo (diferencia < 1 %).
   - Equilibrio de las soluciones del dimensionado (simple y doble armadura).
   - Casos límite y entradas inválidas (geometría, materiales, parámetros, API).
2. **Contraste con la tabla 3.1** — los valores redondeados de la tabla 3.1 de la
   EN 1992-1-1 se reproducen con tolerancia de medio dígito. Su transcripción **no** se
   ha cotejado con el Anejo 19 oficial (pendiente).
3. **Validación normativa independiente (PENDIENTE)** — requiere:
   - cotejo de cada fila de `docs/normativa.md` con el texto oficial;
   - contraste con ejemplos resueltos de bibliografía técnica verificable (no
     disponibles en el entorno de desarrollo: no se han inventado valores de referencia);
   - revisión por un ingeniero estructural.

Un módulo solo pasará al estado `verificado` (`backend/core/status.py`) cuando se
completen los tres niveles.

## Ejecución
```bash
npm test                # desde la raíz
# o: cd backend && .venv/bin/python -m pytest
```
