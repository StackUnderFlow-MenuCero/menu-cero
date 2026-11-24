# Escenarios de simulación

Cuatro variantes del dataset de demostración (`data/demo/`) para la simulación A vs B (#25, #28). Se generan con `scripts/generar_demo.py` y usan la misma fecha de referencia: **hoy = 2026-11-25**.

| Carpeta | Qué cambia | Kg en riesgo | Aprovechado por el v0 |
|---|---|---:|---:|
| `normal/` | Semana normal de clases (factor 1.00). Es igual a `data/demo/`. | 5.41 | 3.17 kg (58.6 %) |
| `examenes/` | Exámenes y fin de semestre: la demanda × 0.80 | 11.62 | 7.81 kg (67.2 %) |
| `vacaciones/` | Vacaciones: la demanda × 0.25 | 99.25 | 11.48 kg (11.6 %) |
| `alta_caducidad/` | Regreso de un puente: el local cerró 2 días y los lotes envejecieron sin venderse. Los 8 ingredientes más urgentes ya caducaron. | 21.25 | 9.01 kg (42.4 %) |

**Reglas comunes a todos los escenarios:**
- El factor multiplica `demanda_fija` y `demanda_menu_dia`, redondeando al entero más cercano.
- El negocio **compra por costumbre**: la compra es la de una semana normal. Lo que cambia es cuánto se gastó desde la compra.
- Por eso, en vacaciones casi todo queda en riesgo. Es la consecuencia que anticipa la caracterización.

**Nota sobre vacaciones:** el issue #19 decía «baja demanda (vacaciones, ×0.6)». Aquí se usa 0.25, el factor que quedó en la caracterización (`docs/datos.md`, «Factores de demanda por calendario escolar»). El 0.80 de exámenes cubre una baja moderada.
