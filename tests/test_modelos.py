"""Pruebas de construcción e invariantes de los modelos (issue #11)."""

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
        ing.cantidad_kg = 1.0  # type: ignore[misc]


def test_construccion_receta_completa_y_valores_por_omision():
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

    secundaria_a = Receta("REC07", "Crema de champiñones", "secundaria")
    secundaria_b = Receta("REC06", "Calabacitas con queso", "secundaria")
    secundaria_a.ingredientes["ING01"] = 0.05
    assert secundaria_b.ingredientes == {}
    assert secundaria_b.demanda_fija == 0
    assert secundaria_b.demanda_menu_dia == 0


def test_construccion_menu_generado():
    menu = MenuGenerado(
        variante="base",
        porciones={"REC01": 12, "REC07": 10},
        orden_uso=[{"ingrediente": "ING01", "vence_en": 0}],
        metricas={"kg_rescatados": 10.3, "aprovechamiento_pct": 75.6},
        tiempo_ms=0.85,
    )
    assert menu.variante == "base"
    assert menu.porciones == {"REC01": 12, "REC07": 10}
    assert menu.orden_uso == [{"ingrediente": "ING01", "vence_en": 0}]
    assert menu.metricas == {"kg_rescatados": 10.3, "aprovechamiento_pct": 75.6}
    assert menu.tiempo_ms == 0.85

    menu_manual_a = MenuGenerado("manual")
    menu_manual_b = MenuGenerado("manual")
    menu_manual_a.porciones["REC01"] = 4
    menu_manual_a.orden_uso.append("ING01")
    menu_manual_a.metricas["kg_rescatados"] = 1.0
    assert menu_manual_b.porciones == {}
    assert menu_manual_b.orden_uso == []
    assert menu_manual_b.metricas == {}
    assert menu_manual_b.tiempo_ms == 0.0


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
