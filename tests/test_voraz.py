"""Pruebas del preprocesamiento, llenado y función objetivo del voraz (issue #20)."""

from datetime import date

import pytest

from menucero.modelos import Ingrediente, Receta
from menucero.voraz import VARIANTES, llenar, preparar, valor_objetivo


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

    v = valor_objetivo({"REC01": 12, "REC03": 10, "REC07": 10}, estado)
    assert v == pytest.approx(1.51667, abs=1e-5)


def test_llenar_traza_ejemplo_de_referencia(ingredientes, recetas, hoy):
    estado = preparar(ingredientes, recetas, hoy)
    porciones = llenar(estado, variante="base")

    assert porciones == {"REC01": 12, "REC03": 10, "REC07": 10}
    assert valor_objetivo(porciones, estado) == pytest.approx(1.51667, abs=1e-5)


def test_llenar_respeta_permitidas_y_excluidas(ingredientes, recetas, hoy):
    estado = preparar(ingredientes, recetas, hoy)

    assert llenar(estado, permitidas={"REC03"}) == {"REC03": 10}
    assert llenar(estado, permitidas=set()) == {}
    assert llenar(estado, excluidas={"REC01"}) == {"REC03": 10, "REC07": 10}


def test_llenar_ignora_demanda_cero_e_ingredientes_faltantes_o_caducados(hoy):
    ingredientes = [
        Ingrediente("ING01", "Crema", 2.0, date(2026, 11, 17), 70.0),
        Ingrediente("ING_CAD", "Leche", 1.0, date(2026, 11, 15), 30.0),
    ]
    recetas = [
        # Demanda del menú del día en 0 -> no puede proponerse
        Receta("REC_CERO", "Salsa", "fijo", {"ING01": 0.10}, demanda_fija=0, demanda_menu_dia=0),
        # Usa un ingrediente que no existe en inventario -> disponible 0
        Receta(
            "REC_FALTA",
            "Pasta",
            "fijo",
            {"ING01": 0.10, "ING_NO_EXISTE": 0.20},
            demanda_fija=0,
            demanda_menu_dia=10,
        ),
        # Usa un ingrediente caducado -> excluido en preparar, disponible 0
        Receta(
            "REC_CAD",
            "Licuado",
            "secundaria",
            {"ING01": 0.10, "ING_CAD": 0.20},
            demanda_fija=0,
            demanda_menu_dia=10,
        ),
        # Única receta viable
        Receta(
            "REC_OK",
            "Crema pura",
            "secundaria",
            {"ING01": 0.20},
            demanda_fija=0,
            demanda_menu_dia=5,
        ),
    ]

    estado = preparar(ingredientes, recetas, hoy)
    assert llenar(estado) == {"REC_OK": 5}


def test_llenar_sin_ingredientes_en_riesgo_devuelve_vacio(hoy):
    ingredientes = [Ingrediente("ING01", "Bistec", 3.0, date(2026, 11, 18), 180.0)]
    recetas = [
        Receta("REC01", "Tacos", "fijo", {"ING01": 0.12}, demanda_fija=25, demanda_menu_dia=10)
    ]

    estado = preparar(ingredientes, recetas, hoy)
    assert estado.orden == []
    assert llenar(estado) == {}


def test_llenar_acota_porciones_a_las_necesarias_con_tolerancia_eps(hoy):
    # Reserva = 3 * 0.14 = 0.42 kg/día; d = 1 -> riesgo = 2.0 - 0.84 = 1.16 kg; disp = 1.58 kg.
    # En IEEE 754, 1.16 / 0.04 = 28.999999999999996: con EPS debe pedir exactamente 29
    # porciones (sin truncar a 28 y sin agotar las 39 que cabrían en disponible).
    ingredientes = [Ingrediente("ING01", "Crema", 2.0, date(2026, 11, 17), 70.0)]
    recetas = [
        Receta(
            "REC_FIJA", "Base carta", "fijo", {"ING01": 0.14}, demanda_fija=3, demanda_menu_dia=0
        ),
        Receta(
            "REC_DIA",
            "Especial",
            "secundaria",
            {"ING01": 0.04},
            demanda_fija=0,
            demanda_menu_dia=50,
        ),
    ]

    estado = preparar(ingredientes, recetas, hoy)
    assert llenar(estado) == {"REC_DIA": 29}


def test_llenar_rechaza_variante_desconocida(ingredientes, recetas, hoy):
    estado = preparar(ingredientes, recetas, hoy)
    with pytest.raises(ValueError, match="variante desconocida"):
        llenar(estado, variante="inexistente")
