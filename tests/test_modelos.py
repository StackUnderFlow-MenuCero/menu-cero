"""Pruebas de construcción, validación e invariantes de los modelos (issue #11)."""

import ast
from dataclasses import FrozenInstanceError
from datetime import date
from pathlib import Path

import pytest

from menucero.modelos import Ingrediente, MenuGenerado, Receta


def test_construccion_ingrediente():
    ing = Ingrediente(
        id="ING01",
        nombre="Crema ácida",
        cantidad_kg=2.0,
        fecha_caducidad=date(2026, 11, 17),
        costo_kg=70.0,
    )
    assert ing.id == "ING01"
    assert ing.nombre == "Crema ácida"
    assert ing.cantidad_kg == 2.0
    assert ing.fecha_caducidad == date(2026, 11, 17)
    assert ing.costo_kg == 70.0


def test_ingrediente_es_inmutable():
    ing = Ingrediente("ING01", "Crema ácida", 2.0, date(2026, 11, 17), 70.0)
    with pytest.raises(FrozenInstanceError):
        ing.cantidad_kg = 5.0  # type: ignore[misc]


@pytest.mark.parametrize(("kg", "costo"), [(-1.0, 70.0), (2.0, -1.0)])
def test_ingrediente_rechaza_negativos(kg: float, costo: float):
    with pytest.raises(ValueError):
        Ingrediente("ING01", "Crema ácida", kg, date(2026, 11, 17), costo)


def test_construccion_receta_e_inmutabilidad():
    receta = Receta(
        id="REC01",
        platillo="Pollo a la crema con champiñones",
        tipo="fijo",
        ingredientes={"ING03": 0.15, "ING01": 0.04, "ING02": 0.03},
        demanda_fija=3,
        demanda_menu_dia=12,
    )
    assert receta.id == "REC01"
    assert receta.platillo == "Pollo a la crema con champiñones"
    assert receta.tipo == "fijo"
    assert receta.ingredientes == {"ING03": 0.15, "ING01": 0.04, "ING02": 0.03}
    assert receta.demanda_fija == 3
    assert receta.demanda_menu_dia == 12

    with pytest.raises(FrozenInstanceError):
        receta.tipo = "secundaria"  # type: ignore[misc]

    secundaria = Receta("REC07", "Crema de champiñones", "secundaria", {"ING01": 0.05})
    assert secundaria.demanda_fija == 0
    assert secundaria.demanda_menu_dia == 0


def test_receta_rechaza_tipo_invalido():
    with pytest.raises(ValueError, match="fijo o secundaria"):
        Receta("R1", "X", "especial", {"ING01": 0.1})


@pytest.mark.parametrize("kg", [0.0, -0.05])
def test_receta_rechaza_kg_por_porcion_no_positivo(kg: float):
    with pytest.raises(ValueError, match="mayor que 0"):
        Receta("R1", "X", "fijo", {"ING01": kg})


@pytest.mark.parametrize(("fija", "menu"), [(-1, 5), (3, -2)])
def test_receta_rechaza_demandas_negativas(fija: int, menu: int):
    with pytest.raises(ValueError, match="demanda no puede ser negativa"):
        Receta("R1", "X", "fijo", {"ING01": 0.1}, demanda_fija=fija, demanda_menu_dia=menu)


def test_menu_generado_contrato_y_total_porciones():
    # Construcción posicional usada por voraz.py (#20/#23) y fuerza_bruta.py (#24)
    menu = MenuGenerado("base", {"REC01": 12, "REC03": 10}, 1.51667, 0.85)
    assert menu.variante == "base"
    assert menu.porciones == {"REC01": 12, "REC03": 10}
    assert menu.valor == pytest.approx(1.51667)
    assert menu.tiempo_ms == pytest.approx(0.85)
    assert menu.total_porciones == 22
    assert menu.orden_uso == []
    assert menu.metricas == {}

    # Aislamiento de default_factory en orden_uso y metricas
    menu_a = MenuGenerado("manual", {"REC01": 4})
    menu_b = MenuGenerado("manual", {})
    menu_a.orden_uso.append("ING01")
    menu_a.metricas["kg_rescatados"] = 1.0
    assert menu_b.orden_uso == []
    assert menu_b.metricas == {}
    assert menu_b.total_porciones == 0


def test_modelos_no_dependen_de_pandas_ni_streamlit():
    ruta = Path(__file__).resolve().parents[1] / "src" / "menucero" / "modelos.py"
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    importados: set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            importados.update(alias.name.split(".")[0] for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            importados.add(nodo.module.split(".")[0])
    assert "pandas" not in importados
    assert "streamlit" not in importados
