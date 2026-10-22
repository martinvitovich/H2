# Referencia normativa y estado de verificación

## Norma principal

- **Código Estructural**, aprobado por el **Real Decreto 470/2021, de 29 de junio**
  (BOE-A-2021-13681, BOE n.º 190, de 10/08/2021).
- **Anejo 19**: *Proyecto de estructuras de hormigón. Reglas generales y reglas para edificación*
  (BOE págs. 98285 y siguientes).

## Fuente utilizada para el cotejo

Versión 0.1.0: el PDF oficial no era accesible desde el entorno de desarrollo y los parámetros
se implementaron siguiendo la estructura de la EN 1992-1-1, marcados como pendientes.

Versión 0.2.0: **el texto oficial del Anejo 19 publicado en el BOE** (PDF de 207 páginas,
«BOE-A-2021-13681 Anejo 19») se ha cotejado apartado por apartado para todo lo que interviene en
el módulo de flexión. Las referencias del código indican la página del BOE. Las páginas del PDF
equivalen a «pág. BOE − 98284».

## Matriz de trazabilidad (materiales y flexión ELU de vigas)

| Magnitud / regla | Apartado (BOE pág.) | Implementación | Valor oficial | Estado |
|---|---|---|---|---|
| γ_c, γ_s | 2.4.2.4(1), tabla A19.2.1 (98304) | `parameters.py` | 1,5 / 1,15 (permanente o transitoria); 1,3 / 1,0 (accidental) | Verificado |
| Reducción de γ_s | 2.4.2.6 (98304) | nota del parámetro | hasta 1,10 si se cumplen ≥ 2 condiciones | Verificado (no automatizado) |
| Clases resistentes | 3.1.2(2), tabla A19.3.1 (98308) | `CONCRETE_FCK_CLASSES` | C12/15 a C90/105, f_ck ≤ 90 | Verificado |
| f_cm, f_ctm, f_ctk, E_cm, ε_c1, ε_cu1, ε_cu2, n, ε_c3, ε_cu3 | tabla A19.3.1 (98308) | `materials.Concrete` | relaciones analíticas de la tabla | Verificado (test con todos los valores tabulados) |
| ε_c2 (f_ck > 50) | tabla A19.3.1 (98308) | `Concrete.eps_c2` | **errata**, ver abajo | Verificado con corrección |
| E_cm según el árido | 3.1.3(2) (98307) | `AGGREGATE_ECM_FACTORS` | calizo −10 %, arenisca −30 %, basáltico +20 % | Verificado |
| f_cd = α_cc·f_ck/γ_c | 3.1.6(1), (3.15) (98313) | `Concrete.fcd` | α_cc = 1,00; 0,85–1,0 si la carga permanente supera el 80 % | Verificado |
| f_ctd = α_ct·f_ctk,0,05/γ_c | 3.1.6(2), (3.16) (98313) | `Concrete.fctd` | α_ct = 1,00 | Verificado |
| Parábola-rectángulo | 3.1.7(1), (3.17)-(3.18) (98313) | `sigma_parabola_rectangle` | — | Verificado |
| Bloque rectangular λ, η | 3.1.7(3), (3.19)-(3.22) (98314-98315) | `Concrete.lam/eta` | — | Verificado |
| Reducción del 10 % de η·f_cd | 3.1.7(3), nota (98315) | `width_decreases_towards_compressed_fibre` | si el ancho disminuye hacia la fibra comprimida | Verificado |
| f_ctm,fl | 3.1.8(1), (3.23) (98315) | `Concrete.fctm_fl` | max{(1,6 − h/1000)·f_ctm; f_ctm} | Verificado |
| Rango de f_yk | 3.2.2(3) (98317) | `ReinforcingSteel` | **400–500 MPa** (en v0.1.0 se admitía hasta 600: corregido) | Verificado |
| Diagrama de cálculo del acero | 3.2.7(2), figura A19.3.8 (98319) | `ReinforcingSteel.sigma` | rama inclinada (ε_ud = 0,9·ε_uk, k·f_yk/γ_s) o rama horizontal | Verificado |
| E_s | 3.2.7(4) (98319) | `parameters.Es` | 200 000 N/mm² | Verificado |
| ε_uk, k por designación (B400S, B500S, B400SD, B500SD) | Apéndice C (98473) → Arts. 34 y 35 del CE | `STEEL_GRADES` | **no incluido en el Anejo 19** | **Pendiente**: remite al articulado, no consultado |
| Criterio de ductilidad | 5.5(4), (5.10a/b) (98335-98336) | `ductility_limit` | k1 = 0,44; k2 = k4 = 1,25(0,6 + 0,0014/ε_cu2); k3 = 0,54; δ ≥ k5 = 0,7 (S, SD) | Verificado; su uso con δ = 1 es una decisión de proyecto (D4) |
| Hipótesis de cálculo de secciones | 6.1(2) (98357) | `analysis.py` | — | Verificado |
| Deformaciones límite | 6.1(3), figura A19.6.1 (98357-98358) | `analyse_bending` (pivotes A y B) | ε_cu2 / ε_cu3; ε_ud si procede | Verificado |
| **A_s,min** | 9.2.1.1(1), **(9.1)** (98424) | `flexion.as_min` | **A_s,min = (W/z)·(f_ctm,fl/f_yd), z ≈ 0,8h**; alternativa 1,2·A_s,nec para elementos secundarios | Verificado. **En v0.1.0 se usaba la expresión (9.1N) de la EN 1992-1-1, que NO es la del Anejo 19: corregido** |
| A_s,max | 9.2.1.1(3) (98424) | `flexion.as_max` | 0,04·A_c fuera de solapes | Verificado |
| Sujeción de barras comprimidas | 9.2.1.2(3) (98425) | `_common_checks` | separación transversal ≤ 15·φ | Verificado (nuevo en v0.2.0) |
| Separación libre mínima | 8.2(2) (98405) | `section.min_clear_spacing` | max(k1·φ; d_g + k2; 20 mm), k1 = 1, k2 = 5 mm | Verificado |
| Barras en capas superpuestas en la misma vertical | 8.2(3) (98405) | colocación de barras en `section.py` | — | Cumplido por construcción si las capas tienen igual número de barras |
| Recubrimientos | 8.1(2) → apartado 43.4.1 del CE | No implementado | lo introduce el usuario | Remite al articulado |
| Anchura eficaz del ala | 5.3.2.1 | No implementado | lo introduce el usuario | — |

## Matriz de trazabilidad (cortante ELU de vigas, v0.3.0)

| Magnitud / regla | Apartado (BOE pág.) | Implementación | Valor oficial | Estado |
|---|---|---|---|---|
| Procedimiento general, V_Rd = V_Rd,s + V_ccd + V_td | 6.2.1(2), (6.1) (98359) | `cortante.py` | V_ccd = V_td = 0 (canto constante) | Verificado |
| Zonas sin armadura de cálculo; armadura mínima obligatoria | 6.2.1(3)-(5) (98359) | `shear_beam` | V_Ed ≤ V_Rd,c ⇒ mínima | Verificado (sin aplicar las excepciones de 6.2.1(4)) |
| V_Ed − V_ccd − V_td ≤ V_Rd,max | 6.2.1(6) (98359) | check «Compresión oblicua» | — | Verificado |
| V_Rd,c | 6.2.2(1), (6.2.a) (98359-98360) | `vrdc` | C_Rd,c = 0,18/γ_c; k = 1 + √(200/d) ≤ 2; ρ_l ≤ 0,02; k_1 = 0,15; σ_cp < 0,2·f_cd | Verificado |
| Valor mínimo | (6.2.b), (6.3) (98360) | `vrdc` | v_min = 0,035·k^(3/2)·f_ck^(1/2) | Verificado |
| Celosía, z | 6.2.3(1) (98362) | `z_shear_factor` | z = 0,9·d (habitual sin axil) | Verificado; aviso si N_Ed ≠ 0 |
| Inclinación de bielas | 6.2.3(2), **(6.7)** (98362) | `cot_theta_min/max` | **0,5 ≤ cot θ ≤ 2** (la EN 1992-1-1 usa 1 ≤ cot θ ≤ 2,5) | Verificado |
| V_Rd,s cercos verticales / inclinados | (6.8) / (6.13) (98362-98363) | `vrd_s` | — | Verificado |
| V_Rd,max verticales / inclinados | (6.9) / (6.14) (98363) | `vrd_max` | — | Verificado |
| ν_1 | (6.6) / 6.2.3(3) y (6.10) (98361, 98363) | `nu1_and_fywd` | 0,6(1 − f_ck/250); opción (6.10) con f_ywd = 0,8·f_ywk | Verificado |
| α_cw | 6.2.3(3) (98363) | `alpha_cw` | 1 para estructuras sin pretensado | Verificado |
| Área máxima eficaz | notas (6.12)/(6.15) (98363) | aviso | ≤ ½·α_cw·ν_1·f_cd/sen α (cot θ = 1) | Verificado (como aviso) |
| ΔF_td | 6.2.3(7), (6.18) (98364) | resultado informativo | 0,5·V_Ed·(cot θ − cot α) | Verificado (no se comprueba la armadura longitudinal) |
| Ángulo de la armadura de cortante | 9.2.2(1) (98427) | validación | 45° ≤ α ≤ 90° | Verificado |
| Proporción de cercos | 9.2.2(4) (98428) | hipótesis | β_3 = 0,5 | Verificado (solo cercos ⇒ se cumple) |
| ρ_w y ρ_w,min | 9.2.2(5), (9.4)-(9.5) (98428) | check | ρ_w = A_sw/(s·b_w·sen α); ρ_w,min = 0,08·√f_ck/f_yk | Verificado |
| s_l,max | 9.2.2(6), (9.6) (98428) | check | 0,75·d·(1 + cot α) | Verificado |
| s_t,max | 9.2.2(8), (9.8) (98428) | check | 0,75·d ≤ 600 mm | Verificado |
| Separación libre entre cercos | 8.2(2) (98405) | check y propuesta | max(φ; d_g + 5; 20 mm) | Verificado |
| Reducción β por cargas próximas a apoyos | 6.2.2(6), 6.2.3(8) | **No implementado** | — | Limitación declarada |
| Rasante ala-alma, juntas, torsión | 6.2.4, 6.2.5, 6.3 | **No implementado** | — | Limitación declarada |

## Matriz de trazabilidad (pilares, v0.4.0)

| Magnitud / regla | Apartado (BOE pág.) | Implementación | Valor oficial | Estado |
|---|---|---|---|---|
| Hipótesis y dominios de deformación (pivotes A, B, C) | 6.1(2)-(3), figura A19.6.1 (98357-98358) | `nm.py` | ε_cu2 / ε_c2 a (1 − ε_c2/ε_cu2)·h / ε_ud | Verificado |
| Excentricidad mínima | 6.1(4) (98357) | `pilares.py` | e_0 = h/30 ≥ 20 mm | Verificado |
| Imperfecciones | 5.2(5)-(7), (5.1)-(5.2) (98330) | `pilares.py` | θ_0 = 1/200; α_h = 2/√l ∈ [2/3, 1]; α_m = √(0,5(1 + 1/m)); e_i = θ_i·l_0/2 | Verificado (m = 1, elemento aislado) |
| e_i simplificada | 5.2(7) a), 5.2(9) (98330-98331) | opción | e_i = l_0/400 (pilares arriostrados) | Verificado |
| Despreciar el segundo orden | 5.8.2(6), 5.8.3.1 (98340-98341) | `pilares.py` | λ ≤ λ_lim = 20·A·B·C/√n | Verificado; **errata en B**, ver abajo |
| r_m | 5.8.3.1(1) (98340-98341) | `pilares.py` | M01/M02; r_m = 1 si no arriostrado o con cargas transversales | Verificado |
| Esbeltez | 5.8.3.2(1), (5.14) (98341) | `pilares.py` | λ = l_0/i (sección bruta) | Verificado |
| Longitud efectiva | figura A19.5.7, (5.15), (5.16) (98341) | `_l0` | β·l; arriostrados/no arriostrados con k1, k2 (mín. recomendado 0,1) | Verificado |
| Fluencia eficaz | 5.8.4(2), (5.19) (98343) | `pilares.py` | φ_ef = φ(∞,t_0)·M_0Eqp/M_0Ed | Verificado (φ(∞,t_0) lo aporta el usuario; 3.1.4 no implementado) |
| Momento equivalente | 5.8.8.2(2), (5.32) (98347) | `pilares.py` | M_0e = 0,6·M02 + 0,4·M01 ≥ 0,4·M02 | Verificado |
| Curvatura nominal | 5.8.8.2-5.8.8.3, (5.31)-(5.37) (98347-98348) | `pilares.py` | M_2 = N·e_2; e_2 = (1/r)·l_0²/c; c = 10 (8 con M de primer orden constante); 1/r_0 = ε_yd/(0,45d); d = h/2 + i_s; K_r con n_bal = 0,4; K_φ = 1 + β·φ_ef | Verificado (exige sección simétrica) |
| Pilar: h ≤ 4b | 9.5.1(1) (98433) | validación | — | Verificado |
| φ_min longitudinal | 9.5.2(1) (98433) | check | 12 mm | Verificado |
| **Armadura mínima por cara** | 9.5.2(2) (98434) | check | **A′_s,min = 0,05·N_Ed/f_yc,d, f_yc,d = f_yd ≯ 400 MPa** (propia del Anejo; distinta de la EN 1992-1-1) | Verificado |
| A_s,max | 9.5.2(3) (98434) | check | 0,04·A_c (0,08 en solapes, no comprobado) | Verificado |
| Barras de esquina | 9.5.2(4) (98434) | check | una por esquina | Verificado |
| Armadura transversal | 9.5.3(1), (3), (4), (6) (98434-98435) | checks | φ_t ≥ max(6; φ_max/4); s_cl,max = min(15·φ_min; 300; min(b, h)); 0,6 en zonas indicadas; barras a ≤ 150 mm de una sujeta | Verificado; ver nota sobre «G» |
| Flexión esviada | 5.8.9 | **No implementado** | — | Limitación declarada |
| Métodos de rigidez nominal y general | 5.8.7, 5.8.6 | **No implementado** | — | Limitación declarada |

## Erratas detectadas en el texto oficial

1. **ε_c2 en la tabla A19.3.1 (pág. 98308).** La columna de relaciones analíticas imprime
   «ε_c2 (‰) = 2,0 + 0,85·[(f_ck − 50)]^0,53», pero los valores tabulados de la misma tabla
   (2,2; 2,3; 2,4; 2,5; 2,6 ‰ para C55 a C90) solo se obtienen con el coeficiente **0,085**:
   con 0,85 resultaría ε_c2 ≈ 4,0 ‰ para C55/67. Se implementa 0,085, coherente con los valores
   tabulados. Lo comprueba `test_eps_c2_errata_in_official_formula`.
2. **ε_cu1 (misma tabla).** El paréntesis está mal colocado («(98 − f_cm/100)»); los valores
   tabulados corresponden a 2,8 + 27·[(98 − f_cm)/100]^4, que es lo implementado.
3. **f_ctk,0,05 de C60/75.** La tabla da 3,1 MPa, mientras que 0,7·f_ctm (con f_ctm = 4,355 sin
   redondear) da 3,05. El valor tabulado procede de aplicar 0,7 a f_ctm ya redondeada. Es una
   diferencia de redondeo, no de fórmula.
4. **Coeficiente B de la esbeltez límite (5.13), pág. 98340.** El texto imprime
   «B = 1 + √(1 + 2ω) (si ω no es conocido, se puede usar B = 1,1)». Con esa expresión B ≥ 2 para
   cualquier ω ≥ 0, incompatible con el valor por defecto 1,1 del mismo apartado, y λ_lim casi se
   duplicaría (del lado de la inseguridad). Se adopta B = √(1 + 2ω), coherente con B = 1,1
   (ω ≈ 0,1). Test: `test_slenderness_and_limit_manual`.
5. **s_cl,max en 9.5.3(3), pág. 98434.** El texto imprime «min(G, h)»; «G» no está definido. Se
   interpreta como la menor dimensión de la sección, min(b, h) (lectura del lado de la seguridad).

## Dependencias respecto de otras disposiciones (no consultadas)

- **Artículos 34 y 35 del Código Estructural**: propiedades de ductilidad de los aceros. Solo
  intervienen con la rama inclinada del diagrama; con la rama horizontal (por defecto) no se usan.
- **Apartado 43.4.1 del Código Estructural**: recubrimientos mínimos (el usuario introduce c_nom).
- **Bases de cálculo / combinación de acciones**: el usuario introduce directamente M_Ed.

## Otros apartados relevantes identificados para fases futuras

- 5.6.3(2): en rótulas plásticas, x_u/d ≤ 0,45 (f_ck ≤ 50) y ≤ 0,35 (f_ck ≥ 55).
- 6.1(4): excentricidad mínima e_0 = h/30 ≥ 20 mm en secciones comprimidas (pilares, fase 4).
- 6.1(5): deformación media limitada a ε_c2 en partes con carga aproximadamente centrada.
- 9.2.1.2(1)-(2): momento de empotramiento parcial β1 = 0,15 en apoyos; reparto de la armadura
  en el ala.
- 6.2 (cortante, fase 3), 7.3 y 7.4 (ELS, fase 5).
