"""Pruebas del dataset de demostración y los escenarios (#19)."""

import csv
from datetime import date, timedelta
from pathlib import Path

import pytest

import generar_demo as gd
import voraz_v0

DATA = Path(__file__).resolve().parents[1] / "data"
ESCENARIOS = ["normal", "examenes", "vacaciones", "alta_caducidad"]
ARCHIVOS = ["inventario.csv", "recetas.csv", "demanda.csv"]


def leer(carpeta: Path, archivo: str) -> list[dict[str, str]]:
    with open(carpeta / archivo, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def dias(fila: dict[str, str], hoy: date = gd.HOY_DEMO) -> int:
    return (date.fromisoformat(fila["fecha_caducidad"]) - hoy).days


def test_demo_tiene_40_ingredientes_unicos():
    inventario = leer(DATA / "demo", "inventario.csv")
    ids = [f["ingrediente_id"] for f in inventario]
    assert len(ids) == 40
    assert len(set(ids)) == 40


def test_ocho_ingredientes_vencen_en_menos_de_48_horas():
    inventario = leer(DATA / "demo", "inventario.csv")
    assert sum(0 <= dias(f) <= 1 for f in inventario) == 8
    assert all(dias(f) >= 0 for f in inventario)


def test_recetas_e_inventario_son_coherentes():
    inventario = {f["ingrediente_id"] for f in leer(DATA / "demo", "inventario.csv")}
    recetas = leer(DATA / "demo", "recetas.csv")
    usados = {f["ingrediente_id"] for f in recetas}
    assert usados == inventario  # todos se usan y ninguno falta
    pares = [(f["receta_id"], f["ingrediente_id"]) for f in recetas]
    assert len(pares) == len(set(pares))
    assert all(float(f["kg_por_porcion"]) > 0 for f in recetas)
    assert {f["tipo"] for f in recetas} == {"fijo", "secundaria"}


def test_demanda_cubre_todas_las_recetas():
    recetas = leer(DATA / "demo", "recetas.csv")
    demanda = {f["receta_id"]: f for f in leer(DATA / "demo", "demanda.csv")}
    tipos = {f["receta_id"]: f["tipo"] for f in recetas}
    assert set(demanda) == set(tipos)
    for receta, tipo in tipos.items():
        if tipo == "secundaria":
            assert demanda[receta]["demanda_fija"] == "0"


@pytest.mark.parametrize("escenario", ESCENARIOS)
def test_los_archivos_guardados_se_regeneran_igual(tmp_path, escenario):
    gd.generar(gd.HOY_DEMO, tmp_path)
    for archivo in ARCHIVOS:
        assert leer(tmp_path / "escenarios" / escenario, archivo) == leer(
            DATA / "escenarios" / escenario, archivo
        )
    assert leer(tmp_path / "demo", "inventario.csv") == leer(DATA / "demo", "inventario.csv")


def test_otra_fecha_recorre_las_caducidades(tmp_path):
    otra = gd.HOY_DEMO + timedelta(days=6)
    gd.generar(otra, tmp_path)
    nuevo = leer(tmp_path / "demo", "inventario.csv")
    guardado = leer(DATA / "demo", "inventario.csv")
    assert [dias(f, otra) for f in nuevo] == [dias(f) for f in guardado]
    assert [f["cantidad_kg"] for f in nuevo] == [f["cantidad_kg"] for f in guardado]


@pytest.mark.parametrize(("escenario", "factor"), [("examenes", 0.8), ("vacaciones", 0.25)])
def test_factor_de_demanda(escenario, factor):
    normal = {f["receta_id"]: f for f in leer(DATA / "escenarios" / "normal", "demanda.csv")}
    for f in leer(DATA / "escenarios" / escenario, "demanda.csv"):
        base = normal[f["receta_id"]]
        assert int(f["demanda_fija"]) == gd.redondear(int(base["demanda_fija"]) * factor)
        assert int(f["demanda_menu_dia"]) == gd.redondear(int(base["demanda_menu_dia"]) * factor)


def test_alta_caducidad_envejece_dos_dias_sin_vender():
    normal = leer(DATA / "escenarios" / "normal", "inventario.csv")
    alta = leer(DATA / "escenarios" / "alta_caducidad", "inventario.csv")
    assert [dias(f) for f in alta] == [dias(f) - 2 for f in normal]
    assert [f["cantidad_kg"] for f in alta] == [f["cantidad_kg"] for f in normal]
    assert sum(dias(f) < 0 for f in alta) == 8


@pytest.mark.parametrize("escenario", ESCENARIOS)
def test_el_prototipo_genera_un_menu_en_cada_escenario(escenario):
    resultado = voraz_v0.generar_menu(
        *voraz_v0.leer_csv(DATA / "escenarios" / escenario), gd.HOY_DEMO
    )
    assert resultado.porciones
    assert resultado.riesgo_total_kg > 0
