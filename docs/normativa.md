# Referencia normativa y estado de verificación

## Norma principal

- **Código Estructural**, aprobado por el **Real Decreto 470/2021, de 29 de junio**
  (BOE-A-2021-13681, BOE n.º 190, de 10/08/2021).
- **Anejo 19**: *Proyecto de estructuras de hormigón. Reglas generales y reglas para edificación*.
- Documento oficial: <https://cdn.transportes.gob.es/portal-web-transportes/ministerio/normativa/codigo-estructural/anejo_19._proyecto_de_estructuras_de_hormigon._reglas_generales.pdf>

## Limitación de acceso a la fuente (importante)

Durante el desarrollo de la versión 0.1.0, la política de red del entorno de
desarrollo **bloqueó** el acceso a `cdn.transportes.gob.es`, `cdn.mitma.gob.es`,
`boe.es` y las réplicas conocidas del documento. Por tanto:

1. **No se ha podido cotejar el texto oficial del Anejo 19** apartado por apartado.
2. Los coeficientes parciales γ_c y γ_s (tabla 2.1, 2.4.2.4) se han contrastado con
   extractos del PDF oficial obtenidos a través de un buscador (fuente secundaria):
   persistente/transitoria γ_c = 1,5, γ_s = 1,15; accidental γ_c = 1,3, γ_s = 1,0.
3. El resto de ecuaciones y parámetros se han implementado siguiendo la estructura y
   numeración de la EN 1992-1-1:2004, que el Anejo 19 transpone con sus elecciones
   nacionales. Cada parámetro está marcado como **pendiente de verificación** en
   `backend/core/parameters.py` y en la interfaz («Configuración normativa»).

**Acción requerida antes de considerar validado cualquier módulo:** cotejar cada fila
de la tabla siguiente con el texto oficial y actualizar el estado del parámetro.

## Matriz de trazabilidad (flexión ELU de vigas)

| Magnitud / regla | Apartado | Implementación | Valor adoptado | Estado |
|---|---|---|---|---|
| γ_c, γ_s | 2.4.2.4, tabla 2.1 | `parameters.py` | 1,5 / 1,15 (pers.); 1,3 / 1,0 (acc.) | Confirmado (fuente secundaria) |
| f_cm, f_ctm, f_ctk, E_cm, ε_c1, ε_cu1, ε_c2, ε_cu2, n, ε_c3, ε_cu3 | 3.1.2–3.1.3, tabla 3.1 | `materials.Concrete` | relaciones analíticas de la tabla | Pendiente |
| f_cd = α_cc·f_ck/γ_c | 3.1.6(1), (3.15) | `Concrete.fcd` | α_cc = 1,0 | **Pendiente (parámetro nacional)** |
| f_ctd = α_ct·f_ctk,0,05/γ_c | 3.1.6(2), (3.16) | `Concrete.fctd` | α_ct = 1,0 | Pendiente |
| Parábola-rectángulo | 3.1.7(1), (3.17)-(3.18) | `sigma_parabola_rectangle` | — | Pendiente |
| Bloque rectangular λ, η | 3.1.7(3), (3.19)-(3.22) | `Concrete.lam/eta` | — | Pendiente |
| Reducción 10 % de η·f_cd si el ancho disminuye hacia la fibra comprimida | 3.1.7(3), nota | `analysis.width_decreases_towards_compressed_fibre` | — | Pendiente |
| Diagrama de cálculo del acero | 3.2.7(2), fig. 3.8 | `ReinforcingSteel.sigma` | rama horizontal o inclinada | Pendiente |
| E_s | 3.2.7(4) | `parameters.Es` | 200 000 MPa | Pendiente |
| ε_ud | 3.2.7(2), nota | `eps_ud_factor` | 0,9·ε_uk | Pendiente (solo rama inclinada) |
| Rango de f_yk | 3.2.2(3) | `ReinforcingSteel` | 400–600 MPa | Pendiente |
| ε_uk, k por designación (B400S, B500S, B400SD, B500SD) | Articulado del CE / Anejo C | `STEEL_GRADES` | clase B: 5 %, 1,08; clase C: 7,5 %, 1,15 | **Pendiente (otra disposición)** |
| Hipótesis de cálculo de secciones | 6.1(2) | `analysis.py` | — | Pendiente |
| Deformaciones límite | 6.1(5)-(6), fig. 6.1 | `analyse_bending` (pivotes A y B) | — | Pendiente |
| Criterio de ductilidad x_u/d | 5.5(4), (5.10a/b) | `flexion.ductility_limit` | δ = 1; k1 = 0,44; k2 = 1,25(0,6+0,0014/ε_cu2); k3 = 0,54; k4 = idem | **Pendiente (parámetros nacionales)**; ver decisiones |
| A_s,min | 9.2.1.1(1), (9.1N) | `flexion.as_min` | 0,26·f_ctm/f_yk·b_t·d ≥ 0,0013·b_t·d | **Pendiente (parámetro nacional)** |
| A_s,max | 9.2.1.1(3) | `flexion.as_max` | 0,04·A_c | **Pendiente (parámetro nacional)** |
| Separación libre mínima | 8.2(2) | `section.min_clear_spacing` | k1 = 1; k2 = 5 mm; 20 mm | **Pendiente (parámetros nacionales)** |
| Recubrimientos | 4.4.1 | No implementado | lo introduce el usuario | — |
| Anchura eficaz del ala | 5.3.2.1 | No implementado | lo introduce el usuario | — |

## Dependencias respecto de otras disposiciones

- **Articulado del Código Estructural** (caracterización de los aceros B400S, B500S,
  B400SD, B500SD; durabilidad y resistencias mínimas por clase de exposición): no
  consultado; las propiedades de ductilidad se marcan como pendientes.
- **Combinación de acciones** (Anejo 18 / bases de cálculo): fuera del alcance; el
  usuario introduce directamente M_Ed.

## Puntos que no han podido verificarse

1. Valor de α_cc adoptado en el Anejo 19 (la EN 1992-1-1 recomienda 1,0, pero algunos
   anejos nacionales adoptan 0,85).
2. Si el Anejo 19 modifica la expresión (9.1N) de cuantía mínima o añade cuantías
   geométricas mínimas propias.
3. Valores k1–k4 de 5.5(4) y su aplicabilidad como criterio de ductilidad sin redistribución.
4. Si el Anejo 19 mantiene las clases C12/15 y C16/20 para hormigón armado (el
   articulado puede exigir resistencias mínimas por durabilidad).
5. Propiedades de ductilidad (ε_uk, k) de cada designación de acero.
