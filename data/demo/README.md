# Dataset de demostración

Juego completo del negocio tipo de `docs/datos.md` (#8). Es el que usarán la demostración A vs B (#30) y la simulación (#25, #28). Avance de #19.

| Archivo | Contenido |
|---|---|
| `inventario.csv` | 40 ingredientes perecederos |
| `recetas.csv` | 26 recetas: 20 del menú fijo y 6 secundarias |
| `demanda.csv` | la demanda de las 26 recetas en semana normal |

## Fecha de referencia

**Úsalo con hoy = miércoles 25 de noviembre de 2026**, el día de la demostración (#30). Para otra fecha, se regenera con el mismo comando:

```bash
uv run python scripts/generar_demo.py                   # hoy = 2026-11-25
uv run python scripts/generar_demo.py --hoy 2026-12-01  # recorre todas las caducidades
```

El script reescribe `data/demo/` y `data/escenarios/`. No es aleatorio: con la misma fecha siempre da los mismos archivos, y las pruebas (`tests/test_datos_demo.py`) lo comprueban.

## De dónde sale cada valor

- **Recetas, kg por porción, demanda, vida útil y costos:** las tablas de la caracterización.
- **Inventario:** no se escribe a mano. El script lo calcula con el hábito de compra del negocio:
  - **Compra:** lo que el menú fijo gasta en los días que cubre cada compra, redondeado hacia arriba a la compra mínima del proveedor. Ese redondeo es lo que deja sobrantes en los platillos poco pedidos.
  - **Antigüedad del lote:** fija para cada ingrediente. Determina los días para caducar y cuánto se ha gastado desde la compra.
  - **Regla:** cada lote alcanza todavía para el menú fijo de hoy; si no, el negocio ya habría vuelto a comprar.

Los detalles de la regla están en el docstring de `scripts/generar_demo.py`.

## Lo que vence en menos de 48 horas

Con hoy = 2026-11-25, vencen hoy o mañana 8 ingredientes. Todos son de platillos poco pedidos o de vida corta, que es donde la caracterización ubica el riesgo:

crema ácida, champiñones, chile poblano, carne molida, filete de tilapia, aguacate, pierna y muslo de pollo y nopales.

## Cambios respecto a la caracterización (anotados)

La caracterización tiene 10 platillos fijos, 4 secundarios y 18 perecederos. Para llegar a los 40 ingredientes que pide #19 se amplió el mismo negocio:

- **10 platillos fijos más.** Desayunos (molletes, torta de jamón, huevos con chorizo, hotcakes, coctel de fruta, licuado), un caldo de pollo, chuleta en salsa verde, nopales a la mexicana (poca salida) y pollo con brócoli (poca salida). El horario ya incluía desayunos.
- **2 secundarias más:** sopa de verduras y rajas con crema y elote.
- **22 ingredientes más.** Sus costos y vida útil están dentro de los rangos de la tabla del generador. Jamón, chorizo, leche y huevo no tienen categoría en esa tabla; son estimaciones del equipo.
- **Ventas:** con la ampliación, el menú fijo suma 198 porciones al día en lugar de 125.
- **Champiñones:** se compran una vez por semana, porque el ejemplo de la caracterización supone un lote que dura 5 días.

Ningún valor se ajustó para forzar un resultado. Cualquier cambio futuro se anota aquí.

## Resultado del voraz

Con hoy = 2026-11-25, los dos voraces aprovechan **3.17 de 5.41 kg en riesgo (58.6 %)**:

- **Voraz principal** (`src/menucero/voraz.py`, #20): 9 platillos y 43 porciones en el menú del día, en menos de 1 ms.
- **Prototipo v0** (`uv run python prototipo/voraz_v0.py data/demo --hoy 2026-11-25`): 8 platillos y 39 porciones.

Los resultados de los escenarios están en `data/escenarios/README.md`.

## Pendiente para cerrar #19

- [ ] Pasar la validación de `carga.py` (#13). Ya se probó con la versión de la rama `edguzsv/feature/prototipo` (commit 7162e27): `data/demo/` y los 4 escenarios pasan sin errores. Solo `alta_caducidad/` da 8 advertencias de «ingrediente caducado», que es lo que define ese escenario. Falta que #13 llegue a `main`.
- [ ] Revisar con Less si el generador (#17) debe reutilizar este catálogo.
