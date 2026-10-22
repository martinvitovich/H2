# Ejemplos

Ficheros de entrada (mismo formato que `POST /api/vigas/flexion`). Sus resultados **no
son valores de referencia validados**; sirven para reproducir y revisar el procedimiento.

```bash
backend/.venv/bin/python examples/run_example.py examples/viga_rect_dimensionado.json
backend/.venv/bin/python examples/run_example.py examples/viga_T_comprobacion.json --pdf informe.pdf
backend/.venv/bin/python examples/run_example.py examples/viga_cortante.json
backend/.venv/bin/python examples/run_example.py examples/pilar.json
backend/.venv/bin/python examples/run_example.py examples/losa.json
```
