# Evaluación por simulación (OP4)

Esta sección corresponde al apartado 8 del reporte técnico (#32). Todos los números salen de `resultados/`, que se regenera con un comando (ver el final). Si un número cambia, la prueba `test_los_resultados_guardados_estan_al_dia` falla hasta que se vuelvan a generar los resultados y se actualice este texto.

## 8.1 Qué se comparó y cómo

**Pregunta.** ¿Cuánto desperdicio y cuánto dinero ahorra un puesto de comida con menú fijo si cada día agrega el menú del día que propone el voraz?

| Escenario | Qué vende cada día |
|---|---|
| **A** | Solo el menú fijo |
| **B** | El menú fijo y, además, el menú del día que genera el voraz con el inventario de ese día |

**Simulador** (`src/menucero/simulacion.py`, #25). Avanza día por día con el inventario inicial y **sin reposición**:

1. Se atiende primero el menú fijo. Si no alcanza el inventario, el resto son porciones no atendidas.
2. En B, se vende después el menú del día.
3. Lo que llega a su fecha de caducidad sin usarse es **merma**.

La demanda de cada platillo es aleatoria (Poisson, con media la demanda estimada). A y B con la misma semilla atienden exactamente a los mismos clientes del menú fijo, así que la diferencia entre ambos se debe solo al menú del día.

**Configuración** (`scripts/simular.py`, #28):

- 4 escenarios de `data/escenarios` (#19), todos con inicio el miércoles 25 de noviembre de 2026:
  - normal;
  - exámenes (demanda × 0.80);
  - vacaciones (demanda × 0.25);
  - alta caducidad (regreso de un puente, con 8 ingredientes ya caducados).
- 2 horizontes: 3 días, que es lo que duran las compras del dataset, y 7 días, el horizonte que pide #25.
- 30 semillas por escenario y horizonte: 240 parejas A–B en total.
- Voraz: **el voraz principal** (`src/menucero/voraz.py`, #20), con la propuesta `base` de `generar_menu`. En 8.2 se compara con el prototipo v0 (`prototipo/voraz_v0.py`), que se usó antes de que el principal estuviera en `main`.
- Métricas (#22):
  - desperdicio evitado = 100 × (merma A − merma B) / merma A;
  - costo ahorrado = Σ costo_kg × (merma A − merma B), por ingrediente.

## 8.2 Resultados

**Tabla 1.** Merma con solo el menú fijo (A) y con el menú del día (B). Promedio ± desviación estándar de 30 semillas. Entre corchetes, el intervalo de confianza del 95 % del promedio del desperdicio evitado.

| Escenario | Días | Merma A (kg) | Merma B (kg) | Desperdicio evitado (%) | Costo ahorrado ($) |
|---|---:|---:|---:|---:|---:|
| Normal | 3 | 15.05 ± 1.08 | 11.20 ± 0.82 | 25.4 ± 4.8 [23.6, 27.2] | 308.58 ± 92.62 |
| Exámenes | 3 | 17.55 ± 1.84 | 11.41 ± 1.21 | 34.9 ± 3.9 [33.4, 36.4] | 497.17 ± 94.54 |
| Vacaciones | 3 | 54.30 ± 1.75 | 43.08 ± 1.93 | 20.7 ± 1.7 [20.0, 21.3] | 756.44 ± 70.52 |
| Alta caducidad | 3 | 65.71 ± 2.54 | 57.66 ± 2.70 | 12.3 ± 1.5 [11.7, 12.8] | 478.28 ± 70.24 |
| Normal | 7 | 29.80 ± 1.50 | 24.75 ± 1.14 | 16.9 ± 3.1 [15.7, 18.0] | 304.26 ± 97.61 |
| Exámenes | 7 | 39.91 ± 2.62 | 31.82 ± 1.47 | 20.1 ± 3.1 [19.0, 21.3] | 543.82 ± 100.01 |
| Vacaciones | 7 | 109.09 ± 2.78 | 91.90 ± 2.98 | 15.8 ± 1.2 [15.3, 16.2] | 1,149.68 ± 93.39 |
| Alta caducidad | 7 | 70.67 ± 2.74 | 61.70 ± 2.86 | 12.7 ± 1.5 [12.2, 13.3] | 546.37 ± 73.64 |

*Fuente: elaboración propia con `resultados/simulacion.csv` y `resultados/resumen.md`.*

**Lo principal.**

- **B tuvo menos merma que A en las 240 parejas.** El peor caso evitó el 8.8 % y el mejor el 41.2 %.
- Ningún intervalo de confianza se acerca a 0. La mejora no es efecto del azar de la demanda.
- En promedio, el menú del día evita entre el **12 % y el 35 %** de la merma, según el escenario y el horizonte.

![Figura 1](../resultados/merma_a_vs_b.png)

**Figura 1.** Merma promedio de A y B por escenario. La línea es ± 1 desviación estándar. *Fuente: `resultados/merma_a_vs_b.png`.*

**Cómo leer la Figura 1.**

- En los cuatro escenarios y los dos horizontes, la barra de B es más baja que la de A, y sus barras de error no se tocan.
- La diferencia en kg es mayor donde más se desperdicia: vacaciones y alta caducidad. En porcentaje, la mayor diferencia está en exámenes.
- Vacaciones es el escenario con más merma. Con la demanda en 25 %, el inventario de una semana normal no se alcanza a usar, y el menú del día rescata 11 kg en 3 días, pero no puede vender lo que nadie pide.

![Figura 2](../resultados/desperdicio_evitado.png)

**Figura 2.** Desperdicio evitado en cada una de las 30 semillas. *Fuente: `resultados/desperdicio_evitado.png`.*

**Cómo leer la Figura 2.**

- Todas las cajas están por encima de 0.
- **Exámenes** tiene el mayor beneficio: de 25.9 % a 41.2 % con 3 días. Con la demanda al 80 %, el menú fijo deja más sobrante cada día, y el menú del día tiene más qué rescatar y clientes que lo compran.
- **Normal** tiene la mayor dispersión con 3 días: de 16.7 % a 33.1 %.
- **Alta caducidad** tiene la caja más baja y más angosta: 15.7 kg ya están caducados al empezar, y esa merma no la evita ningún menú.
- Con 7 días el porcentaje baja en todos los escenarios menos alta caducidad. Sin reposición, desde el día 3 el menú fijo se queda sin ingredientes (ver 8.4), y ambos escenarios desperdician lo que ya no se puede cocinar.

**Voraz principal contra el prototipo v0.** Los resultados anteriores eran del v0. Con las mismas 240 parejas, el voraz principal evita más merma en normal y en exámenes, y da exactamente lo mismo en vacaciones y alta caducidad.

| Escenario | Días | Desperdicio evitado con v0 (%) | Con el voraz principal (%) | Porciones del menú del día (v0 → principal) |
|---|---:|---:|---:|---:|
| Normal | 3 | 16.7 | **25.4** | 986 → 1103 |
| Exámenes | 3 | 30.7 | **34.9** | 2216 → 2041 |
| Vacaciones | 3 | 20.7 | 20.7 | 2298 → 2298 |
| Alta caducidad | 3 | 12.3 | 12.3 | 1141 → 1141 |
| Normal | 7 | 13.3 | **16.9** | 986 → 1103 |
| Exámenes | 7 | 19.3 | **20.1** | 2275 → 2108 |
| Vacaciones | 7 | 15.8 | 15.8 | 2316 → 2316 |
| Alta caducidad | 7 | 12.7 | 12.7 | 1141 → 1141 |

*Fuente: elaboración propia con `resultados/simulacion.csv` de cada voraz. Las porciones son la suma de las 30 semillas.*

- En exámenes, el voraz principal vende **menos** porciones del menú del día y aun así evita más merma. Concuerda con su cambio principal: no prepara más porciones de las necesarias para salvar los kg en riesgo, así que el inventario queda para los platillos que sí rescatan algo.
- En normal vende más porciones que el v0 y también evita más merma.
- En vacaciones y alta caducidad, los dos voraces eligen las mismas porciones en las 30 semillas, así que la merma es idéntica.

## 8.3 Contraste con lo esperado

En la Actividad 03 se estimó que, en la demostración con 40 ingredientes, *«solo con el menú fijo, podría perderse hasta el 60 % de esos ingredientes»*: los que vencen en menos de 48 horas.

**Tabla 2.** Porcentaje de los kg de los ingredientes urgentes que termina como merma. Son los que vencen hoy o mañana al empezar: los 8 de la demostración en el escenario normal. Promedio ± desviación estándar de 30 semillas, con 3 días.

| Escenario | Kg urgentes | Se pierde en A (%) | Se pierde en B (%) | Diferencia (puntos) |
|---|---:|---:|---:|---:|
| Normal (la demostración) | 15.71 | 61.8 ± 3.0 | 42.0 ± 3.4 | −19.8 |
| Exámenes | 17.16 | 56.4 ± 3.9 | 34.9 ± 2.9 | −21.5 |
| Vacaciones | 21.76 | 85.1 ± 3.2 | 69.3 ± 3.3 | −15.8 |
| Alta caducidad¹ | 72.91 | 66.4 ± 3.5 | 55.4 ± 3.7 | −11.0 |

*Fuente: elaboración propia con `resultados/simulacion.csv`. Con 7 días los porcentajes son iguales, porque los urgentes caducan en los primeros 2 días.*
¹ En alta caducidad los 8 de la demostración ya caducaron. Los urgentes son otros 18 ingredientes que el cierre de 2 días dejó a 0 o 1 día de vencer.

**Lectura.**

- **La estimación de la Actividad 03 se confirma.** En la demostración (escenario normal), solo con el menú fijo se pierde el **61.8 %** de los ingredientes urgentes, prácticamente el 60 % estimado. En exámenes se pierde un poco menos y en vacaciones bastante más.
- Con el menú del día, esa pérdida baja a **42.0 %**. Se rescatan unos 3 kg de los 15.7 kg urgentes.
- El menú del día **no elimina** la pérdida. En la demostración, todavía se pierden 6.6 kg urgentes. Hay dos razones:
  - Su demanda está limitada: solo se venden las porciones adicionales que se estima que piden los clientes.
  - Varios urgentes son ingredientes que pocas recetas usan, en poca cantidad por porción.
- La diferencia es clara, como se esperaba, pero no es del orden de «casi todo se rescata». Así hay que presentarla.

## 8.4 Efecto secundario: porciones del menú fijo no atendidas

El menú fijo se atiende antes que el menú del día, así que **el mismo día** nunca pierde porciones por él. Pero el voraz solo reserva lo que el menú fijo necesita **hoy**, y el menú del día puede gastar lo que el menú fijo necesitaría **los días siguientes**.

| Escenario | No atendidas A (3 días) | No atendidas B (3 días) | Diferencia |
|---|---:|---:|---:|
| Normal | 296.4 | 311.3 | +14.9 (+5.0 %) |
| Exámenes | 183.0 | 215.6 | +32.7 (+17.9 %) |
| Vacaciones | 25.9 | 25.9 | 0 |
| Alta caducidad | 461.6 | 461.7 | +0.1 |

*Fuente: `resultados/resumen.md`.*

- Las porciones no atendidas son altas en A y en B. Es efecto de no reponer inventario (ver 8.5), no del menú del día.
- La diferencia entre B y A sí es atribuible al menú del día.
- Con el v0 era mayor en exámenes (+37.7). Con el voraz principal bajó a +32.7, lo que concuerda con que limite las porciones a las necesarias para salvar los kg en riesgo. En normal quedó prácticamente igual (+14.3 con el v0).
- **Mejora posible:** que el voraz reserve el consumo del menú fijo de todos los días que le quedan al ingrediente, no solo el de hoy.

## 8.5 Limitaciones

1. **Demanda estimada.**
   - La demanda de cada platillo sale de la caracterización (#8), no de ventas reales.
   - El ruido Poisson representa la variación diaria, pero no cambios de preferencia, clima ni promociones.
   - La demanda del menú del día es la parte más incierta: nadie la ha medido.
2. **Sin reposición.**
   - El inventario inicial es todo lo que hay. En un negocio real se compra cada 1 a 3 días.
   - Con 7 días, el menú fijo se queda sin ingredientes desde el día 3, y quedan sin atender unas 1100 porciones en el escenario normal. Esa merma aparece por igual en A y en B, y baja el porcentaje evitado.
   - Por eso el horizonte de 3 días, que coincide con el ciclo de compra del dataset, es el resultado más representativo.
3. **Supuesto de venta del menú del día.**
   - El modelo base supone que el menú del día se prepara sobre pedido. Lo que no se vende no se prepara.
   - Para medir qué tanto depende el resultado de este supuesto, se corrió una prueba más estricta: el menú del día se prepara completo al inicio del día, se vende el 100, 75 o 50 % de su demanda estimada, y **lo que sobra se tira como merma** (Tabla 3, Figura 3).
4. **Datos sintéticos.**
   - El inventario, las recetas y los costos son de un puesto *tipo*, construido a partir de la caracterización (#8), no de un negocio real.
   - El generador parametrizable (#17) todavía no está, así que no se probaron otros tamaños ni otras composiciones del inventario.
5. **Una sola propuesta por día.** La simulación vende la propuesta `base` del voraz. Las otras variantes de #23 (económica, eficiencia, etc.) no se simularon, y la distancia al óptimo se mide aparte, con la fuerza bruta (#24).

**Tabla 3.** Sensibilidad al supuesto de venta: 3 días, menú del día preparado completo y sobrantes tirados. Promedio ± desviación estándar de 30 semillas; entre corchetes, el mínimo y el máximo.

| Escenario | Se vende | Desperdicio evitado (%) | Porciones sobrantes de B |
|---|---:|---:|---:|
| Normal | 100 % | 21.8 ± 7.0 [4.8, 32.6] | 3.4 |
| Normal | 75 % | 14.9 ± 9.7 [−6.6, 30.3] | 8.0 |
| Normal | 50 % | 5.8 ± 8.5 [−10.0, 19.8] | 14.1 |
| Exámenes | 100 % | 21.6 ± 9.2 [−10.2, 35.4] | 9.8 |
| Exámenes | 75 % | 6.8 ± 7.7 [−19.4, 18.4] | 19.4 |
| Exámenes | 50 % | −16.4 ± 12.1 [−51.4, −0.4] | 34.6 |
| Vacaciones | 100 % | 14.1 ± 2.9 [9.4, 19.0] | 28.9 |
| Vacaciones | 75 % | 7.5 ± 3.0 [2.1, 14.0] | 42.5 |
| Vacaciones | 50 % | −0.5 ± 3.4 [−6.2, 4.6] | 58.4 |
| Alta caducidad | 100 % | 11.6 ± 1.8 [9.1, 14.6] | 7.7 |
| Alta caducidad | 75 % | 9.8 ± 1.7 [7.2, 12.8] | 12.7 |
| Alta caducidad | 50 % | 5.8 ± 1.6 [1.4, 9.2] | 22.3 |

*Fuente: elaboración propia con `resultados/sensibilidad_venta.csv`.*

![Figura 3](../resultados/sensibilidad_venta.png)

**Figura 3.** Desperdicio evitado según la parte vendida del menú del día, cuando se prepara completo y lo que sobra se tira. Bajo 0, B tira más que A. *Fuente: `resultados/sensibilidad_venta.png`.*

**Lectura.** **Este es el supuesto que más pesa.**

| Se vende | B tiene menos merma que A en |
|---:|---:|
| 100 % | 119 de 120 corridas |
| 75 % | 115 de 120 corridas |
| 50 % | 67 de 120 corridas: poco más de la mitad |

- **Exámenes** es el caso más sensible: con 50 % de venta, el menú del día tira más de lo que rescata en las 30 corridas. Con 75 % todavía ahorra en promedio (6.8 %); con el v0 ya perdía (−4.4 %).
- **Alta caducidad** es el más robusto: los ingredientes que rescata se iban a perder de todos modos.

La conclusión práctica para el negocio es **preparar el menú del día por tandas, o solo hasta la demanda segura**, en lugar de prepararlo todo de una vez. Del lado del algoritmo, el voraz principal ya no propone más porciones de las necesarias para salvar los kg en riesgo, una de las mejoras planteadas en `prototipo/voraz_v0.py`. Por eso aguanta mejor este supuesto que el v0: con 75 % de venta, B gana en 115 de 120 corridas, contra 96 con el v0.

## 8.6 Conclusión respecto del objetivo general

El objetivo general era generar un menú del día que priorice los ingredientes próximos a caducar *«con el fin de reducir el desperdicio de ingredientes y su costo en comparación con trabajar solo con el menú fijo, lo cual se comprobará mediante simulaciones con datos de prueba»*.

Con los datos de prueba y el modelo de simulación descritos, **el objetivo se cumple**:

- El menú del día redujo la merma en las 240 parejas de corridas: en promedio, del **12 % al 35 %** según el escenario.
- Ahorró de **$304 a $1,150** de ingredientes en el horizonte simulado.
- En la demostración, bajó la pérdida de los ingredientes urgentes del **61.8 % al 42.0 %**.

**Esta conclusión tiene dos condiciones:**

1. **El menú del día tiene que venderse.** Si se prepara completo y se vende solo la mitad de lo estimado, el beneficio desaparece en exámenes y vacaciones.
2. **Las cifras son de datos sintéticos.** Son evidencia de que el enfoque funciona en un puesto tipo, no una medición en un negocio real.

Con el voraz principal (#20) los resultados mejoraron respecto del v0 (8.2), y el sobreuso de 8.4 bajó en exámenes. Falta medir qué tan cerca queda del óptimo (#24) y su eficiencia con inventarios grandes (#27).

## Cómo reproducir

```bash
uv run python scripts/simular.py
```

Tarda unos 3 segundos y escribe en `resultados/`:

| Archivo | Contenido |
|---|---|
| `simulacion.csv` | Una fila por escenario, horizonte y semilla |
| `resumen.csv` / `resumen.md` | Tablas 1 y 2 |
| `sensibilidad_venta.csv` | Tabla 3 |
| `merma_a_vs_b.png` | Figura 1 |
| `desperdicio_evitado.png` | Figura 2 |
| `sensibilidad_venta.png` | Figura 3 |

Los intervalos de confianza de la Tabla 1 se calculan con la t de Student: promedio ± 2.045 × desviación / √30.
