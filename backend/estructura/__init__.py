"""Proyecto estructural integral: modelo de datos persistente (niveles, losas, vigas, pilares,
zapatas), relaciones entre elementos, transmisión de cargas, dependencias, control de cambios
y ejecución de los cálculos del motor (``core``) sobre los elementos del proyecto.

Este paquete no contiene fórmulas del Anejo 19: obtiene los datos de entrada del motor a partir
del modelo y delega en ``core``. Las reglas de transmisión de cargas (estática isostática y áreas
tributarias) están documentadas en ``docs/proyecto_integral.md`` y quedan registradas en cada
resultado.
"""
