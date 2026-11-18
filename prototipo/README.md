# Prototipo v0 del voraz (Checkpoint 1)

Primera solución ejecutable de Menú Cero. Está en un solo archivo, `voraz_v0.py`, y solo usa la biblioteca estándar de Python. Sirve para el Checkpoint 1 y, después, como punto de comparación para el voraz definitivo de `src/menucero/voraz.py` (#20 y #23).

## Cómo correrlo

Desde la raíz del repositorio:

```bash
uv run python prototipo/voraz_v0.py data/ejemplo --hoy 2026-11-17
uv run pytest tests/test_prototipo_v0.py
```

Los datos de ejemplo están pensados para hoy = 2026-11-17 (ver `data/ejemplo/README.md`). Con otra fecha cambian los días para caducar y el resultado.

## Qué hace

1. **Lee** `inventario.csv`, `recetas.csv` y `demanda.csv` con el formato de `docs/datos.md`. No valida: eso es la carga de #13.
2. **Calcula la urgencia** de cada ingrediente vigente (los caducados se descartan):
   - días para caducar `d` y prioridad `p = 1/(d + 1)`;
   - reserva del menú fijo: `Σ demanda_fija · kg_por_porcion`;
   - kg en riesgo: `max(0, cantidad − reserva · (d + 1))`, lo que el menú fijo no alcanza a usar antes de que caduque.
3. **Da un puntaje a cada receta:** `Σ p · min(kg_por_porcion, riesgo)` sobre sus ingredientes.
4. **Elige de forma voraz:** recorre las recetas de mayor a menor puntaje y a cada una le asigna todas las porciones posibles, sin pasar su demanda del menú del día ni el inventario que queda.
5. **Reporta** los kg en riesgo aprovechados y el valor `V = Σ p · min(usado, riesgo)`.

## Resultado con los datos de ejemplo

| Receta | Porciones |
|---|---:|
| REC04 Chiles rellenos de queso | 8 |
| REC01 Pollo a la crema con champiñones | 12 |
| REC07 Crema de champiñones | 10 |
| REC03 Enchiladas suizas | 10 |
| REC06 Calabacitas con queso | 8 |
| REC05 Picadillo de res con papa | 4 |

Aprovecha 10.30 de 13.62 kg en riesgo (75.6 %), con V = 4.25455, en menos de 1 ms. En este ejemplo chico coincide con la propuesta `base` que espera `data/ejemplo/README.md`; con más recetas e ingredientes (#17, #19) las dos versiones se separan.

## Complejidad aproximada

Con `n` ingredientes, `m` recetas y `E` pares receta–ingrediente (las filas de `recetas.csv`, `E ≤ n · m`):

| Paso | Costo |
|---|---|
| Leer los CSV | O(n + E) |
| Reserva, días, prioridad y riesgo | O(n + E) |
| Puntaje de todas las recetas | O(E) |
| Ordenar las recetas por puntaje | O(m log m) |
| Asignar porciones y descontar inventario | O(E) |
| Ordenar los ingredientes para el reporte | O(n log n) |
| **Total** | **O(n log n + m log m + E)** |

La memoria es O(n + E). Como cada receta tiene pocos ingredientes, `E` crece casi como `m` y el voraz es prácticamente lineal-logarítmico. En cambio, una búsqueda exhaustiva tiene que probar al menos `2^m` combinaciones de recetas (más aún si también varía el número de porciones): con 30 recetas ya son más de mil millones. La fuerza bruta (#24) solo se usará con `m ≤ 20`, para medir qué tan cerca del óptimo queda el voraz.

## Limitaciones y lo que cambia en el voraz definitivo

| v0 | Voraz definitivo (#20, #23) |
|---|---|
| El puntaje de cada receta se calcula una vez y no cambia al asignar porciones. | Recorre los ingredientes del más urgente al menos urgente y recalcula lo que falta por salvar. |
| Prepara todas las porciones posibles aunque el ingrediente ya esté salvado. Por ejemplo, usa 1.40 kg de calabacita cuando solo 1.20 kg estaban en riesgo; los 0.20 kg de más los habría usado el menú fijo en los días siguientes. | Prepara solo las porciones necesarias para salvar cada ingrediente. |
| Genera un solo menú. | Genera de 3 a 5 propuestas (variantes y recetas secundarias). |
| No valida los CSV. | Usa la carga con validación de #13. |

Que el voraz definitivo dé un `V` mayor **no está garantizado**. Una prueba preliminar con 200 instancias aleatorias (40 ingredientes, 15 recetas) y una implementación de referencia del diseño de las guías dio esto:

| Comparación de `V` contra la mejor de las 5 variantes | Instancias |
|---|---:|
| Mismo valor | 138 |
| v0 mayor | 44 |
| v0 menor | 18 |

A cambio, v0 usa en promedio 6.06 kg por instancia por encima de lo que estaba en riesgo: inventario que el menú fijo necesitaba en los días siguientes y que `V` no castiga. Medir las dos cosas juntas (`V` y kg usados de más) y comparar contra la fuerza bruta es parte del Checkpoint 2. Como todo voraz, ninguna de las dos versiones garantiza el óptimo.
