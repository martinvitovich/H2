# Decisiones técnicas y normativas

## D1 — Unidades internas N, mm, MPa
El motor trabaja en N, mm, MPa y N·mm. La API expone momentos en kN·m. Las
conversiones se concentran en `backend/core/units.py`.

## D2 — Parámetros centralizados con estado de verificación
Todos los coeficientes normativos viven en `backend/core/parameters.py`, con
referencia, rango admisible y estado (`confirmado_fuente_secundaria`,
`pendiente_verificacion`, `definido_por_usuario`). La interfaz permite
sobrescribirlos; el valor modificado queda registrado en cada cálculo y en el proyecto.

## D3 — Dimensionado con bloque rectangular y verificación con método general
- El dimensionado de secciones **rectangulares** usa la solución cerrada del bloque
  rectangular (3.1.7(3)). Su dominio de validez: sección de ancho constante en la
  zona comprimida, flexión simple, fibra neutra dentro de la sección.
- Toda disposición propuesta se **verifica** con el método general (compatibilidad
  de deformaciones + parábola-rectángulo, 6.1), que admite secciones en T, varias
  capas y armadura de compresión. Una disposición solo se acepta si cumple
  resistencia, criterio de ductilidad, cuantías y separaciones.
- Para secciones en T solo se ofrece la comprobación (método general); el
  dimensionado automático de T queda pendiente.

## D4 — Criterio de ductilidad x_u/d ≤ ξ_lim
El Anejo 19 no impone explícitamente un límite de x/d a secciones sin
redistribución (5.5(4) se refiere a la redistribución de momentos y 5.6.3(2) a las rótulas
plásticas del análisis plástico, con x_u/d ≤ 0,45 para f_ck ≤ 50). Para garantizar un comportamiento dúctil se adopta como **criterio de
proyecto** la expresión (5.10) de 5.5(4) con δ configurable (δ = 1 por defecto →
ξ_lim = 0,448 para f_ck ≤ 50 MPa). Además, en el dimensionado se exige la cedencia de
la armadura traccionada (ξ ≤ ε_cu3/(ε_cu3 + ε_yd)). Ambos criterios se documentan en
la traza como hipótesis y pueden ajustarse.

## D5 — Hormigón desplazado
En ambos métodos se descuenta la tensión del hormigón en el área de las barras
situadas en la zona comprimida (evita contar dos veces esa área).

## D6 — Rama del diagrama del acero
Por defecto, rama superior horizontal (3.2.7(2) b), que no requiere limitar la
deformación del acero. La rama inclinada está disponible y activa el pivote A
(ε_ud). El bloque rectangular no se aplica si el agotamiento lo produce el acero.

## D7 — Propuesta de armado
Búsqueda exhaustiva sobre los diámetros configurados: hasta dos capas de un mismo
diámetro en la cara traccionada y, si hace falta, una capa en la comprimida. Se
recalcula d con la geometría real de cada candidato. Orden de preferencia: menos
capas, menor área, menos barras. Se muestran alternativas. No se incluye armadura de
montaje (limitación declarada).

## D8 — Persistencia
Ficheros JSON versionados (`format_version` = 1) en `backend/data/projects/`
(configurable con `HA_DATA_DIR`). La clase `ProjectStore` aísla el almacenamiento para
poder sustituirlo por una base de datos. `migrate()` es el punto de entrada para
futuras versiones de formato.

## D9 — Informe PDF
ReportLab con fuentes DejaVu incluidas en el repositorio (`backend/services/fonts`,
licencia libre adjunta) para representar correctamente símbolos griegos y matemáticos.
El informe se construye solo con el resultado y la traza: no recalcula.

## D10 — Despliegue futuro
`npm run start` compila el frontend y FastAPI lo sirve como estáticos desde el mismo
proceso; CORS configurable con `HA_CORS_ORIGINS`. Esto permite publicar la aplicación
detrás de un proxy inverso sin cambios de arquitectura.

## D11 — Erratas del texto oficial
La expresión de ε_c2 impresa en la tabla A19.3.1 («0,85») es incoherente con los valores
tabulados de la misma tabla; se implementa 0,085, que los reproduce. Ver `docs/normativa.md`.

## D12 — Armadura mínima según la expresión (9.1) del Anejo 19
A_s,min = (W/z)·(f_ctm,fl/f_yd) con z = 0,8·h (aproximación que el propio Anejo admite;
configurable), W módulo resistente bruto respecto a la fibra más traccionada (depende del signo
del momento en secciones en T) y f_ctm,fl según (3.23). La alternativa 1,2·A_s,nec para
elementos secundarios es una opción explícita del usuario; en comprobación solo está disponible
para secciones rectangulares (A_s,nec con el bloque rectangular y el d real).

## D13 — 9.2.1.2(3) sin dato de separación de estribos
Si hay barras comprimidas que intervienen en la resistencia y no se indica la separación de
estribos, la verificación queda «no evaluable» y el resultado global no se declara conforme.

## D14 — Barras de capas superpuestas (8.2(3))
Las capas interiores se colocan en las columnas de la primera capa de la misma cara. Si una capa
interior tiene más barras que la primera, se informa del incumplimiento.

## D15 — Elección del ángulo de las bielas (cortante)
No se fija θ arbitrariamente. En el dimensionado se adopta el mayor cot θ del intervalo (6.7)
con V_Ed ≤ V_Rd,max (raíz de V_Ed·(1 + c²) = K·(c + cot α)), lo que minimiza la armadura de
cortante. En la comprobación se toma el θ que maximiza V_Rd = min(V_Rd,s; V_Rd,max) dentro de
(6.7): el límite superior, la intersección V_Rd,s = V_Rd,max (cot θ = √(K/A − 1)) o el máximo de
V_Rd,max (cot θ* = −cot α + √(cot²α + 1)). El usuario puede fijar cot θ.

## D16 — Propuesta de cercos
Separación = min(A_sw/(A_sw/s)_nec; s_l,max), redondeada hacia abajo a múltiplos de 25 mm
(criterio no normativo, configurable), descartando las que no respetan la separación libre de
8.2(2). Se ofrecen alternativas con φ6–φ12 y 2 o 4 ramas.

## D17 — Secciones críticas del pilar
Arriostrado sin cargas transversales: sección intermedia con M_Ed = max(M_0e + N·e_i + M_2; N·e_0)
y extremo con M_Ed = max(|M02|; N·e_0) (la nota de 5.8.7.3(3) advierte que los momentos de
extremo pueden superar a los equivalentes). Con cargas transversales: M_0 = momento máximo de
vano introducido por el usuario. No arriostrado: sección crítica en el extremo con M02 + N·e_i + M_2.

## D18 — Dominio A con rama horizontal del acero
Con la rama horizontal el Anejo no limita la deformación del acero; para recorrer los planos
del dominio A se fija numéricamente ε_s = 100 ‰ en la armadura más traccionada. El efecto en
la envolvente es despreciable y del lado de la seguridad (subconjunto de planos admisibles).

## D19 — Segundo orden solo si hay datos suficientes
Si λ > λ_lim y falta φ_ef, o la armadura no es simétrica (requisito de 5.8.8.3(1)), la
verificación de flexocompresión queda «no evaluable» y no se declara conforme.

## D20 — Tensión del acero para w_k
Se toma σ_s en la capa de armadura más traccionada (no en el centro de gravedad del grupo): del lado de la
seguridad cuando hay varias capas.

## D21 — Flecha a partir de la curvatura de la sección crítica
Siguiendo 7.4.3(7) se calcula la deformación suponiendo el elemento sin fisurar y totalmente fisurado y se
interpola con (7.18). La flecha se obtiene de la curvatura en la sección de momento máximo con los
coeficientes de forma de resistencia de materiales: biapoyada con carga uniforme 5/48 (carga) y 1/8
(retracción, curvatura constante); voladizo 1/4 y 1/2. Para otros sistemas el usuario introduce k_M y k_cs.

## D22 — Flecha diferida
Se aproxima como δ_tot(largo plazo, φ, ε_cs, β = 0,5) − δ_inst(E_cm, β = 1,0). No se modela la secuencia de
construcción ni el instante de colocación de tabiques.

## D23 — Método simplificado en secciones en T
ρ = A_s,req/(b_w·d) (del lado de la seguridad); corrección × 0,8 si b_f/b_w > 3 (7.4.2(2)).

## D24 — Losas por banda de 1 m con barras equivalentes
La armadura de cada cara se representa por una barra equivalente de igual área por metro situada a la
profundidad de su eje; en flexión solo intervienen el área y la profundidad, por lo que el resultado es
exacto. Las separaciones se comprueban aparte con las reglas de 9.3.1.1(3) y 8.2(2).

## D25 — Despliegue de un solo proceso
`npm run start` compila el frontend y FastAPI lo sirve con un «fallback» a index.html para las rutas
de la aplicación (recarga directa de /pilares, /els…); las rutas /api inexistentes devuelven 404.

## D26 — Base de datos SQLite para proyectos
Proyectos, elementos, relaciones, resultados e historial en SQLite (biblioteca estándar, claves foráneas,
WAL, migraciones versionadas). Sin servidor adicional y desplegable en el mismo contenedor. Los proyectos
JSON anteriores se importan una vez sin borrar los ficheros.

## D27 — Estado de resultados por huella de la entrada
No se marcan resultados «a mano»: el estado se obtiene comparando la huella SHA-256 de la entrada del motor
derivada de los datos actuales (más la versión del software) con la guardada. Así cualquier cambio aguas
arriba (losa, relación, configuración, nivel) desactualiza exactamente los cálculos cuya entrada cambia.

## D28 — Transmisión de cargas solo por equilibrio isostático o datos del usuario
El motor no dispone de análisis de continuidad ni de placas. La transmisión usa áreas/anchos tributarios
definidos por el usuario y equilibrio de vigas biapoyadas o en voladizo; para otros casos el usuario introduce
esfuerzos y reacciones de un análisis externo (modelo «manual»). Así se documenta en cada resultado.

## D29 — Sin recálculo automático
Los cambios se guardan al instante pero los cálculos solo se ejecutan a petición («Calcular pendientes»), para
no sobrescribir resultados sin que el usuario sepa a qué datos corresponden.

## D30 — Comprobación del terreno fuera del Anejo 19
La presión media bajo zapata (carga centrada, presión uniforme, combinación característica frente a σ_adm del
estudio geotécnico) se incluye como comprobación simplificada identificada como no perteneciente al Anejo 19.
