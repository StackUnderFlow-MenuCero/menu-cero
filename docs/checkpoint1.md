# Checkpoint 1

Seminario de Integración de Desarrollo · equipo StackUnderFlow · semana del 16 al 19 de noviembre de 2026.

El Checkpoint 1 pide dejar claro qué problema resolvemos, por qué es relevante y cómo vamos a avanzar (problema, equipo, FODA y backlog inicial), y tener un algoritmo base funcional con su complejidad aproximada. Cada sección de este documento cubre uno de esos puntos.

## 1. Problema

Los puestos de comida con **menú fijo**, como las cocinas económicas frente a CUCEI, compran los ingredientes de todos sus platillos, se vendan mucho o poco. Lo que usan los platillos populares se gasta a tiempo; lo de los platillos de poca salida se queda en el refrigerador hasta caducar. El negocio pierde dinero, genera residuos y a veces termina quitando el platillo de la carta.

Por ejemplo, en nuestro negocio tipo los champiñones se compran por kilo y duran unos 5 días, pero el pollo a la crema usa 30 g por porción y se piden 3 al día: en 5 días se usan 450 g y se tira más de la mitad.

**Por qué es relevante.** Según el PNUMA (*Food Waste Index Report 2024*), en 2022 se desperdició cerca del 19 % de los alimentos disponibles para los consumidores, y los servicios de comida generaron alrededor del 28 % de ese desperdicio.

**Nuestra propuesta.** Un **menú del día** que se suma al menú fijo y se arma con lo que está por caducar. Un algoritmo voraz, variante de la mochila 0/1, elige qué platillos y cuántas porciones preparar para aprovechar primero lo más urgente, sin quitarle al menú fijo lo que necesita. Se valida simulando una semana solo con menú fijo (A) contra menú fijo + menú del día (B). La caracterización completa está en [`datos.md`](datos.md#caracterización-del-negocio-tipo).

## 2. Equipo

| Rol | Integrante | GitHub | Responsabilidad |
|---|---|---|---|
| A | Salvador | `SalvadorRGDev` | Datos y evaluación: formato y caracterización de los datos, simulación A vs B |
| B | Arath | `arcamp0130` | Algoritmo: modelos, prioridad, voraz y análisis de complejidad |
| C | Edwin | `edguzsv` | Prototipo: carga de los CSV, métricas y pantallas en Streamlit |
| D | Less | `alesspiz` | Soporte y documentación: generador de datos, fuerza bruta, mediciones, reporte y entrega |

## 3. FODA

| | Positivo | Negativo |
|---|---|---|
| **Interno** | **Fortalezas**<br>• El voraz es rápido: O(n log n + m log m + E), menos de 1 ms con los datos de ejemplo.<br>• Los datos tienen sustento: negocio tipo de CUCEI con precios y vida útil de fuentes públicas.<br>• Proceso ordenado: backlog en GitHub, CI y una revisión obligatoria en cada PR.<br>• Herramienta local y gratuita: no necesita servidor, internet ni base de datos. | **Debilidades**<br>• El voraz no garantiza el óptimo; falta compararlo con la fuerza bruta.<br>• Los datos son sintéticos: ningún negocio real los ha validado.<br>• Muchas tareas dependen unas de otras: un atraso en los modelos o en la carga frena el voraz y la app.<br>• `V` premia usar lo que está en riesgo, pero no castiga gastar inventario que el menú fijo necesita después. |
| **Externo** | **Oportunidades**<br>• El desperdicio de alimentos es un problema reconocido: 19 % según el PNUMA y la meta 12.3 de los ODS (reducirlo a la mitad para 2030).<br>• Ahorro directo para negocios pequeños: lo que no se tira ya no se vuelve a comprar.<br>• Se puede extender: restricción nutricional (#33), precios reales del SNIIM y otros tipos de negocio. | **Amenazas**<br>• La demanda cambia con el calendario: baja a 0.80 en exámenes y a 0.25 en vacaciones.<br>• Si el inventario se registra mal (fechas o kg), el menú propuesto también sale mal.<br>• Plazo corto: tres entregas en tres semanas, en paralelo con otras materias. |

## 4. Backlog inicial

El backlog está en el [tablero del proyecto](https://github.com/orgs/StackUnderFlow-MenuCero/projects/1): 5 issues padre (los objetivos OP1 a OP4 y Soporte) y 32 tareas, cada una con responsable, etiqueta y milestone.

| Milestone | Fecha | Tareas | Contenido |
|---|---|---:|---|
| M0 · Avance intermedio | mié 18 nov | 12 | Repositorio y CI, formato y datos de ejemplo, caracterización, modelos, prioridad, carga, pantalla mínima y, para este checkpoint, el prototipo v0 y este documento |
| M1 · Datos completos y voraz principal | vie 20 nov | 6 | Generador de datos, diseño formal, dataset de demostración, voraz principal y métricas |
| M2 · Prototipo completo y experimentos | mar 24 nov | 6 | Variantes del voraz, fuerza bruta, simulador, pantalla de propuestas, mediciones y corridas |
| M3 · Evaluación y documentación | mié 25 nov | 5 | Análisis de complejidad, demostración A vs B, análisis de resultados y borrador del reporte |
| M4 · Entrega final | vie 27 nov | 3 | Integración, presentación y entrega |

## 5. Algoritmo base

La primera solución ejecutable es el **prototipo v0 del voraz** (#40), en [`prototipo/`](../prototipo/README.md):

```bash
uv run python prototipo/voraz_v0.py data/ejemplo --hoy 2026-11-17
```

1. Calcula para cada ingrediente los días para caducar `d`, la prioridad `p = 1/(d + 1)` y los kg en riesgo: lo que el menú fijo no alcanza a usar antes de que caduque.
2. Da a cada receta un puntaje: lo que aprovecha, por porción, de los ingredientes en riesgo, pesado por su prioridad.
3. Recorre las recetas de mayor a menor puntaje y asigna a cada una todas las porciones posibles, sin pasar su demanda ni el inventario.

Con los datos de ejemplo (12 ingredientes y 7 recetas) aprovecha **10.30 de 13.62 kg en riesgo (75.6 %)** en menos de 1 ms.

**Complejidad aproximada:** O(n log n + m log m + E), con `n` ingredientes, `m` recetas y `E` pares receta–ingrediente. Como cada receta tiene pocos ingredientes, es prácticamente lineal-logarítmica. Probar todas las combinaciones de recetas cuesta al menos O(2^m): con 30 recetas ya son más de mil millones. El desglose por paso está en el README del prototipo.

El voraz definitivo (#20 y #23) recorrerá los ingredientes del más urgente al menos urgente, preparará solo las porciones necesarias y generará de 3 a 5 propuestas. Comparar las dos versiones contra la fuerza bruta (#24) es parte del Checkpoint 2.

## 6. Evidencia del avance

| Entrega | Issue | PR |
|---|---|---|
| Estructura base con uv, ruff, pytest y CI | #6 | #37 |
| Formato de los tres CSV y reglas de validación | #7 | #9 |
| Caracterización del negocio tipo | #8 | #39 |
| CSV de ejemplo y archivos inválidos para probar la carga | #10 | #38 |
| Prototipo v0 del voraz | #40 | #42 |
| FODA y este documento | #41 | #43 |

Cada PR pasa por el CI (lint, formato y pruebas) y necesita una aprobación antes de unirse a `main`.
