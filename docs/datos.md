# Datos de entrada de Menú Cero

Este documento es el contrato de datos del equipo. Dice qué trae cada CSV, en qué unidades y qué valores son inválidos. La carga (`carga.py`, #13) valida exactamente estas reglas, y el algoritmo (#11, #20) y la app trabajan con lo que resulta.

Las primeras secciones definen el formato (#7). La última, [Caracterización del negocio tipo](#caracterización-del-negocio-tipo) (#8), describe el negocio que representan los datos de prueba: sus platillos, la demanda, la vida útil de los ingredientes y sus costos.

## Resumen

| Archivo | Una fila es | Clave |
|---|---|---|
| `inventario.csv` | un ingrediente en existencia | `ingrediente_id` |
| `recetas.csv` | un ingrediente de una receta (formato largo) | `receta_id` + `ingrediente_id` |
| `demanda.csv` | la demanda diaria de una receta | `receta_id` |

Relaciones entre archivos:

```
recetas.ingrediente_id ──► inventario.ingrediente_id
demanda.receta_id ───────► recetas.receta_id
```

## Convenciones para los tres archivos

- **Codificación:** UTF-8. También se acepta UTF-8 con BOM, que es como lo guarda Excel.
- **Separadores:** coma entre columnas y punto decimal (`2.5`, no `2,5`), sin separador de miles.
- **Encabezado:** la primera fila lleva los nombres exactos de las columnas, en minúsculas. El orden de las columnas no importa.
- **Limpieza:** las columnas de más se ignoran con una advertencia; las filas completamente vacías se ignoran; los espacios al inicio y al final de cada celda se recortan.
- **Identificadores:** letras sin acentos, dígitos, guion y guion bajo (`ING01`, `REC_07`). Distinguen mayúsculas.
- **Fechas:** `AAAA-MM-DD` (`2026-11-17`).
- **Cantidades:** todo en kilogramos. Los líquidos se capturan como 1 L ≈ 1 kg y las piezas se convierten a kg (tabla abajo).
- **Dinero:** pesos mexicanos por kg, sin signo `$`.
- **Fecha de referencia («hoy»):** no va en los CSV; se elige en la app o en la línea de comandos. Así el mismo juego de datos se puede evaluar en distintas fechas y los resultados se pueden repetir.

Conversiones aproximadas de piezas a kg (confirmadas en la caracterización, #8):

| Pieza | kg aprox. |
|---|---:|
| Huevo | 0.055 |
| Tortilla de maíz | 0.030 |
| Bolillo | 0.070 |
| Jitomate saladet | 0.120 |
| Aguacate mediano | 0.200 |
| Chile poblano | 0.130 |
| Lechuga romana | 0.500 |
| Limón | 0.040 |

## `inventario.csv`

| Columna | Tipo | Unidad | Obligatoria | Regla |
|---|---|---|---|---|
| `ingrediente_id` | texto | — | sí | único en el archivo |
| `nombre` | texto | — | sí | no vacío |
| `cantidad_kg` | decimal | kg | sí | ≥ 0 |
| `fecha_caducidad` | fecha | `AAAA-MM-DD` | sí | fecha válida |
| `costo_kg` | decimal | MXN/kg | sí | ≥ 0 |
| `kcal_kg` | decimal | kcal/kg | no | ≥ 0; solo para la extensión nutricional (#33) |
| `proteina_g_kg` | decimal | g/kg | no | ≥ 0; solo para la extensión nutricional (#33) |

```csv
ingrediente_id,nombre,cantidad_kg,fecha_caducidad,costo_kg
ING01,Crema ácida,2.0,2026-11-17,70.00
ING02,Champiñones,1.5,2026-11-18,95.00
ING03,Pechuga de pollo,8.0,2026-11-20,120.00
```

- **`fecha_caducidad` es el último día en que el ingrediente se puede usar.** Si vence hoy, todavía se usa hoy: días para caducar = 0 y prioridad = 1. Si la fecha ya pasó, el ingrediente está caducado.
- **Una fila por ingrediente.** Si hay varios lotes con fechas distintas, se registra la cantidad total con la fecha más próxima. Es un criterio conservador: hace que se priorice usarlo antes. Manejar lotes por separado queda fuera del prototipo.

## `recetas.csv`

Formato largo: una fila por cada ingrediente de cada receta.

| Columna | Tipo | Unidad | Obligatoria | Regla |
|---|---|---|---|---|
| `receta_id` | texto | — | sí | |
| `platillo` | texto | — | sí | igual en todas las filas de la receta |
| `tipo` | `fijo` o `secundaria` | — | sí | igual en todas las filas de la receta |
| `ingrediente_id` | texto | — | sí | debería existir en `inventario.csv` |
| `kg_por_porcion` | decimal | kg | sí | > 0 |

El par (`receta_id`, `ingrediente_id`) no se repite.

```csv
receta_id,platillo,tipo,ingrediente_id,kg_por_porcion
REC01,Pollo a la crema con champiñones,fijo,ING03,0.150
REC01,Pollo a la crema con champiñones,fijo,ING01,0.040
REC01,Pollo a la crema con champiñones,fijo,ING02,0.030
```

- **`fijo`:** platillo del menú fijo (la carta). Se vende todos los días según `demanda_fija` y además puede promoverse como menú del día.
- **`secundaria`:** platillo que el negocio ya sabe preparar pero que no está en la carta (por ejemplo, crema de champiñones). Solo se ofrece como menú del día, para aprovechar lo que sobra. Así se cumple la restricción de usar solo recetas que el negocio ya prepara.
- **Qué ingredientes listar:** solo los que se quieren controlar. La sal, el aceite y otros básicos de despensa pueden omitirse; si se incluyen, tienen que estar en el inventario.

## `demanda.csv`

| Columna | Tipo | Unidad | Obligatoria | Regla |
|---|---|---|---|---|
| `receta_id` | texto | — | sí | único; debe existir en `recetas.csv` |
| `demanda_fija` | entero | porciones/día | sí | ≥ 0 |
| `demanda_menu_dia` | entero | porciones/día | sí | ≥ 0 |

```csv
receta_id,demanda_fija,demanda_menu_dia
REC01,3,12
REC02,25,5
REC07,0,10
```

- **`demanda_fija`:** las porciones que se venden al día con el menú fijo. Las recetas secundarias llevan 0.
- **`demanda_menu_dia`:** las porciones **adicionales** que se estima vender si el platillo sale como menú del día. Es el tope de la restricción de demanda: el algoritmo nunca propone más porciones que esta cantidad.
  - Un platillo que ya se vende mucho tiene un valor bajo, porque promoverlo agrega pocas ventas.
  - Con 0, el platillo nunca se propone como menú del día.

Los ejemplos de las tres tablas son fragmentos ilustrativos; el juego completo de ejemplo está en `data/ejemplo/` (#10).

## Validación

- **Error:** detiene la carga. La app muestra todos los errores juntos, no solo el primero, para corregirlos de una vez.
- **Advertencia:** se reporta y la carga continúa, aplicando la corrección que indica la tabla.

### Errores

| Situación | Dónde |
|---|---|
| Falta un archivo o no tiene filas de datos | cualquiera |
| Falta una columna obligatoria | cualquiera |
| Celda obligatoria vacía | cualquiera |
| Identificador con caracteres no permitidos | cualquiera |
| Número no válido (texto o coma decimal) | `cantidad_kg`, `costo_kg`, `kg_por_porcion`, demandas |
| Fecha no válida o con otro formato | `fecha_caducidad` |
| `cantidad_kg` o `costo_kg` negativos | inventario |
| `kg_por_porcion` ≤ 0 | recetas |
| Demanda negativa o con decimales | demanda |
| `tipo` distinto de `fijo` o `secundaria` | recetas |
| `ingrediente_id` repetido | inventario |
| Par receta-ingrediente repetido | recetas |
| Una receta con `platillo` o `tipo` distintos entre sus filas | recetas |
| `receta_id` repetido | demanda |

### Advertencias

| Situación | Qué hace el programa |
|---|---|
| Columna desconocida | la ignora |
| Ingrediente caducado respecto de la fecha de referencia | lo excluye del menú y lo cuenta como merma ya perdida |
| Ingrediente con cantidad 0 | lo conserva; ninguna receta podrá usarlo |
| Ingrediente con costo 0 | lo usa así (probable error de captura) |
| Ingrediente que ninguna receta usa | lo conserva; no se podrá aprovechar con el menú del día |
| Receta que usa un ingrediente que no está en el inventario | toma cantidad 0; la receta no se podrá preparar |
| `kg_por_porcion` mayor que 1 kg | lo usa así; conviene revisar si se capturó en gramos |
| Receta sin fila en `demanda.csv` | pone ambas demandas en 0 |
| Fila de demanda de una receta que no existe | la ignora |
| Receta secundaria con `demanda_fija` > 0 | toma 0, porque no está en la carta |

### Formato de los mensajes

```
archivo, fila N, columna C: problema («valor encontrado»)
```

Las filas se cuentan como en una hoja de cálculo: el encabezado es la fila 1 y el primer dato, la fila 2. Por ejemplo:

```
inventario.csv, fila 4, columna fecha_caducidad: no es una fecha AAAA-MM-DD («17/11/2026»)
recetas.csv, fila 9, columna kg_por_porcion: debe ser mayor que 0 («0»)
```

## Cómo se usan estos datos

Con la fecha de referencia, cada ingrediente produce los valores que usa el algoritmo. El detalle está en `docs/diseno.md` (#18).

| Valor | Cálculo |
|---|---|
| Días para caducar `d` | `fecha_caducidad − hoy` (0 si vence hoy) |
| Prioridad | `1 / (d + 1)`: hoy 1, mañana 0.5, en 7 días 0.125 |
| Reserva | Σ `demanda_fija × kg_por_porcion` de las recetas fijas que lo usan: los kg que el menú fijo consume al día |
| Kg en riesgo | `max(0, cantidad_kg − reserva × (d + 1))`: lo que el menú fijo no alcanzará a usar antes de que venza |

## Caracterización del negocio tipo

Los datos de prueba representan un negocio **inventado pero típico**. Se armó con lo que se ve alrededor de CUCEI y con precios publicados en noviembre de 2026. No es un negocio real ni sale de una encuesta: los valores son estimaciones del equipo, y cada tabla dice de dónde sale cada dato. Si hay oportunidad, conviene contrastarlos con una plática con el encargado de algún puesto.

### El negocio

| Rasgo | Supuesto |
|---|---|
| Tipo | Cocina económica de un solo local frente a CUCEI. El centro universitario no tiene comedor propio. |
| Clientes | Estudiantes, profesores y trabajadores. |
| Horario | Lunes a viernes, de 8:00 a 17:00, con desayunos y comidas. |
| Ventas | Unas 125 porciones al día en semana normal de clases (suma del menú fijo). |
| Refrigeración | Un refrigerador comercial de dos puertas. El pollo, la carne y el pescado se guardan frescos, sin congelar. |
| Compras | Pollo y carne 2 o 3 veces por semana con un proveedor. Verdura 2 veces por semana en el mercado. Crema y queso una vez por semana con un distribuidor. Tortilla diario. |
| Cómo decide hoy | Tiene la carta fija y a veces anuncia un «platillo del día» que el encargado elige a ojo. |

**Por qué se desperdicia.** Para ofrecer un platillo poco pedido, el negocio tiene que comprar sus ingredientes en la presentación mínima del proveedor.

- Ejemplo: los champiñones se compran por kilo, y el pollo a la crema usa 0.030 kg por porción con 3 porciones al día.
- Así, en 5 días de vida útil se ocupan 0.45 kg y el resto (más de la mitad) se tira.
- Los platillos populares no tienen ese problema: los tacos de bistec venden 25 porciones al día y la carne se acaba antes de vencer.

### Menú fijo

Diez platillos. «Porciones al día» es la demanda en semana normal (`demanda_fija`). «Menú del día» es cuántas porciones **adicionales** se venderían si se promueve (`demanda_menu_dia`), según esta regla:

- **Los populares** agregan poco (0 a 5 porciones), porque quien los quiere ya los pide.
- **Los poco pedidos** agregan más (6 a 12 porciones), porque la promoción los da a conocer.

| Platillo | Porciones al día | Poca salida | Menú del día | Perecederos por porción (kg) |
|---|---:|:---:|---:|---|
| Chilaquiles rojos con pollo | 30 | | 3 | tortilla 0.090 · pechuga 0.080 · jitomate 0.060 · crema 0.020 · queso fresco 0.020 |
| Tacos de bistec (3 piezas) | 25 | | 5 | bistec 0.120 · tortilla 0.090 |
| Milanesa de pollo con arroz y frijoles | 20 | | 4 | pechuga 0.150 · huevo 0.030 · lechuga 0.030 · jitomate 0.030 |
| Huevos al gusto | 15 | | 3 | huevo 0.110 · tortilla 0.060 · jitomate 0.040 · cebolla 0.010 · chile serrano 0.005 |
| Picadillo de res con papa | 12 | | 6 | carne molida 0.120 · papa 0.080 · calabacita 0.050 · jitomate 0.040 · cebolla 0.015 |
| Bistec a la mexicana | 10 | | 6 | bistec 0.150 · tortilla 0.090 · jitomate 0.080 · cebolla 0.030 · chile serrano 0.010 |
| Enchiladas suizas | 6 | | 10 | pechuga 0.100 · tortilla 0.080 · crema 0.050 |
| Pollo a la crema con champiñones | 3 | ✔ | 12 | pechuga 0.150 · crema 0.040 · champiñones 0.030 |
| Chiles rellenos de queso | 2 | ✔ | 8 | chile poblano 0.150 · jitomate 0.080 · queso fresco 0.070 · cebolla 0.020 |
| Filete de pescado a la plancha | 2 | ✔ | 6 | filete de tilapia 0.180 · lechuga 0.040 · jitomate 0.030 · limón 0.020 |

- **Poca salida** (3 porciones al día o menos): el pollo a la crema, los chiles rellenos y el pescado. Sus ingredientes son los que más se desperdician.
- **Lo que no se lista:** arroz, frijol, aceite, sal, pan molido y chiles secos. No son perecederos, así que no se controlan (ver «Qué ingredientes listar» en `recetas.csv`).
- **Tamaños de porción:** son los de una comida corrida: 120 a 180 g de proteína y 2 o 3 tortillas de 30 g.

### Recetas secundarias

Platillos que el negocio ya sabe preparar, pero que no están en la carta. Solo salen como menú del día y llevan `demanda_fija = 0`.

| Platillo | Menú del día | Perecederos por porción (kg) | Qué aprovecha |
|---|---:|---|---|
| Crema de champiñones | 10 | champiñones 0.080 · crema 0.050 | la sopa del día; usa lo que sobra del pollo a la crema |
| Calabacitas con queso | 8 | calabacita 0.150 · jitomate 0.050 · queso fresco 0.040 · cebolla 0.020 | la guarnición de siempre, servida como plato |
| Sopa de tortilla | 10 | jitomate 0.080 · tortilla 0.060 · aguacate 0.030 · crema 0.020 · queso fresco 0.020 | la tortilla del día anterior y la crema |
| Tostadas de tinga de pollo | 8 | pechuga 0.080 · jitomate 0.060 · tortilla 0.060 · cebolla 0.040 · lechuga 0.030 · crema 0.020 | la pechuga y la tortilla que sobran |

### Ingredientes perecederos

«Vida útil» son los días que el ingrediente se puede usar desde que se compra, guardado en refrigeración. «Costo» es lo que se supone que paga el negocio por kg.

- **De dónde salen los costos:** el negocio compra a proveedor o en el mercado, así que el costo supuesto queda por debajo del precio de supermercado.
- **Precios de referencia:** son ofertas de supermercado publicadas en noviembre de 2026. Sirven como tope; donde no hubo dato publicado se indica «estimación».

| Ingrediente | Categoría | Vida útil (días) | Base de la vida útil | Precio de referencia ($/kg) | Costo supuesto ($/kg) | Compra mínima |
|---|---|---:|---|---|---:|---|
| Pechuga de pollo sin hueso | Pollo | 2–4 | FSIS: 1–2 días el pollo crudo en casa; se supone la fecha del proveedor | 120 Chedraui · 172 Walmart [2, 3] | 120 | 3 kg |
| Bistec de res | Res | 3–5 | FSIS: 3–5 días los bistecs y cortes [5] | 257 Chedraui [2]; 189–200 en Guadalajara (jun 2025) [4] | 180 | 3 kg |
| Carne molida de res | Res | 1–2 | FSIS: 1–2 días la carne molida [5] | 136 Chedraui · 135 Walmart [2, 3] | 130 | 2 kg |
| Filete de tilapia | Pescado | 1–3 | FSIS: 1–3 días el pescado fresco [5] | 103 Chedraui [2] | 100 | 2 kg |
| Crema ácida | Lácteo | 5–10 | estimación: abierta dura menos que la fecha del envase | estimación | 70 | 1 kg |
| Queso fresco | Lácteo | 5–7 | estimación: queso de alta humedad | estimación | 120 | 1 kg |
| Huevo | Huevo | 21–35 | FSIS: 3–5 semanas el huevo crudo con cascarón [5] | estimación | 45 | 1.8 kg (30 piezas) |
| Champiñones | Hongo | 4–7 | estimación | 114 Walmart, a granel [3] | 95 | 1 kg |
| Chile poblano | Verdura | 5–7 | estimación | estimación | 45 | 2 kg |
| Jitomate saladet | Verdura | 4–7 | estimación, ya maduro | 27 Walmart [3] | 25 | 5 kg |
| Calabacita | Verdura | 4–7 | estimación | estimación | 30 | 2 kg |
| Lechuga romana | Verdura | 5–7 | estimación | 24.50 la pieza Chedraui (≈ 49/kg) [2] | 45 | 2 piezas |
| Aguacate Hass | Fruta | 2–4 | estimación, ya maduro | 41.50 Chedraui · 42 Walmart [2, 3] | 40 | 2 kg |
| Chile serrano | Verdura | 7–10 | estimación | 49.90 Chedraui [2] | 40 | 0.5 kg |
| Limón | Fruta | 10–14 | estimación | 32.90 Chedraui [2] | 30 | 1 kg |
| Cebolla blanca | Verdura | 10–20 | estimación | 49.90 Chedraui [2] | 30 | 3 kg |
| Papa blanca | Verdura | 14–21 | estimación | 46.90 Chedraui · 47 Walmart [2, 3] | 35 | 4 kg |
| Tortilla de maíz | Tortilla | 1–3 | estimación: tortilla de tortillería, sin conservadores | estimación | 25 | diaria |

Lo que más se arriesga es lo que dura poco **y** se usa en platillos poco pedidos: crema, champiñones, chile poblano, queso fresco y pescado.

### Factores de demanda por calendario escolar

Los clientes son sobre todo de CUCEI, así que la demanda sigue el calendario escolar de la Universidad de Guadalajara [6]. El factor multiplica `demanda_fija` y `demanda_menu_dia` de todos los platillos.

| Periodo | Factor | Qué pasa |
|---|---:|---|
| Semana normal de clases | 1.00 | Es la referencia: la tabla del menú fijo. |
| Exámenes y fin de semestre | 0.80 | La asistencia es irregular: muchos alumnos solo van a presentar y se van. |
| Vacaciones | 0.25 | Solo quedan trabajadores, personal administrativo y cursos intersemestrales. |

Los factores son estimaciones del equipo. Lo importante para el proyecto es la consecuencia:

- El negocio compra por costumbre, así que en exámenes y vacaciones compra casi lo mismo.
- Como vende menos, crecen los kg en riesgo.
- Las corridas de la simulación (#25, #28) usan estos tres factores como escenarios.

### Rangos para el generador de datos sintéticos

Ajuste de la tabla de referencia del generador (#17) con lo anterior. La compra mínima es la que hace que los platillos poco pedidos dejen sobrantes.

| Categoría | Vida útil (días) | Costo ($/kg) | Compra mínima (kg) |
|---|---|---|---:|
| Carne de res | 2–5 | 130–200 | 3.0 |
| Pollo | 2–4 | 100–130 | 3.0 |
| Cerdo | 3–5 | 95–150 | 2.0 |
| Pescado | 1–3 | 90–120 | 2.0 |
| Lácteos | 5–10 | 60–130 | 1.0 |
| Verduras | 4–14 | 20–50 | 2.0 |
| Hongos | 4–7 | 80–110 | 1.0 |
| Tortilla y pan | 1–3 | 22–40 | 3.0 |

El cerdo no aparece en el menú de arriba. Su rango sale de los precios de referencia (pulpa $109, chuleta $97, costilla $149 [2]) y de la vida útil de los cortes del FSIS [5].

### Relación con los datos de ejemplo

`data/ejemplo/` (#10) es un recorte de este negocio, con 12 ingredientes y 7 recetas, pensado para hoy = 2026-11-17:

- **Del menú fijo:** pollo a la crema, tacos de bistec, enchiladas suizas, chiles rellenos y picadillo.
- **Secundarias:** crema de champiñones y calabacitas con queso.

Los kg por porción, la demanda y los costos son los de estas tablas. El juego completo, que alimenta la demostración y la simulación, es el #19.

### Fuentes

1. Programa de las Naciones Unidas para el Medio Ambiente (PNUMA). (2024). *Food Waste Index Report 2024*. Nairobi: PNUMA. Es el contexto del problema: el sector de servicios de comida generó cerca del 28 % del desperdicio de alimentos en 2022.
2. Ruptura360. (9 de noviembre de 2026). *Martimiércoles Chedraui: lista de ofertas 10 y 11 de noviembre 2026*. https://ruptura360.mx/periodismo-de-servicio/martimiercoles-chedraui-ofertas-frutas-verduras-carnes-2/
3. Ruptura360. (2 de noviembre de 2026). *Lista de precios del Martes de Frescura Walmart para el 3 de noviembre de 2026*. https://ruptura360.mx/periodismo-de-servicio/ofertas-martes-de-frescura-walmart-perecederos/
4. Azteca Jalisco. (19 de junio de 2025). *Precio del kilo de carne de res hoy 19 de junio 2025: ¿cuánto cuesta en Guadalajara y otras zonas de Jalisco?* https://www.aztecajalisco.com/local/cual-es-el-precio-del-kilo-carne-res-hoy-19-junio-2025-esto-vale-el-kilo-en-guadalajara/
5. FoodSafety.gov, con datos del Food Safety and Inspection Service del USDA (FSIS). *Cold Food Storage Chart*. Tiempos en refrigeración a 4 °C (40 °F) o menos. https://www.foodsafety.gov/food-safety-charts/cold-food-storage-charts
6. Universidad de Guadalajara. *Calendario escolar* vigente. Da las fechas de clases, exámenes y vacaciones.

Para actualizar los precios con datos de mayoreo de Guadalajara está el Sistema Nacional de Información e Integración de Mercados (SNIIM) de la Secretaría de Economía.
