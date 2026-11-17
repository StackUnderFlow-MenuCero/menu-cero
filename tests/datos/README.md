# Archivos inválidos para probar la carga

Cada carpeta es una copia de `data/ejemplo/` con **un solo** error en `inventario.csv`. `recetas.csv` y `demanda.csv` son idénticos al ejemplo, así que la carga debe reportar ese error y nada más.

| Carpeta | Qué se cambió | Error que debe reportar `cargar_datos` (#13) |
|---|---|---|
| `columna_faltante/` | se quitó la columna `costo_kg` | `inventario.csv: falta la columna obligatoria costo_kg` |
| `cantidad_negativa/` | ING02 (fila 3) tiene `cantidad_kg = -1.5` | `inventario.csv, fila 3, columna cantidad_kg: no puede ser negativa («-1.5»)` |
| `fecha_mal_escrita/` | ING01 (fila 2) tiene la fecha `17/11/2026` | `inventario.csv, fila 2, columna fecha_caducidad: no es una fecha AAAA-MM-DD («17/11/2026»)` |

El texto exacto del mensaje lo decide la carga. Las pruebas deberían revisar el archivo, la fila, la columna y el valor, no la redacción.

```python
from pathlib import Path

DATOS = Path(__file__).parent / "datos"


def rutas(caso: str) -> list[Path]:
    return [DATOS / caso / f"{n}.csv" for n in ("inventario", "recetas", "demanda")]


def test_fecha_mal_escrita():
    res = cargar_datos(*rutas("fecha_mal_escrita"))
    assert not res.ok
    [error] = res.errores
    assert (error.archivo, error.fila, error.columna, error.valor) == (
        "inventario.csv",
        2,
        "fecha_caducidad",
        "17/11/2026",
    )
```

Si agregas más casos, sigue la misma regla: una carpeta por error y los otros dos archivos sin cambios. `tests/test_datos_ejemplo.py` revisa que se cumpla.
