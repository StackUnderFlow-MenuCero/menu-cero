# Simulación A vs B (30 semillas por escenario, voraz: v0 (prototipo))

Fecha de inicio 2026-11-25, demanda Poisson, sin reposición. Promedio ± desviación estándar; entre corchetes, mínimo y máximo.

| Escenario | Días | Merma A (kg) | Merma B (kg) | Desperdicio evitado (%) | Costo ahorrado ($) | No atendidas A | No atendidas B |
|---|---:|---:|---:|---:|---:|---:|---:|
| Normal | 3 | 15.05 ± 1.08 | 12.53 ± 0.82 | 16.7 ± 3.0 [8.9, 21.1] | 154.92 ± 56.64 | 296.4 | 310.7 |
| Exámenes | 3 | 17.55 ± 1.84 | 12.12 ± 1.18 | 30.7 ± 4.8 [19.5, 40.3] | 423.77 ± 104.78 | 183.0 | 220.7 |
| Vacaciones | 3 | 54.30 ± 1.75 | 43.08 ± 1.93 | 20.7 ± 1.7 [17.3, 24.0] | 756.44 ± 70.52 | 25.9 | 25.9 |
| Alta caducidad | 3 | 65.71 ± 2.54 | 57.66 ± 2.70 | 12.3 ± 1.5 [9.7, 14.7] | 478.28 ± 70.24 | 461.6 | 461.7 |
| Normal | 7 | 29.80 ± 1.50 | 25.82 ± 1.18 | 13.3 ± 2.0 [8.8, 16.8] | 158.92 ± 62.22 | 1086.0 | 1100.3 |
| Exámenes | 7 | 39.91 ± 2.62 | 32.14 ± 1.45 | 19.3 ± 3.4 [13.0, 28.6] | 452.90 ± 100.86 | 814.1 | 852.4 |
| Vacaciones | 7 | 109.09 ± 2.78 | 91.90 ± 2.98 | 15.8 ± 1.2 [13.3, 18.1] | 1,149.68 ± 93.39 | 245.8 | 245.8 |
| Alta caducidad | 7 | 70.67 ± 2.74 | 61.70 ± 2.86 | 12.7 ± 1.5 [10.4, 15.2] | 546.37 ± 73.64 | 1253.6 | 1253.7 |

## Pérdida de los ingredientes urgentes y del inventario

Urgentes: los que vencen hoy o mañana al empezar. Porcentaje de sus kg iniciales que terminan como merma.

| Escenario | Días | Urgentes A (%) | Urgentes B (%) | Inventario A (%) | Inventario B (%) |
|---|---:|---:|---:|---:|---:|
| Normal | 3 | 61.8 ± 3.0 | 42.8 ± 3.1 | 13.4 | 11.2 |
| Exámenes | 3 | 56.4 ± 3.9 | 35.8 ± 2.9 | 13.8 | 9.5 |
| Vacaciones | 3 | 85.1 ± 3.2 | 69.3 ± 3.3 | 32.1 | 25.4 |
| Alta caducidad | 3 | 66.4 ± 3.5 | 55.4 ± 3.7 | 58.6 | 51.4 |
| Normal | 7 | 61.8 ± 3.0 | 42.8 ± 3.1 | 26.6 | 23.0 |
| Exámenes | 7 | 56.4 ± 3.9 | 35.8 ± 2.9 | 31.3 | 25.2 |
| Vacaciones | 7 | 85.1 ± 3.2 | 69.3 ± 3.3 | 64.5 | 54.3 |
| Alta caducidad | 7 | 66.4 ± 3.5 | 55.4 ± 3.7 | 63.0 | 55.0 |

## Sensibilidad al supuesto de venta (3 días)

El menú del día se prepara completo al inicio del día; se vende la fracción indicada de su demanda estimada y lo que sobra se tira como merma.

| Escenario | Venta | Merma A (kg) | Merma B (kg) | Desperdicio evitado (%) | Porciones sobrantes B |
|---|---:|---:|---:|---:|---:|
| Normal | 100% | 15.05 | 13.04 | 13.2 ± 4.7 [3.0, 20.3] | 2.9 |
| Normal | 75% | 15.05 | 13.92 | 7.4 ± 8.3 [-16.7, 19.5] | 7.2 |
| Normal | 50% | 15.05 | 15.20 | -1.1 ± 7.9 [-18.2, 11.2] | 13.1 |
| Exámenes | 100% | 17.55 | 15.00 | 13.8 ± 10.9 [-22.2, 30.5] | 12.0 |
| Exámenes | 75% | 17.55 | 18.22 | -4.4 ± 9.0 [-27.5, 8.4] | 23.6 |
| Exámenes | 50% | 17.55 | 22.48 | -29.0 ± 13.9 [-71.0, -10.3] | 40.1 |
| Vacaciones | 100% | 54.30 | 46.67 | 14.1 ± 2.9 [9.4, 19.0] | 28.9 |
| Vacaciones | 75% | 54.30 | 50.26 | 7.5 ± 3.0 [2.1, 14.0] | 42.5 |
| Vacaciones | 50% | 54.30 | 54.54 | -0.5 ± 3.4 [-6.2, 4.6] | 58.4 |
| Alta caducidad | 100% | 65.71 | 58.12 | 11.6 ± 1.8 [9.1, 14.6] | 7.7 |
| Alta caducidad | 75% | 65.71 | 59.27 | 9.8 ± 1.7 [7.2, 12.8] | 12.7 |
| Alta caducidad | 50% | 65.71 | 61.93 | 5.8 ± 1.6 [1.4, 9.2] | 22.3 |
