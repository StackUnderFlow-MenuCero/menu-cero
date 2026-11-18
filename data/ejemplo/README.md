# Datos de ejemplo

Juego pequeño para desarrollar y probar la carga (#13), la pantalla del avance (#14) y el algoritmo (#20, #23). Sigue el formato de `docs/datos.md` (#7) y sale del negocio tipo de la caracterización (#8).

| Archivo | Contenido |
|---|---|
| `inventario.csv` | 12 ingredientes perecederos |
| `recetas.csv` | 7 recetas: 5 del menú fijo y 2 secundarias |
| `demanda.csv` | la demanda de las 7 recetas |

## Fecha de referencia

**Úsalo con hoy = martes 17 de noviembre de 2026.** En la app, elige esa fecha en «Fecha de referencia». En el código, pásala como `hoy=date(2026, 11, 17)`.

Con otra fecha cambian los días para caducar y, con ellos, todos los resultados. Por ejemplo, desde el miércoles 18 la crema ya está caducada y la carga lo avisa.

## Qué contiene

Los ingredientes ING01 a ING05 y las recetas REC01, REC02, REC03 y REC07 tienen los mismos valores que el ejemplo de referencia de las guías (sección 4.6). Encima se agregan 7 ingredientes y 3 recetas.

Por eso los resultados **no** son los del ejemplo de referencia: aquí la fecha es otra y hay más recetas. Las pruebas del algoritmo usan el ejemplo de referencia, que está en `tests/conftest.py` (#11).

| id | Ingrediente | kg | Caduca | d | Kg en riesgo |
|---|---|---:|---|---:|---:|
| ING01 | Crema ácida | 2.0 | 2026-11-17 | 0 | 1.58 |
| ING02 | Champiñones | 1.5 | 2026-11-18 | 1 | 1.32 |
| ING03 | Pechuga de pollo | 8.0 | 2026-11-20 | 3 | 3.80 |
| ING04 | Tortilla de maíz | 6.0 | 2026-11-19 | 2 | 0 |
| ING05 | Bistec de res | 5.0 | 2026-11-18 | 1 | 0 |
| ING06 | Queso fresco | 2.0 | 2026-11-20 | 3 | 1.44 |
| ING07 | Jitomate saladet | 5.0 | 2026-11-21 | 4 | 1.80 |
| ING08 | Cebolla blanca | 3.0 | 2026-11-27 | 10 | 0.58 |
| ING09 | Chile poblano | 2.5 | 2026-11-18 | 1 | 1.90 |
| ING10 | Calabacita | 3.0 | 2026-11-19 | 2 | 1.20 |
| ING11 | Carne molida de res | 2.0 | 2026-11-19 | 2 | 0 |
| ING12 | Papa blanca | 4.0 | 2026-11-30 | 13 | 0 |

- **Vencen en menos de 48 horas** (`d ≤ 1`): crema, champiñones, bistec y chile poblano.
- **Platillos de poca salida** (3 porciones al día o menos): REC01 *Pollo a la crema con champiñones*, que usa la crema y los champiñones, y REC04 *Chiles rellenos de queso*, que usa el chile poblano y el queso.
- **Recetas secundarias:** REC06 *Calabacitas con queso* y REC07 *Crema de champiñones*.
- **Lo que el menú fijo sí consume a tiempo:** el bistec y la tortilla (por los tacos, con 25 porciones al día), la carne molida y la papa. Por eso no tienen kg en riesgo.
- **Total en riesgo:** 13.62 kg, con un valor de $1,048.70.

## Resultados esperados

Valores calculados con una implementación de referencia del diseño de las guías, con hoy = 2026-11-17. Sirven para comparar cuando el voraz (#20, #23) y las métricas (#21) estén listos.

| Variante | Porciones del menú del día | V | Kg rescatados | Aprovechamiento | Costo recuperado |
|---|---|---:|---:|---:|---:|
| base | REC01 12 · REC03 10 · REC04 8 · REC05 4 · REC06 8 · REC07 10 | 4.25455 | 10.30 | 75.6 % | $786.80 |
| sin_principal (sin REC01) | REC03 10 · REC04 8 · REC05 4 · REC06 8 · REC07 10 | 3.14455 | 7.66 | 56.2 % | $503.00 |
| secundarias | REC06 8 · REC07 10 | 1.47455 | 3.38 | 24.8 % | $200.20 |

- **Variantes que se descartan:** `economica` y `eficiencia` dan lo mismo que `base`, así que `generar_propuestas` devuelve 3 propuestas.
- **Fuerza bruta (#24):** encuentra el mismo valor que el voraz.
- **Lo que no se rescata:** 3.32 kg. Sobre todo pechuga (1.0 kg), chile poblano (0.7 kg), jitomate (0.6 kg) y queso (0.56 kg). La demanda del menú del día no alcanza para usarlos.

## Archivos inválidos

Las copias con errores para probar la validación están en `tests/datos/`. Ahí se explica qué error trae cada una.
