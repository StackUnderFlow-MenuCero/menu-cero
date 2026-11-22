"""Pruebas unitarias para metricas.py (#21 y #22)."""

from datetime import date

import pytest

from menucero.metricas import (
    costo_ahorrado,
    desperdicio_evitado,
    metricas_propuesta,
    orden_de_uso,
)
from menucero.modelos import Ingrediente, MenuGenerado, Receta


@pytest.fixture
def datos_base():
    hoy = date(2026, 11, 16)
    ingredientes = [
        Ingrediente("ING01", "Crema ácida", 2.0, date(2026, 11, 17), 70.0),
        Ingrediente("ING02", "Champiñones", 1.5, date(2026, 11, 18), 95.0),
        Ingrediente("ING03", "Pechuga de pollo", 8.0, date(2026, 11, 20), 120.0),
        Ingrediente("ING04", "Tortilla de maíz", 6.0, date(2026, 11, 19), 25.0),
        Ingrediente("ING05", "Bistec de res", 5.0, date(2026, 11, 18), 180.0),
    ]
    recetas = [
        Receta(
            "REC01",
            "Pollo a la crema con champiñones",
            "fijo",
            {"ING03": 0.150, "ING01": 0.040, "ING02": 0.030},
            demanda_fija=3,
            demanda_menu_dia=12,
        ),
        Receta(
            "REC02",
            "Tacos de bistec",
            "fijo",
            {"ING05": 0.120, "ING04": 0.090},
            demanda_fija=25,
            demanda_menu_dia=5,
        ),
        Receta(
            "REC03",
            "Enchiladas suizas",
            "fijo",
            {"ING03": 0.100, "ING01": 0.050, "ING04": 0.080},
            demanda_fija=6,
            demanda_menu_dia=10,
        ),
        Receta(
            "REC07",
            "Crema de champiñones",
            "secundaria",
            {"ING02": 0.080, "ING01": 0.050},
            demanda_fija=0,
            demanda_menu_dia=10,
        ),
    ]
    return ingredientes, recetas, hoy


def test_metricas_del_ejemplo(datos_base):
    ingredientes, recetas, hoy = datos_base
    menu = MenuGenerado("base", {"REC01": 12, "REC03": 10, "REC07": 10})
    m = metricas_propuesta(menu, ingredientes, recetas, hoy)

    assert m["kg_en_riesgo"] == pytest.approx(5.14)
    assert m["kg_rescatados"] == pytest.approx(5.07)
    assert m["pct_aprovechamiento"] == pytest.approx(98.638, abs=1e-3)
    assert m["costo_recuperado"] == pytest.approx(521.40)
    assert m["porciones"] == 32
    assert m["platillos"] == 3


def test_orden_de_uso(datos_base):
    ingredientes, recetas, hoy = datos_base
    menu = MenuGenerado("base", {"REC01": 12, "REC03": 10, "REC07": 10})
    uso = orden_de_uso(menu, ingredientes, recetas, hoy)

    assert [u.ingrediente_id for u in uso] == ["ING01", "ING02", "ING04", "ING03"]
    assert uso[0].kg_a_usar == pytest.approx(1.48)
    assert uso[2].kg_a_usar == pytest.approx(0.80)


def test_propuesta_vacia(datos_base):
    ingredientes, recetas, hoy = datos_base
    menu = MenuGenerado("vacia", {})
    m = metricas_propuesta(menu, ingredientes, recetas, hoy)

    assert m["kg_rescatados"] == pytest.approx(0.0)
    assert m["pct_aprovechamiento"] == pytest.approx(0.0)
    assert m["costo_recuperado"] == pytest.approx(0.0)
    assert m["porciones"] == 0
    assert m["platillos"] == 0
    assert orden_de_uso(menu, ingredientes, recetas, hoy) == []


def test_evaluacion_a_vs_b():
    merma_a = {"ING01": 1.20, "ING02": 1.00}
    merma_b = {"ING01": 0.20, "ING02": 0.40}
    costos = {"ING01": 70.0, "ING02": 95.0}

    assert desperdicio_evitado(merma_a, merma_b) == pytest.approx(72.727, abs=1e-3)
    assert costo_ahorrado(merma_a, merma_b, costos) == pytest.approx(127.0)
    assert desperdicio_evitado({}, {}) is None
    assert desperdicio_evitado({"ING01": 1.0}, {"ING01": 1.5}) == pytest.approx(-50.0)
