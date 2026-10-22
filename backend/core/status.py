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
    {"id": "losas", "name": "Losas", "status": "no_disponible", "detail": "Pendiente."},
    {"id": "pilares", "name": "Pilares — flexocompresión", "status": "no_disponible",
     "detail": "Fase 4."},
    {"id": "els_fisuracion", "name": "ELS — fisuración", "status": "no_disponible", "detail": "Fase 5."},
    {"id": "els_deformaciones", "name": "ELS — deformaciones", "status": "no_disponible", "detail": "Fase 5."},
    {"id": "proyectos", "name": "Proyectos", "status": "pendiente_validacion",
     "detail": "Guardado/apertura en JSON versionado (formato 1)."},
    {"id": "informes", "name": "Informes PDF", "status": "pendiente_validacion",
     "detail": "Informe de flexión de vigas."},
]
