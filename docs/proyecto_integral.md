# Proyecto estructural integral (v0.7.0)

Gestión de un proyecto completo (p. ej., una vivienda) con niveles, losas, vigas, pilares y zapatas
relacionados, transmisión de cargas con procedencia, control de cambios y cálculo selectivo con el
motor existente. La planilla de referencia (`Cálculos.xlsx`) se utilizó **solo** para entender la
organización de la información (categorías, relaciones, secuencia losas → vigas → pilares →
fundaciones, tablas resumen); sus fórmulas y resultados no se revisaron ni se usaron como validación.
El motor de cálculo (`backend/core`) no se modificó.

## 1. Modelo de datos (SQLite, `backend/estructura/db.py`)

| Tabla | Contenido | Integridad |
|---|---|---|
| `projects` | nombre, descripción, ubicación, cliente, fecha, sistema estructural, estado (activo/archivado), norma, configuración, parámetros normativos, versión, fechas | — |
| `levels` | código, nombre, cota, altura de planta, orden | FK proyecto (CASCADE); código único por proyecto |
| `elements` | tipo (`losa`, `viga`, `pilar`, `zapata`), código, nivel, descripción, datos (JSON validado contra `estructura/model.py`) | FK proyecto (CASCADE), FK nivel (RESTRICT); código único por proyecto; nivel del mismo proyecto (trigger) |
| `links` | relación origen → destino con datos (`losa_viga`, `viga_apoyo`, `pilar_pilar`, `pilar_zapata`) | FK elementos (CASCADE); únicas; sin autorrelación; mismo proyecto (trigger); tipos compatibles, apoyos únicos y ausencia de ciclos (repositorio) |
| `results` | último resultado por elemento y cálculo: fecha, versión del motor, huella SHA-256 de la entrada, entrada (petición al motor + procedencia + configuración), salida o error | FK elemento (CASCADE); único (elemento, cálculo) |
| `history` | registro de cambios (creación, modificaciones campo a campo antes → después, relaciones, cálculos) | FK proyecto |
| `calc_documents` | cálculos independientes de las calculadoras (formato de proyecto 1) | FK proyecto |
| `legacy_imports`, `meta` | ficheros JSON ya migrados; versión del esquema | — |

Las relaciones usan siempre identificadores internos estables (UUID); los códigos visibles (L101,
V101, P1…) pueden cambiarse sin romperlas. Migraciones versionadas en `MIGRATIONS` (no borran
datos). Los proyectos JSON del almacenamiento anterior se importan una vez, conservando su
identificador; los ficheros originales no se modifican.

## 2. Mapa de dependencias y reglas de transmisión

```
Losa ──(área A o ancho b tributario)──▶ Viga ──(reacción del extremo)──▶ Pilar ──▶ Pilar inferior ──▶ Zapata
                                        Viga ──(reacción, carga puntual en x)──▶ Viga
```

| Paso | Regla (unidades) | Estado |
|---|---|---|
| Cargas de losa | g = h·γ_HA + CM + P_muros/(L·B); q = SCU (kN/m²) | Implementado |
| Losa → viga | w = carga·A/L_viga (área tributaria) o carga·b (ancho tributario) (kN/m). El reparto lo define el usuario; se avisa si Σ A ≠ superficie de la losa (±2 %) | Implementado |
| Viga | g = b·h·γ_HA + muros + otras + Σ losas; q = otras + Σ losas; cargas puntuales del usuario y reacciones de vigas apoyadas | Implementado |
| Esfuerzos de viga | equilibrio de viga **biapoyada** o **voladizo** (G y Q por separado), o esfuerzos y reacciones **manuales** de un análisis externo | Implementado; sin continuidad, redistribución ni alternancia de sobrecargas |
| Viga → pilar / viga | reacción característica (G, Q) del extremo indicado; en vigas, carga puntual en la posición indicada | Implementado; el momento de empotramiento de voladizos no se transmite (aviso) |
| Pilar | N = Σ reacciones + pilar superior + peso propio b·h·l·γ_HA + adicionales; N_Ed = γ_G·N_G + γ_Q·N_Q en la base | Implementado; M₀₁, M₀₂ son datos del usuario (el modelo isostático no transmite momentos) |
| Pilar → zapata | N_k = N_G + N_Q en la base; σ = (N_k + PP)/(B·L) ≤ σ_adm | Implementado como comprobación geotécnica simplificada (fuera del Anejo 19) |
| Losas | m⁺ = p_d·l²/8, v = p_d·l/2 (franja biapoyada); voladizo m⁻ = p_d·l²/2; o manual | Implementado; losas bidireccionales/continuas solo con esfuerzos manuales |

Combinaciones: ELU γ_G·G + γ_Q·Q; característica G + Q; cuasi-permanente G + ψ₂·Q (valores por
defecto 1,35 / 1,5 / 0,3, marcados como «por defecto del programa — confirmar»: las combinaciones de
acciones no forman parte del Anejo 19).

## 3. Cálculos por elemento (motor `core`, sin cambios)

| Elemento | Cálculo | Requiere |
|---|---|---|
| Losa | `losa_flexion` (m⁺ y v), `losa_flexion_neg` | h, SCU, luz o esfuerzos manuales; dimensiona si no hay separación dispuesta |
| Viga | `viga_flexion` (M⁺), `viga_flexion_neg` (M⁻), `viga_cortante`, `viga_fisuracion`, `viga_flecha` | b, h, L; flexión dimensiona sin armadura y comprueba con ella; cortante y ELS requieren armadura dispuesta |
| Pilar | `pilar` (flexocompresión, 5.8, 9.5) | b, h, altura (pilar o nivel), armadura dispuesta |
| Zapata | `zapata_terreno` | pilar relacionado, B, L, h, σ_adm |

Nunca se suponen datos: si faltan, el cálculo queda en «faltan datos» con la lista concreta. La
armadura propuesta por un dimensionado vigente solo se copia a los datos con la acción explícita
«Adoptar armadura propuesta».

## 4. Control de cambios

* Las entradas del motor se derivan de forma determinista de los datos actuales. Estado de cada
  cálculo: `actual` (huella y versión del motor coinciden), `desactualizado`, `sin_calcular`,
  `faltan_datos`, `error` (del motor), `error_datos`, `no_aplica`.
* Al guardar un cambio se informa de los elementos afectados (cierre transitivo aguas abajo).
* No se recalcula automáticamente: «Calcular pendientes» recalcula solo lo no vigente, en orden
  topológico. Los resultados desactualizados se muestran tachados y no se usan en informes.
* El estado global nunca declara el proyecto comprobado si queda algo pendiente.

## 5. Interfaz

`/proyectos` (panel: crear, abrir, duplicar, archivar, exportar/importar JSON, eliminar, búsqueda,
estado de cálculo y última modificación) y `/p/:id/<pestaña>`: Resumen, Datos y materiales, Plantas y
niveles, Losas, Vigas, Pilares, Fundaciones, Relaciones y cargas, Resultados y verificaciones,
Planillas y documentación, Configuración. Tablas editables con autoguardado, alta múltiple, filtros,
búsqueda, duplicado y validación. Ficha de elemento (`/p/:id/e/:eid`): identificación, datos,
armaduras, relaciones, cargas con procedencia, cálculos con detalle normativo e informes, historial.

## 6. Documentación generada

Memoria resumen PDF del proyecto, planilla Excel (proyecto, niveles, losas, vigas, pilares, zapatas,
relaciones, resultados, armaduras, pendientes), ficha PDF por elemento e informe de cálculo completo
por resultado vigente (409 si no lo está).

## 7. Pendiente / fuera de alcance

* Análisis de vigas y losas continuas, pórticos y placas (momentos en apoyos, transmisión de momentos a pilares).
* Alternancia de sobrecargas y combinaciones con varias acciones variables, viento, sismo.
* Dimensionado estructural de zapatas (9.8, 6.4), vigas de cimentación, muros.
* Generación automática de áreas tributarias a partir de geometría en planta.
* Edición concurrente multiusuario (la base de datos SQLite es de un único proceso).
