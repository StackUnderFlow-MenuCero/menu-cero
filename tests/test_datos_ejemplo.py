"""Revisa que los CSV de ejemplo (#10) cumplan el contrato de docs/datos.md (#7).

No usa carga.py (#13): lee los archivos con el módulo csv para que un cambio que rompa
los datos se detecte aunque la carga todavía no exista.
"""

import csv
import re
from collections import Counter
from datetime import date
from pathlib import Path

import pytest

PRUEBAS = Path(__file__).resolve().parent
EJEMPLO = PRUEBAS.parent / "data" / "ejemplo"
INVALIDOS = PRUEBAS / "datos"
HOY = date(2026, 11, 17)  # fecha de referencia del ejemplo (data/ejemplo/README.md)
ARCHIVOS = ("inventario.csv", "recetas.csv", "demanda.csv")
COLUMNAS = {
    "inventario.csv": ["ingrediente_id", "nombre", "cantidad_kg", "fecha_caducidad", "costo_kg"],
    "recetas.csv": ["receta_id", "platillo", "tipo", "ingrediente_id", "kg_por_porcion"],
    "demanda.csv": ["receta_id", "demanda_fija", "demanda_menu_dia"],
}
ID_VALIDO = re.compile(r"[A-Za-z0-9_-]+")


def leer(archivo: str, carpeta: Path = EJEMPLO) -> list[dict[str, str]]:
    with open(carpeta / archivo, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def encabezado(archivo: str, carpeta: Path = EJEMPLO) -> list[str]:
    with open(carpeta / archivo, encoding="utf-8-sig", newline="") as f:
        return next(csv.reader(f))


@pytest.fixture(scope="module")
def inventario():
    return {f["ingrediente_id"]: f for f in leer("inventario.csv")}


@pytest.fixture(scope="module")
def recetas():
    """receta_id -> {"platillo", "tipo", "q": {ingrediente_id: kg_por_porcion}}"""
    salida = {}
    for f in leer("recetas.csv"):
        r = salida.setdefault(
            f["receta_id"], {"platillo": f["platillo"], "tipo": f["tipo"], "q": {}}
        )
        assert (r["platillo"], r["tipo"]) == (f["platillo"], f["tipo"]), f["receta_id"]
        r["q"][f["ingrediente_id"]] = float(f["kg_por_porcion"])
    return salida


@pytest.fixture(scope="module")
def demanda():
    return {f["receta_id"]: f for f in leer("demanda.csv")}


@pytest.mark.parametrize("archivo", ARCHIVOS)
def test_columnas_del_contrato(archivo):
    assert encabezado(archivo) == COLUMNAS[archivo]


def test_inventario_valido(inventario):
    ids = [f["ingrediente_id"] for f in leer("inventario.csv")]
    assert len(ids) == len(set(ids)) == 12
    for i, f in inventario.items():
        assert ID_VALIDO.fullmatch(i), i
        assert f["nombre"], i
        assert float(f["cantidad_kg"]) > 0, i
        assert float(f["costo_kg"]) > 0, i
        assert date.fromisoformat(f["fecha_caducidad"]) >= HOY, f"{i} ya está caducado"


def test_recetas_validas(inventario, recetas):
    pares = Counter((f["receta_id"], f["ingrediente_id"]) for f in leer("recetas.csv"))
    assert max(pares.values()) == 1, "par receta-ingrediente repetido"
    assert len(recetas) == 7
    for j, r in recetas.items():
        assert ID_VALIDO.fullmatch(j), j
        assert r["tipo"] in ("fijo", "secundaria"), j
        for i, kg in r["q"].items():
            assert i in inventario, f"{j} usa {i}, que no está en el inventario"
            assert 0 < kg <= 1, f"{j}: {i} = {kg} kg por porción"


def test_demanda_valida(recetas, demanda):
    ids = [f["receta_id"] for f in leer("demanda.csv")]
    assert len(ids) == len(set(ids))
    assert set(demanda) == set(recetas), "toda receta tiene demanda y viceversa"
    for j, f in demanda.items():
        fija, menu = int(f["demanda_fija"]), int(f["demanda_menu_dia"])
        assert fija >= 0 and menu >= 0, j
        if recetas[j]["tipo"] == "secundaria":
            assert fija == 0, f"{j} es secundaria y no está en la carta"


def test_todo_ingrediente_lo_usa_alguna_receta(inventario, recetas):
    usados = {i for r in recetas.values() for i in r["q"]}
    assert usados == set(inventario)


def test_cumple_lo_que_pide_el_issue_10(inventario, recetas, demanda):
    def dias(i):
        return (date.fromisoformat(inventario[i]["fecha_caducidad"]) - HOY).days

    por_vencer = {i for i in inventario if dias(i) <= 1}  # vencen en menos de 48 h
    nombres = {inventario[i]["nombre"] for i in por_vencer}
    assert len(por_vencer) >= 3
    assert {"Crema ácida", "Champiñones"} <= nombres

    poca_salida = [
        j
        for j, r in recetas.items()
        if r["tipo"] == "fijo" and int(demanda[j]["demanda_fija"]) <= 3
    ]
    assert any(len(por_vencer & set(recetas[j]["q"])) >= 2 for j in poca_salida)
    assert any(r["tipo"] == "secundaria" for r in recetas.values())


CASOS = sorted(p.name for p in INVALIDOS.iterdir() if p.is_dir())


def test_estan_los_casos_que_pide_el_issue_10():
    assert {"columna_faltante", "cantidad_negativa", "fecha_mal_escrita"} <= set(CASOS)


@pytest.mark.parametrize("caso", CASOS)
def test_cada_caso_cambia_un_solo_archivo(caso):
    distintos = [
        a for a in ARCHIVOS if (INVALIDOS / caso / a).read_bytes() != (EJEMPLO / a).read_bytes()
    ]
    assert len(distintos) == 1, f"{caso}: cambia {distintos}"


def test_columna_faltante():
    columnas = encabezado("inventario.csv", INVALIDOS / "columna_faltante")
    assert set(COLUMNAS["inventario.csv"]) - set(columnas) == {"costo_kg"}


@pytest.mark.parametrize(
    ("caso", "fila", "columna", "valor"),
    [
        ("cantidad_negativa", 3, "cantidad_kg", "-1.5"),
        ("fecha_mal_escrita", 2, "fecha_caducidad", "17/11/2026"),
    ],
)
def test_un_solo_valor_cambiado(caso, fila, columna, valor):
    bueno = leer("inventario.csv")
    malo = leer("inventario.csv", INVALIDOS / caso)
    cambios = [
        (n, c, m[c])
        for n, (b, m) in enumerate(zip(bueno, malo, strict=True), start=2)  # fila 1 = encabezado
        for c in COLUMNAS["inventario.csv"]
        if b[c] != m[c]
    ]
    assert cambios == [(fila, columna, valor)]
