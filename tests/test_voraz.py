"""Pruebas del preprocesamiento y función objetivo del voraz (issue #20)."""

from datetime import date

import pytest

from menucero.modelos import Ingrediente, Receta
from menucero.voraz import VARIANTES, preparar, valor_objetivo


def test_constante_variantes():
    assert VARIANTES == ("base", "sin_principal", "economica", "eficiencia", "secundarias")


def test_preparar_ejemplo_de_referencia(ingredientes, recetas, hoy):
    estado = preparar(ingredientes, recetas, hoy)

    assert set(estado.ingredientes) == {"ING01", "ING02", "ING03", "ING04", "ING05"}
    assert set(estado.recetas) == {"REC01", "REC02", "REC03", "REC07"}
    assert estado.p == pytest.approx(
        {
            "ING01": 0.5,
            "ING02": 1 / 3,
            "ING03": 0.2,
            "ING04": 0.25,
            "ING05": 1 / 3,
        }
    )
    assert estado.disponible == pytest.approx(
        {
            "ING01": 1.58,
            "ING02": 1.41,
            "ING03": 6.95,
            "ING04": 3.27,
            "ING05": 2.00,
        }
    )
    assert estado.riesgo == pytest.approx(
        {
            "ING01": 1.16,
            "ING02": 1.23,
            "ING03": 2.75,
            "ING04": 0.0,
            "ING05": 0.0,
        }
    )
    assert estado.orden == ["ING01", "ING02", "ING03"]
    assert set(estado.usa["ING01"]) == {"REC01", "REC03", "REC07"}
    assert set(estado.usa["ING05"]) == {"REC02"}


def test_preparar_excluye_caducados_y_acepta_diccionarios(ingredientes, recetas):
    # El 18 de noviembre ING01 (vence el 17) ya caducó.
    hoy_18 = date(2026, 11, 18)
    ing_dict = {i.id: i for i in ingredientes}
    rec_dict = {r.id: r for r in recetas}

    estado = preparar(ing_dict, rec_dict, hoy_18)

    assert "ING01" not in estado.ingredientes
    assert "ING01" not in estado.disponible
    assert "ING01" not in estado.riesgo
    assert "ING01" not in estado.orden


def test_preparar_recorta_disponible_a_cero_si_reserva_supera_stock():
    hoy = date(2026, 11, 16)
    ing = [Ingrediente("ING01", "Crema", 0.20, date(2026, 11, 17), 70.0)]
    rec = [Receta("REC01", "Pollo", "fijo", {"ING01": 0.10}, demanda_fija=5, demanda_menu_dia=5)]

    estado = preparar(ing, rec, hoy)
    assert estado.disponible["ING01"] == 0.0
    assert estado.riesgo["ING01"] == 0.0
    assert estado.orden == []


def test_valor_objetivo_vacio_y_ejemplo_base(ingredientes, recetas, hoy):
    estado = preparar(ingredientes, recetas, hoy)

    assert valor_objetivo({}, estado) == 0.0
    assert valor_objetivo({"REC01": 0}, estado) == 0.0

    # En la propuesta base del ejemplo de referencia:
    # ING01 usa 1.48 kg pero solo 1.16 kg están en riesgo (min = 1.16, p = 0.5 -> 0.58)
    # ING02 usa 1.16 kg de 1.23 kg en riesgo (min = 1.16, p = 1/3 -> 0.38667)
    # ING03 usa 2.80 kg pero solo 2.75 kg están en riesgo (min = 2.75, p = 0.2 -> 0.55)
    # ING04 usa 0.80 kg pero tiene 0.0 kg en riesgo (-> 0.0)
    v = valor_objetivo({"REC01": 12, "REC03": 10, "REC07": 10}, estado)
    assert v == pytest.approx(1.51667, abs=1e-5)
