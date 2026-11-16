# Datos de entrada de Menú Cero

Este documento es el contrato de datos del equipo. Dice qué trae cada CSV, en qué unidades y qué valores son inválidos. La carga (`carga.py`, #12) valida exactamente estas reglas, y el algoritmo (#10, #19) y la app trabajan con lo que resulta.

Aquí se define el formato (#7). La caracterización del negocio tipo (platillos, vida útil y costos realistas) se agrega en #8.

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

Conversiones aproximadas de piezas a kg (valores de referencia; #8 los confirma):

| Pieza | kg aprox. |
|---|---:|
| Huevo | 0.055 |
| Tortilla de maíz | 0.030 |
| Bolillo | 0.070 |
| Jitomate saladet | 0.120 |
| Aguacate mediano | 0.200 |

## `inventario.csv`

| Columna | Tipo | Unidad | Obligatoria | Regla |
|---|---|---|---|---|
| `ingrediente_id` | texto | — | sí | único en el archivo |
| `nombre` | texto | — | sí | no vacío |
| `cantidad_kg` | decimal | kg | sí | ≥ 0 |
| `fecha_caducidad` | fecha | `AAAA-MM-DD` | sí | fecha válida |
| `costo_kg` | decimal | MXN/kg | sí | ≥ 0 |
| `kcal_kg` | decimal | kcal/kg | no | ≥ 0; solo para la extensión nutricional (#32) |
| `proteina_g_kg` | decimal | g/kg | no | ≥ 0; solo para la extensión nutricional (#32) |

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

Los ejemplos de las tres tablas son fragmentos ilustrativos; el juego completo de ejemplo está en `data/ejemplo/` (#9).

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

Con la fecha de referencia, cada ingrediente produce los valores que usa el algoritmo. El detalle está en `docs/diseno.md` (#17).

| Valor | Cálculo |
|---|---|
| Días para caducar `d` | `fecha_caducidad − hoy` (0 si vence hoy) |
| Prioridad | `1 / (d + 1)`: hoy 1, mañana 0.5, en 7 días 0.125 |
| Reserva | Σ `demanda_fija × kg_por_porcion` de las recetas fijas que lo usan: los kg que el menú fijo consume al día |
| Kg en riesgo | `max(0, cantidad_kg − reserva × (d + 1))`: lo que el menú fijo no alcanzará a usar antes de que venza |
