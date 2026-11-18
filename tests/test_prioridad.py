"""Pruebas de días para caducar, prioridad, merma y ordenamiento (issue #12)."""

import ast
import csv
from datetime import date
from pathlib import Path

import pytest

from menucero.modelos import Ingrediente, Receta
from menucero.prioridad import (
    calcular_reserva_fija,
    dias_para_caducar,
    kg_disponible_hoy,
    kg_en_riesgo,
    ordenar_por_prioridad,
    prioridad,
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


@pytest.mark.parametrize(
    ("dias", "esperada"),
    [
        (0, 1.0),
        (1, 0.5),
        (7, 0.125),
    ],
)
def test_prioridad_valores_del_documento(dias: int, esperada: float):
    assert prioridad(dias) == pytest.approx(esperada)


def test_prioridad_caducado_es_cero():
    assert prioridad(-1) == 0.0
    assert prioridad(-5) == 0.0


def test_dias_para_caducar_usa_fecha_explicita():
    ing = _ing("ING01", date(2026, 11, 20))
    assert dias_para_caducar(ing, date(2026, 11, 20)) == 0
    assert dias_para_caducar(ing, date(2026, 11, 19)) == 1
    assert dias_para_caducar(ing, date(2026, 11, 13)) == 7
    assert dias_para_caducar(ing, date(2026, 11, 22)) == -2


def test_excluye_caducados_y_reporta_merma_perdida():
    hoy = date(2026, 11, 18)
    ingredientes = [
        _ing("ING01", date(2026, 11, 17), cantidad_kg=2.0, costo_kg=70.0, nombre="Crema ácida"),
        _ing("ING02", date(2026, 11, 18), cantidad_kg=1.5, costo_kg=95.0, nombre="Champiñones"),
        _ing("ING03", date(2026, 11, 25), cantidad_kg=3.0, costo_kg=40.0, nombre="Cebolla"),
    ]

    vigentes, merma = ordenar_por_prioridad(ingredientes, hoy)

    assert [v.ingrediente.id for v in vigentes] == ["ING02", "ING03"]
    assert len(merma) == 1
    assert merma[0].ingrediente.id == "ING01"
    assert merma[0].dias == -1
    assert merma[0].cantidad_kg == 2.0
    assert merma[0].costo_perdido == pytest.approx(140.0)


def test_desempate_determinista_prioridad_valor_y_id():
    hoy = date(2026, 11, 17)
    ingredientes = {
        # Prioridad 0.5, valor en riesgo 100.0
        "ING_B": _ing("ING_B", date(2026, 11, 18), cantidad_kg=2.0, costo_kg=50.0),
        # Prioridad 0.5, valor en riesgo 100.0 (empate en prioridad y valor -> gana ING_A)
        "ING_A": _ing("ING_A", date(2026, 11, 18), cantidad_kg=1.0, costo_kg=100.0),
        # Prioridad 0.5, valor en riesgo 200.0 (gana por valor en riesgo)
        "ING_C": _ing("ING_C", date(2026, 11, 18), cantidad_kg=2.0, costo_kg=100.0),
        # Prioridad 1.0, valor en riesgo 10.0 (gana por prioridad)
        "ING_D": _ing("ING_D", date(2026, 11, 17), cantidad_kg=1.0, costo_kg=10.0),
    }

    vigentes, merma = ordenar_por_prioridad(ingredientes, hoy)

    assert merma == []
    assert [v.ingrediente.id for v in vigentes] == ["ING_D", "ING_C", "ING_A", "ING_B"]


def test_reserva_fija_ignora_secundarias_y_calcula_riesgo():
    hoy = date(2026, 11, 17)
    ing = _ing("ING01", date(2026, 11, 17), cantidad_kg=2.0, costo_kg=70.0)
    recetas = [
        Receta("REC01", "Pollo a la crema", "fijo", {"ING01": 0.04}, demanda_fija=3),
        Receta("REC03", "Enchiladas suizas", "fijo", {"ING01": 0.05}, demanda_fija=6),
        # Secundaria no debe contar en la reserva aunque tenga demanda_fija > 0
        Receta("REC07", "Crema", "secundaria", {"ING01": 0.05}, demanda_fija=10),
    ]

    reserva = calcular_reserva_fija(recetas)
    assert reserva["ING01"] == pytest.approx(0.42)
    assert kg_disponible_hoy(ing, reserva["ING01"]) == pytest.approx(1.58)
    assert kg_en_riesgo(ing, dias=0, reserva_diaria_kg=reserva["ING01"]) == pytest.approx(1.58)

    vigentes, _ = ordenar_por_prioridad([ing], hoy, recetas=recetas)
    assert vigentes[0].kg_en_riesgo == pytest.approx(1.58)
    assert vigentes[0].valor_en_riesgo == pytest.approx(110.60)


def test_riesgo_total_coincide_con_datos_ejemplo():
    hoy = date(2026, 11, 17)
    with open(EJEMPLO / "inventario.csv", encoding="utf-8-sig", newline="") as f:
        ingredientes = {
            row["ingrediente_id"]: Ingrediente(
                id=row["ingrediente_id"],
                nombre=row["nombre"],
                cantidad_kg=float(row["cantidad_kg"]),
                fecha_caducidad=date.fromisoformat(row["fecha_caducidad"]),
                costo_kg=float(row["costo_kg"]),
            )
            for row in csv.DictReader(f)
        }

    recetas: dict[str, Receta] = {}
    with open(EJEMPLO / "recetas.csv", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            rec = recetas.setdefault(
                row["receta_id"],
                Receta(
                    id=row["receta_id"],
                    platillo=row["platillo"],
                    tipo=row["tipo"],  # type: ignore[arg-type]
                ),
            )
            rec.ingredientes[row["ingrediente_id"]] = float(row["kg_por_porcion"])

    with open(EJEMPLO / "demanda.csv", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            rec = recetas[row["receta_id"]]
            rec.demanda_fija = int(row["demanda_fija"])
            rec.demanda_menu_dia = int(row["demanda_menu_dia"])

    vigentes, merma = ordenar_por_prioridad(ingredientes, hoy, recetas=recetas)
    assert merma == []
    assert sum(v.kg_en_riesgo for v in vigentes) == pytest.approx(13.62)
    assert sum(v.valor_en_riesgo for v in vigentes) == pytest.approx(1048.70)


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
