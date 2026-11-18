"""Pruebas del prototipo v0 del voraz (prototipo/voraz_v0.py) con data/ejemplo."""

from datetime import date
from pathlib import Path

import pytest

import voraz_v0 as v0

EJEMPLO = Path(__file__).resolve().parents[1] / "data" / "ejemplo"
HOY = date(2026, 11, 17)


@pytest.fixture
def datos():
    return v0.leer_csv(EJEMPLO)


@pytest.mark.parametrize(("dias", "esperada"), [(0, 1.0), (1, 0.5), (3, 0.25), (9, 0.1)])
def test_prioridad_es_uno_entre_dias_mas_uno(datos, dias, esperada):
    ingredientes, recetas = datos
    hoy = date.fromordinal(ingredientes["ING01"].caducidad.toordinal() - dias)
    assert v0.calcular_urgencias(ingredientes, recetas, hoy)["ING01"].prioridad == esperada


def test_kg_en_riesgo_coinciden_con_el_readme_de_los_datos(datos):
    urgencias = v0.calcular_urgencias(*datos, HOY)
    riesgo = {i: round(u.riesgo_kg, 2) for i, u in urgencias.items()}
    assert riesgo == {
        "ING01": 1.58,
        "ING02": 1.32,
        "ING03": 3.80,
        "ING04": 0,
        "ING05": 0,
        "ING06": 1.44,
        "ING07": 1.80,
        "ING08": 0.58,
        "ING09": 1.90,
        "ING10": 1.20,
        "ING11": 0,
        "ING12": 0,
    }


def test_respeta_el_inventario_disponible(datos):
    urgencias = v0.calcular_urgencias(*datos, HOY)
    resultado = v0.generar_menu(*datos, HOY)
    for i, usado in resultado.usado_kg.items():
        assert -1e-9 <= usado <= urgencias[i].disponible_kg + 1e-9


def test_respeta_la_demanda_del_menu_del_dia(datos):
    _, recetas = datos
    resultado = v0.generar_menu(*datos, HOY)
    for j, x in resultado.porciones.items():
        assert 1 <= x <= recetas[j].demanda_menu_dia


def test_no_usa_ingredientes_caducados(datos):
    # El 18 de noviembre la crema (ING01) ya caducó: no entra ninguna receta que la use.
    _, recetas = datos
    resultado = v0.generar_menu(*datos, date(2026, 11, 18))
    assert "ING01" not in resultado.usado_kg
    for j in resultado.porciones:
        assert "ING01" not in recetas[j].kg_por_porcion


def test_resultado_del_ejemplo(datos):
    resultado = v0.generar_menu(*datos, HOY)
    assert resultado.porciones == {
        "REC04": 8,
        "REC01": 12,
        "REC07": 10,
        "REC03": 10,
        "REC06": 8,
        "REC05": 4,
    }
    assert resultado.valor == pytest.approx(4.25455, abs=1e-5)
    assert resultado.porcentaje == pytest.approx(75.6, abs=0.05)


def test_sin_ingredientes_en_riesgo_no_propone_nada(datos):
    ingredientes, recetas = datos
    for receta in recetas.values():
        receta.demanda_fija = 1000  # el menú fijo se lo come todo a tiempo
    resultado = v0.generar_menu(ingredientes, recetas, HOY)
    assert resultado.porciones == {}
    assert resultado.porcentaje == 0.0


def test_comando_imprime_el_menu(capsys):
    v0.main([str(EJEMPLO), "--hoy", "2026-11-17"])
    salida = capsys.readouterr().out
    assert "Menú del día propuesto" in salida
    assert "(75.6 %)" in salida
