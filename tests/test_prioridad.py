"""Pruebas de días para caducar, prioridad, reserva y kg en riesgo (issue #12)."""

import ast
import csv
from datetime import date
from pathlib import Path

import pytest

from menucero.modelos import Ingrediente, Receta
from menucero.prioridad import (
    dias_para_caducar,
    kg_en_riesgo,
    ordenar_por_prioridad,
    prioridad,
    reserva_diaria,
    separar_caducados,
)

EJEMPLO = Path(__file__).resolve().parents[1] / "data" / "ejemplo"


def _ing(
    ing_id: str,
    caducidad: date,
    cantidad_kg: float = 2.0,
    costo_kg: float = 50.0,
    nombre: str = "Ingrediente",
) -> Ingrediente:
    return Ingrediente(
        id=ing_id,
        nombre=nombre,
        cantidad_kg=cantidad_kg,
        fecha_caducidad=caducidad,
        costo_kg=costo_kg,
    )


@pytest.mark.parametrize(("dias", "esperado"), [(0, 1.0), (1, 0.5), (7, 0.125)])
def test_prioridad_valores_del_documento(dias: int, esperado: float):
    assert prioridad(dias) == pytest.approx(esperado)


@pytest.mark.parametrize("dias", [-1, -5])
def test_prioridad_rechaza_caducados(dias: int):
    with pytest.raises(ValueError, match="caducado"):
        prioridad(dias)


def test_dias_para_caducar_usa_fecha_explicita():
    ing = _ing("ING01", date(2026, 11, 20))
    assert dias_para_caducar(ing, date(2026, 11, 20)) == 0
    assert dias_para_caducar(ing, date(2026, 11, 19)) == 1
    assert dias_para_caducar(ing, date(2026, 11, 13)) == 7
    assert dias_para_caducar(ing, date(2026, 11, 22)) == -2


def test_separar_caducados_conserva_orden_y_excluye_del_ordenamiento():
    hoy = date(2026, 11, 18)
    lista = [
        _ing("ING_V1", date(2026, 11, 20)),
        _ing("ING_CAD1", date(2026, 11, 17)),
        _ing("ING_V2", date(2026, 11, 18)),
        _ing("ING_CAD2", date(2026, 11, 15)),
    ]

    vigentes, caducados = separar_caducados(lista, hoy)
    assert [i.id for i in vigentes] == ["ING_V1", "ING_V2"]
    assert [i.id for i in caducados] == ["ING_CAD1", "ING_CAD2"]

    ordenados = ordenar_por_prioridad(lista, hoy)
    assert [i.id for i in ordenados] == ["ING_V2", "ING_V1"]


def test_reserva_diaria_del_ejemplo_e_ignora_secundarias(recetas):
    esperada = {
        "ING01": 0.42,
        "ING02": 0.09,
        "ING03": 1.05,
        "ING04": 2.73,
        "ING05": 3.00,
    }
    assert reserva_diaria(recetas) == pytest.approx(esperada)

    # Una receta secundaria no debe sumar a la reserva aunque tenga demanda_fija > 0
    secundaria_con_fija = Receta(
        "REC99",
        "Sopa extra",
        "secundaria",
        {"ING01": 0.50},
        demanda_fija=10,
        demanda_menu_dia=5,
    )
    assert reserva_diaria([*recetas, secundaria_con_fija]) == pytest.approx(esperada)


def test_kg_en_riesgo_del_ejemplo_y_caducado_en_cero(ingredientes, recetas, hoy):
    r = kg_en_riesgo(ingredientes, recetas, hoy)
    assert r == pytest.approx(
        {"ING01": 1.16, "ING02": 1.23, "ING03": 2.75, "ING04": 0.0, "ING05": 0.0}
    )

    caducado = _ing("ING_CAD", date(2026, 11, 15), cantidad_kg=3.0, costo_kg=80.0)
    r_con_caducado = kg_en_riesgo([*ingredientes, caducado], recetas, hoy)
    assert r_con_caducado["ING_CAD"] == 0.0


def test_orden_cambia_con_riesgo(ingredientes, recetas, hoy):
    orden_sin_riesgo = [i.id for i in ordenar_por_prioridad(ingredientes, hoy)]
    assert orden_sin_riesgo == ["ING01", "ING05", "ING02", "ING04", "ING03"]

    riesgo = kg_en_riesgo(ingredientes, recetas, hoy)
    orden_con_riesgo = [i.id for i in ordenar_por_prioridad(ingredientes, hoy, riesgo)]
    assert orden_con_riesgo == ["ING01", "ING02", "ING05", "ING04", "ING03"]


def test_desempate_determinista_por_id():
    hoy = date(2026, 11, 17)
    lista = [
        _ing("ING_B", date(2026, 11, 18), cantidad_kg=2.0, costo_kg=50.0),
        _ing("ING_A", date(2026, 11, 18), cantidad_kg=1.0, costo_kg=100.0),
        _ing("ING_C", date(2026, 11, 18), cantidad_kg=2.0, costo_kg=100.0),
    ]
    ordenados = ordenar_por_prioridad(lista, hoy)
    assert [i.id for i in ordenados] == ["ING_C", "ING_A", "ING_B"]


def test_riesgo_total_coincide_con_datos_ejemplo():
    hoy = date(2026, 11, 17)
    with open(EJEMPLO / "inventario.csv", encoding="utf-8-sig", newline="") as f:
        inventario = [
            Ingrediente(
                id=row["ingrediente_id"],
                nombre=row["nombre"],
                cantidad_kg=float(row["cantidad_kg"]),
                fecha_caducidad=date.fromisoformat(row["fecha_caducidad"]),
                costo_kg=float(row["costo_kg"]),
            )
            for row in csv.DictReader(f)
        ]

    datos_recetas: dict[str, dict[str, object]] = {}
    with open(EJEMPLO / "recetas.csv", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            entry = datos_recetas.setdefault(
                row["receta_id"],
                {"platillo": row["platillo"], "tipo": row["tipo"], "ingredientes": {}},
            )
            entry["ingredientes"][row["ingrediente_id"]] = float(row["kg_por_porcion"])  # type: ignore[index]

    demandas: dict[str, tuple[int, int]] = {}
    with open(EJEMPLO / "demanda.csv", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            demandas[row["receta_id"]] = (int(row["demanda_fija"]), int(row["demanda_menu_dia"]))

    lista_recetas = [
        Receta(
            id=rec_id,
            platillo=str(entry["platillo"]),
            tipo=str(entry["tipo"]),
            ingredientes=entry["ingredientes"],  # type: ignore[arg-type]
            demanda_fija=demandas[rec_id][0],
            demanda_menu_dia=demandas[rec_id][1],
        )
        for rec_id, entry in datos_recetas.items()
    ]

    _, caducados = separar_caducados(inventario, hoy)
    assert caducados == []

    riesgo = kg_en_riesgo(inventario, lista_recetas, hoy)
    assert sum(riesgo.values()) == pytest.approx(13.62)
    assert sum(riesgo[i.id] * i.costo_kg for i in inventario) == pytest.approx(1048.70)


def test_prioridad_no_usa_pandas_streamlit_ni_fecha_del_sistema():
    ruta = Path(__file__).resolve().parents[1] / "src" / "menucero" / "prioridad.py"
    codigo = ruta.read_text(encoding="utf-8")
    arbol = ast.parse(codigo)
    importados: set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            importados.update(alias.name.split(".")[0] for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            importados.add(nodo.module.split(".")[0])
    assert "pandas" not in importados
    assert "streamlit" not in importados
    assert "today(" not in codigo
    assert "now(" not in codigo
