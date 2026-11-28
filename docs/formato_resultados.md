# Formato de los resultados de la fuerza bruta y del benchmark

La página pública (#49) tiene lista la sección **«Voraz contra fuerza bruta»**. La arma `scripts/pagina.py` en cuanto aparecen estos archivos en `resultados/`. Mientras no existan, la página dice que la parte está en desarrollo. Cada parte se muestra por separado: la calidad aparece cuando llega `calidad.csv` y la eficiencia cuando llega `benchmark.csv`.

| Archivo | Lo genera | Parte de la página |
|---|---|---|
| `resultados/calidad.csv` | la comparación de calidad de #24 | Tabla 5 y el texto de calidad |
| `resultados/benchmark.csv` | `scripts/benchmark.py` de #27 | Tablas 6 y 7 y el texto de eficiencia |
| `resultados/tiempo_vs_n.png`, `ram_vs_n.png`, `voraz_vs_fuerza_bruta.png` | las gráficas de #27 | Figuras 4 a 6 (cada una es opcional) |

Si un archivo existe pero no tiene el formato, la construcción de la página falla con un mensaje que dice el archivo, la fila y la columna. Así no se publica una tabla rota. Las columnas pueden venir en cualquier orden, y las columnas de más se ignoran.

Si el formato les queda mejor de otra manera, se cambia en `scripts/pagina.py` (constantes `COLUMNAS_CALIDAD` y `COLUMNAS_BENCHMARK`) y en este documento.

## `calidad.csv` (#24)

Una fila por instancia pequeña. #24 pide 30, con m de 6 a 14 recetas.

| Columna | Tipo | Qué es |
|---|---|---|
| `instancia` | entero | número de la instancia |
| `semilla` | entero | semilla del generador sintético (#17) |
| `n` | entero | ingredientes |
| `m` | entero | recetas candidatas |
| `valor_voraz` | decimal | `V` del menú del voraz (`generar_menu`, variante `base`) |
| `valor_optimo` | decimal | `V` del mejor subconjunto que encontró la fuerza bruta |
| `tiempo_voraz_ms` | decimal | tiempo del voraz en esa instancia, en ms |
| `tiempo_fuerza_bruta_ms` | decimal | tiempo de la fuerza bruta en esa instancia, en ms |

La página calcula `valor_voraz / valor_optimo`. Si `valor_optimo` es 0, el cociente cuenta como 1. Si `valor_voraz` es mayor que `valor_optimo`, la construcción falla, porque significa que la fuerza bruta no está usando la misma regla de llenado o el mismo `V` que el voraz.

## `benchmark.csv` (#27)

Una fila por algoritmo y tamaño, con las 5 semillas juntas.

| Columna | Tipo | Qué es |
|---|---|---|
| `algoritmo` | `voraz` o `fuerza_bruta` | qué se midió |
| `n` | entero | ingredientes |
| `m` | entero | recetas |
| `mediana_ms` | decimal | mediana del tiempo, en ms |
| `p25_ms`, `p75_ms` | decimal | cuartiles del tiempo, en ms; vacíos si `extrapolado = 1` |
| `pico_kib` | decimal | pico de memoria con `tracemalloc`, en KiB; puede ir vacío si `extrapolado = 1` |
| `extrapolado` | `0` o `1` | `1` si el tiempo se estimó a partir de lo medido en lugar de medirse |
| `cpu` | texto | procesador del equipo donde se midió |
| `python` | texto | versión de Python |

Tiene que haber al menos una fila medida (`extrapolado = 0`) de cada algoritmo. La página toma el CPU y la versión de Python de la primera fila.

Ejemplo (los números son inventados):

```csv
algoritmo,n,m,mediana_ms,p25_ms,p75_ms,pico_kib,extrapolado,cpu,python
voraz,1000,400,17.4,16.53,18.444,1850,0,AMD Ryzen 5 5600,3.13.0
fuerza_bruta,44,20,4194.304,4068.475,4362.076,70,0,AMD Ryzen 5 5600,3.13.0
fuerza_bruta,1000,400,1.0329e+118,,,,1,AMD Ryzen 5 5600,3.13.0
```

## Para verlo antes de subirlo

```bash
uv run python scripts/pagina.py                 # escribe _site/
uv run python -m http.server -d _site 8000      # http://localhost:8000/#fuerza-bruta
```

`tests/ejemplos/fuerza_bruta/` tiene un ejemplo completo con números inventados. Las pruebas de la página lo usan.
