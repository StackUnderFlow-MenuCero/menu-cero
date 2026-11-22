"""Fixtures compartidas con el ejemplo de referencia del equipo (issue #11)."""

from datetime import date

import pytest

from menucero.modelos import Ingrediente, Receta

HOY = date(2026, 11, 16)


@pytest.fixture
def hoy() -> date:
    """Fecha de referencia fija para el ejemplo base de pruebas."""
    return HOY


@pytest.fixture
def ingredientes() -> list[Ingrediente]:
    """Inventario de referencia con 5 ingredientes perecederos."""
    return [
        Ingrediente("ING01", "Crema ácida", 2.0, date(2026, 11, 17), 70.0),
        Ingrediente("ING02", "Champiñones", 1.5, date(2026, 11, 18), 95.0),
        Ingrediente("ING03", "Pechuga de pollo", 8.0, date(2026, 11, 20), 120.0),
        Ingrediente("ING04", "Tortilla de maíz", 6.0, date(2026, 11, 19), 25.0),
        Ingrediente("ING05", "Bistec de res", 5.0, date(2026, 11, 18), 180.0),
    ]


@pytest.fixture
def recetas() -> list[Receta]:
    """Recetario de referencia con 3 platillos fijos y 1 receta secundaria."""
    return [
        Receta(
            "REC01",
            "Pollo a la crema con champiñones",
            "fijo",
            {"ING03": 0.150, "ING01": 0.040, "ING02": 0.030},
            3,
            12,
        ),
        Receta(
            "REC02",
            "Tacos de bistec",
            "fijo",
            {"ING05": 0.120, "ING04": 0.090},
            25,
            5,
        ),
        Receta(
            "REC03",
            "Enchiladas suizas",
            "fijo",
            {"ING03": 0.100, "ING01": 0.050, "ING04": 0.080},
            6,
            10,
        ),
        Receta(
            "REC07",
            "Crema de champiñones",
            "secundaria",
            {"ING02": 0.080, "ING01": 0.050},
            0,
            10,
        ),
    ]
