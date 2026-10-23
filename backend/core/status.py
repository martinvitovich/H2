"""Estado real de implementación de cada módulo (fuente única para la API y la UI).

Estados:
* ``verificado``: implementado y con validación normativa independiente completada.
* ``pendiente_validacion``: implementado, con pruebas matemáticas, pero sin validación
  normativa independiente completa.
* ``no_disponible``: no implementado.
"""

MODULES = [
    {"id": "materiales", "name": "Materiales", "status": "pendiente_validacion",
     "detail": "Hormigón (tabla A19.3.1, 3.1.6, 3.1.7, 3.1.8) y acero (3.2.7), cotejados con el texto oficial. Pendiente: ductilidad de cada designación de acero (Art. 34-35 CE)."},
    {"id": "secciones", "name": "Secciones", "status": "pendiente_validacion",
     "detail": "Rectangular y en T, armaduras en varias capas, separaciones 8.2."},
    {"id": "vigas_flexion", "name": "Vigas — flexión ELU", "status": "pendiente_validacion",
     "detail": "Dimensionado (rectangular) y comprobación (rectangular y T) en flexión simple. Cotejado con el texto oficial; pendiente contraste con ejemplos bibliográficos."},
    {"id": "vigas_cortante", "name": "Vigas — cortante ELU", "status": "pendiente_validacion",
     "detail": "V_Rd,c, cercos (α 45°–90°), bielas, cuantías y separaciones (6.2, 9.2.2). Cotejado con el texto oficial; pendiente contraste con ejemplos bibliográficos."},
    {"id": "losas", "name": "Losas macizas unidireccionales", "status": "pendiente_validacion",
     "detail": "Flexión por metro, cuantías y separaciones (9.3.1), reparto 20 %, cortante sin armadura (6.2.2). Cotejado con el texto oficial; pendiente contraste bibliográfico. Losas bidireccionales, planas y punzonamiento: no disponibles."},
    {"id": "pilares", "name": "Pilares — flexocompresión", "status": "pendiente_validacion",
     "detail": "Diagrama N–M (6.1), esbeltez y curvatura nominal (5.8), imperfecciones (5.2), disposiciones 9.5. Flexión recta, sección rectangular. Cotejado con el texto oficial; pendiente contraste bibliográfico."},
    {"id": "els_fisuracion", "name": "ELS — fisuración", "status": "pendiente_validacion",
     "detail": "w_k (7.3.4), w_max (tabla 27.2), armadura mínima (7.3.2), tensiones (7.2). Flexión simple. Cotejado con el texto oficial; pendiente contraste bibliográfico."},
    {"id": "els_deformaciones", "name": "ELS — deformaciones", "status": "pendiente_validacion",
     "detail": "Relación luz/canto (7.4.2) y cálculo de flechas (7.4.3) con fluencia y retracción (3.1.4, Apéndice B). Cotejado con el texto oficial; pendiente contraste bibliográfico."},
    {"id": "proyecto_integral", "name": "Proyecto estructural integral", "status": "pendiente_validacion",
     "detail": "Niveles, losas, vigas, pilares y zapatas relacionados en una base de datos; transmisión de cargas con procedencia (áreas tributarias y equilibrio de vigas isostáticas); control de resultados desactualizados; cálculo selectivo con el motor. Sin análisis de continuidad, placas ni dimensionado estructural de zapatas."},
    {"id": "proyectos", "name": "Proyectos", "status": "pendiente_validacion",
     "detail": "Base de datos SQLite con migraciones; importación de los proyectos JSON anteriores; exportación/importación JSON (formato 2)."},
    {"id": "informes", "name": "Informes y planillas", "status": "pendiente_validacion",
     "detail": "Informes PDF de cada cálculo, ficha PDF por elemento, memoria resumen PDF del proyecto y planilla Excel de datos y resultados."},
]
