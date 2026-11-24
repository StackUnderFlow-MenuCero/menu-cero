# Diseño del algoritmo de Menú Cero

Este documento formaliza el problema de optimización que resuelve Menú Cero, define el modelo matemático y sus restricciones, y presenta el algoritmo voraz con ajuste que se implementa en `src/menucero/voraz.py` (#20 y #23) y se contrasta contra fuerza bruta en `src/menucero/fuerza_bruta.py` (#24). El contrato de los datos de entrada está en [`docs/datos.md`](datos.md).

---

## 1. Problema

En un restaurante o cocina económica con menú fijo, el desperdicio se concentra en ingredientes perecederos usados en platillos de baja rotación cuya existencia supera lo que el menú fijo consumirá antes de la fecha de caducidad. A partir de una fecha de referencia explícita (`hoy`), del inventario disponible (cantidades, caducidades y costos), del recetario existente (platillos fijos y recetas secundarias) y de la demanda diaria estimada, el algoritmo debe decidir **qué platillos proponer como menú del día y cuántas porciones adicionales preparar de cada uno**, priorizando los ingredientes más próximos a caducar sin exceder el inventario disponible ni la demanda esperada y usando exclusivamente recetas que el negocio ya sabe preparar.

---

## 2. Notación

### Conjuntos y tamaños

| Símbolo | Significado |
|---|---|
| $I$ | Conjunto de ingredientes vigentes ($d_i \ge 0$), con $n = \lvert I \rvert$. Los ingredientes ya caducados ($d_i < 0$) se excluyen antes de optimizar y se reportan como merma ya perdida. |
| $J$ | Conjunto de recetas existentes (`fijo` y `secundaria`), con $m = \lvert J \rvert$. |
| $J_{\text{fijo}}, J_{\text{sec}}$ | Partición de $J$ en recetas del menú fijo y recetas secundarias. |
| $E$ | Número total de pares ingrediente–receta ($E = \sum_{j \in J} \lvert \text{ingredientes}(j) \rvert$). |
| $k$ | Número máximo de ingredientes en una receta ($k = \max_{j \in J} \lvert \text{ingredientes}(j) \rvert$). |

### Parámetros (calculados respecto a `hoy`)

| Símbolo | Unidad | Definición |
|---|---|---|
| $s_i$ | kg | Cantidad en inventario del ingrediente $i \in I$ (`cantidad_kg`). |
| $c_i$ | MXN/kg | Costo unitario del ingrediente $i$ (`costo_kg`). |
| $d_i$ | días | Días para caducar: $\text{fecha\_caducidad}_i - \text{hoy}$ ($0$ si vence hoy). |
| $p_i$ | — | Prioridad por urgencia: $p_i = \dfrac{1}{d_i + 1} \in (0, 1]$ (hoy $= 1$, mañana $= 0.5$, en 7 días $= 0.125$). |
| $q_{ij}$ | kg/porción | Kilogramos del ingrediente $i$ requeridos por una porción de la receta $j$ ($0$ si $j$ no usa $i$). |
| $F_j$ | porciones/día | Demanda diaria estimada en el menú fijo (`demanda_fija`; $0$ para $j \in J_{\text{sec}}$). |
| $M_j$ | porciones/día | Demanda adicional máxima estimada si la receta $j$ se ofrece como menú del día (`demanda_menu_dia`). |

### Cantidades derivadas por ingrediente

Para cada ingrediente vigente $i \in I$:

1. **Reserva diaria del menú fijo ($r_i$, kg/día):** consumo esperado por los platillos de la carta fija cada día:
   $$r_i = \sum_{j \in J_{\text{fijo}}} F_j \cdot q_{ij}$$
2. **Inventario disponible hoy ($a_i$, kg):** existencia que puede destinarse hoy al menú del día sin quitarle ingredientes al menú fijo de hoy:
   $$a_i = \max(0,\; s_i - r_i)$$
   Para ingredientes faltantes en el inventario o ya caducados se toma $a_i = 0$, impidiendo preparar cualquier receta que los requiera.
3. **Kilogramos en riesgo ($R_i$, kg):** cantidad que el menú fijo no alcanzará a consumir durante los $d_i + 1$ días de vida útil restantes (incluyendo `hoy`):
   $$R_i = \max\bigl(0,\; s_i - r_i \cdot (d_i + 1)\bigr)$$
   El **valor económico en riesgo** es $R_i \cdot c_i$ (MXN).

---

## 3. Modelo formal

### Variables de decisión

$$x_j \in \{0, 1, \dots, M_j\} \qquad \forall\, j \in J$$

donde $x_j$ representa el número entero de porciones adicionales de la receta $j$ propuestas en el menú del día (equivalentemente, $y_j \in \{0, 1\}$ indica si la receta entra al menú del día y $x_j \le M_j \cdot y_j$).

### Restricciones

1. **Inventario disponible (sin afectar la reserva del menú fijo de hoy):**
   $$\sum_{j \in J} q_{ij} \cdot x_j \le a_i \qquad \forall\, i \in I$$
2. **Demanda estimada del menú del día:**
   $$0 \le x_j \le M_j, \quad x_j \in \mathbb{Z} \qquad \forall\, j \in J$$
3. **Solo recetas existentes:**
   $$j \in J = J_{\text{fijo}} \cup J_{\text{sec}}$$
   (no se inventan platillos ni se alteran las proporciones $q_{ij}$).

### Función objetivo

$$\text{maximizar} \quad V(x) = \sum_{i \in I} p_i \cdot \min\!\left(\sum_{j \in J} q_{ij} \cdot x_j,\; R_i\right)$$

- El término $\min(\text{usado}_i, R_i)$ asegura que solo suma valor el aprovechamiento de kilogramos realmente en riesgo: usar inventario sano por encima de $R_i$ no aporta ganancia en $V(x)$.
- Además, la regla de asignación acota las porciones a $\lceil \text{pendiente}_i / q_{ij} \rceil$ para evitar sobreconsumir stock sano que el menú fijo necesitará en días posteriores (evitando el sobreuso observado en estrategias que asignan hasta agotar $a_i$).

---

## 4. Relación con la mochila 0/1 y justificación de la estrategia voraz

Cada receta es un objeto que se incluye o no en el menú del día (decisión 0/1), con una cantidad de porciones acotada por su demanda $M_j$. Como existe una restricción de capacidad independiente por cada ingrediente disponible ($a_i$), el problema constituye una **variante multidimensional y acotada de la mochila 0/1**, un problema **NP-difícil** para el cual no se conoce ningún algoritmo exacto de tiempo polinomial.

Por ello se resuelve de **forma aproximada con una estrategia voraz**: es rápida y escala a cientos o miles de ingredientes en milisegundos, aunque no garantiza alcanzar el óptimo global en todas las instancias. La calidad de la aproximación (cociente $V_{\text{voraz}} / V_{\text{óptimo}}$) se mide empíricamente contra una búsqueda por fuerza bruta sobre los $2^m$ subconjuntos de recetas en instancias pequeñas ($m \le 20$).

---

## 5. Algoritmo voraz con ajuste

### Idea general

Para evitar repetir preprocesamientos en la generación de múltiples variantes y en la comparación con fuerza bruta, el algoritmo se divide en dos fases:

1. **`PREPARAR(ingredientes, recetas, hoy)`:** separa ingredientes caducados, calcula $d_i, p_i, r_i, a_i, R_i$, construye un **índice invertido** `usa[i]` con las recetas que contienen el ingrediente $i$, y ordena los ingredientes con $R_i > 0$ en la lista $L$ con desempate determinista por `(p_i desc, R_i * c_i desc, id asc)`.
2. **`LLENAR(estado, variante, excluidas, permitidas)`:** realiza hasta **dos pasadas**:
   - **Pasada 1 (`fijo`):** recorre $L$ del ingrediente más urgente al menos urgente; mientras quede `pendiente[i] > EPS`, evalúa las recetas fijas en `usa[i]` (permitidas y no excluidas) ordenadas por el criterio de la variante (con desempate por `receta.id` ascendente) y asigna el máximo de porciones permitido simultáneamente por demanda restante, inventario disponible y cantidad necesaria para cubrir `pendiente[i]`.
   - **Pasada 2 (`secundaria`):** si aún quedan ingredientes en riesgo sin cubrir tras la pasada principal, repite el proceso usando recetas `secundaria` (la variante `secundarias` ejecuta únicamente esta segunda pasada).

### Tolerancia numérica

En aritmética de punto flotante IEEE 754, cocientes exactos en base 10 como `1.16 / 0.04` producen `28.999999999999996`. Para evitar truncamientos erróneos se usa `EPS = 1e-9`:

- Tope de inventario: $\lfloor \text{resto}[h] / q_{hj} + \varepsilon \rfloor$
- Porciones necesarias: $\lceil \text{pendiente}[i] / q_{ij} - \varepsilon \rceil$
- Condición de pendiente cubierto: $\text{pendiente}[i] \le \varepsilon$

### Pseudocódigo

```text
GENERAR_PROPUESTAS(ingredientes, recetas, hoy, k = 5)
    estado ← PREPARAR(ingredientes, recetas, hoy)                   # O(n log n + E)
    propuestas ← []
    vistas ← ∅
    principal ← None
    para v en (base, sin_principal, economica, eficiencia, secundarias)[:k]:
        excluidas ← {principal} si (v == sin_principal y principal ≠ None) si no ∅
        porciones ← LLENAR(estado, v, excluidas, permitidas=None)
        si v == base y porciones ≠ ∅:
            principal ← argmax_j (porciones[j], j)
        si porciones ≠ ∅ y porciones no está en vistas:
            vistas.agregar(porciones)
            propuestas.agregar(MenuGenerado(v, porciones, VALOR_OBJETIVO(porciones, estado)))
    regresar propuestas ordenadas por valor V descendente (entre 3 y 5 si existen distintas)

PREPARAR(ingredientes, recetas, hoy)
    vigentes, _ ← separar_caducados(ingredientes, hoy)
    reserva ← reserva_diaria(recetas)                               # solo recetas fijo
    riesgo ← kg_en_riesgo(vigentes, recetas, hoy)
    disponible[i] ← max(0, s_i - reserva[i]) para i en vigentes     # 0 si falta o caducó
    p[i] ← 1 / (d_i + 1) para i en vigentes
    usa[i] ← lista de receta_id que contienen a i                   # índice invertido
    L ← [i en ordenar_por_prioridad(vigentes, hoy, riesgo) si riesgo[i] > EPS]
    regresar Estado(vigentes, recetas, p, disponible, riesgo, usa, L)

LLENAR(estado, variante, excluidas, permitidas)
    resto ← copia de estado.disponible
    pendiente ← copia de estado.riesgo
    porciones ← {}
    pasadas ← (secundaria,) si variante == secundarias si no (fijo, secundaria)
    para tipo en pasadas:
        para cada i en estado.orden:
            si pendiente[i] ≤ EPS: continuar
            candidatas ← [j en estado.usa[i] tal que
                          receta[j].tipo == tipo
                          y j no en excluidas
                          y (permitidas es None o j en permitidas)]
            ordenar candidatas por (-criterio(variante, j, estado), j)
            para cada j en candidatas:
                tope_demanda ← M_j - porciones.get(j, 0)
                tope_stock   ← min_{h en j} ⌊resto.get(h, 0) / q_hj + EPS⌋
                necesarias   ← ⌈pendiente[i] / q_ij - EPS⌉
                x ← min(tope_demanda, tope_stock, necesarias)
                si x ≥ 1:
                    porciones[j] ← porciones.get(j, 0) + x
                    para h en ingredientes de j:
                        resto[h] ← max(0, resto[h] - x · q_hj)
                        pendiente[h] ← max(0, pendiente[h] - x · q_hj)
                si pendiente[i] ≤ EPS:
                    salir del ciclo de candidatas
    regresar porciones
```

### Variantes (de 3 a 5 propuestas)

El orden de ingredientes $L$ es el mismo en todas las variantes; cada variante modifica el criterio de ordenamiento de recetas candidatas o el subconjunto permitido:

| Variante | Criterio de orden de recetas ($R_h > \varepsilon$) | Qué prioriza |
|---|---|---|
| `base` | $\sum_{h:\, R_h > \varepsilon} p_h \cdot q_{hj}$ | Máximo rescate ponderado por urgencia. |
| `sin_principal` | Igual que `base`, excluyendo la receta con más porciones de `base` (desempate por `id`) | Diversidad operativa cuando el encargado prefiere otra opción principal. |
| `economica` | $\sum_{h:\, R_h > \varepsilon} p_h \cdot q_{hj} \cdot c_h$ | Rescatar primero los ingredientes de mayor costo por kg. |
| `eficiencia` | $\dfrac{\sum_{h:\, R_h > \varepsilon} p_h \cdot q_{hj}}{\sum_{h} q_{hj}}$ | Maximizar rescate por kilogramo total consumido, cuidando el inventario sano. |
| `secundarias` | Igual que `base`, pero ejecutando únicamente la pasada `secundaria` | Ofrecer un menú del día nuevo sin promover platillos de la carta fija. |

Las propuestas con el mismo diccionario de porciones se eliminan por deduplicación y el conjunto resultante se ordena por $V(x)$ descendente. Si el inventario solo permite menos de 3 propuestas distintas, se devuelven únicamente las existentes sin fabricar duplicados.

---

## 6. Ejemplo resuelto

### Instancia de referencia (`hoy = 2026-11-16`)

**Inventario:**

| id | Ingrediente | $s_i$ (kg) | Caduca | $c_i$ (MXN/kg) | $d_i$ | $p_i$ | $r_i$ (kg/día) | $a_i$ (kg) | $R_i$ (kg) |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|
| `ING01` | Crema ácida | 2.0 | 2026-11-17 | 70 | 1 | 0.5000 | 0.42 | 1.58 | **1.16** |
| `ING02` | Champiñones | 1.5 | 2026-11-18 | 95 | 2 | 0.3333 | 0.09 | 1.41 | **1.23** |
| `ING03` | Pechuga de pollo | 8.0 | 2026-11-20 | 120 | 4 | 0.2000 | 1.05 | 6.95 | **2.75** |
| `ING04` | Tortilla de maíz | 6.0 | 2026-11-19 | 25 | 3 | 0.2500 | 2.73 | 3.27 | 0.00 |
| `ING05` | Bistec de res | 5.0 | 2026-11-18 | 180 | 2 | 0.3333 | 3.00 | 2.00 | 0.00 |

**Recetas y demanda:**

- `REC01` *Pollo a la crema con champiñones* (`fijo`, $F=3$, $M=12$): `ING03` 0.150, `ING01` 0.040, `ING02` 0.030. Puntaje `base` $= 0.0600$.
- `REC02` *Tacos de bistec* (`fijo`, $F=25$, $M=5$): `ING05` 0.120, `ING04` 0.090. Puntaje `base` $= 0.0000$.
- `REC03` *Enchiladas suizas* (`fijo`, $F=6$, $M=10$): `ING03` 0.100, `ING01` 0.050, `ING04` 0.080. Puntaje `base` $= 0.0450$.
- `REC07` *Crema de champiñones* (`secundaria`, $F=0$, $M=10$): `ING02` 0.080, `ING01` 0.050. Puntaje `base` $= 0.0517$.

Orden de ingredientes en riesgo: $L = [\text{ING01}, \text{ING02}, \text{ING03}]$.

### Traza paso a paso (variante `base`)

| Pasada | Ingrediente (pendiente) | Receta | Tope demanda | Tope inventario | Necesarias | $x$ asignado |
|---|---|---|---:|---:|---:|---:|
| `fijo` | `ING01` (1.16 kg) | `REC01` | 12 | 39 | 29 | **12** |
| `fijo` | `ING01` (0.68 kg) | `REC03` | 10 | 22 | 14 | **10** |
| `fijo` | `ING02` (0.87 kg) | `REC01` | 0 | 15 | 29 | 0 |
| `fijo` | `ING03` (0.00 kg) | — | — | — | — | *(ya cubierto)* |
| `secundaria` | `ING01` (0.18 kg) | `REC07` | 10 | 12 | 4 | **4** |
| `secundaria` | `ING02` (0.55 kg) | `REC07` | 6 | 8 | 7 | **6** |

### Resultado y propuestas generadas

- **Propuesta `base`:** `{REC01: 12, REC03: 10, REC07: 10}` (32 porciones, 3 platillos).
  - Rescatado: `ING01` 1.16 kg, `ING02` 1.16 kg, `ING03` 2.75 kg → **5.07 de 5.14 kg** (**98.6 %** de aprovechamiento).
  - Costo recuperado: **$521.40 MXN**.
  - Valor objetivo: **$V = 1.51667$** (coincide con el óptimo exacto de fuerza bruta sobre los 16 subconjuntos).
- **Conjunto de propuestas de `GENERAR_PROPUESTAS`:** devuelve **3 propuestas distintas** (`economica` y `eficiencia` coinciden con `base` y se descartan por repetidas):
  1. `base`: `REC01: 12, REC03: 10, REC07: 10` ($V = 1.51667$, 98.6 %).
  2. `sin_principal` (excluye `REC01`): `REC03: 10, REC07: 10` ($V = 0.96667$, 54.5 %).
  3. `secundarias`: `REC07: 10` ($V = 0.51667$, 25.3 %).

---

## 7. Análisis de complejidad

*(Se completará en #29 una vez integrados los resultados experimentales de calidad contra fuerza bruta de #24 y los benchmarks de tiempo y memoria con $n \in \{20, 100, 500, 1000\}$ de #27.)*

Resumen preliminar de las cotas de diseño:

- **Voraz (tiempo):** $O(n \log n + E \cdot (k + \log m))$; con recetas de tamaño acotado ($k$ constante), $E = O(m)$ y resulta $O(n \log n + m \log m)$.
- **Voraz (espacio):** $O(n + m + E)$.
- **Fuerza bruta (tiempo):** $O(2^m \cdot (n + E \cdot k))$, inviable para $m$ grande.
