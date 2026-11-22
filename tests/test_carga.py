"""Pruebas unitarias para carga.py (Issue #13)."""

from datetime import date
from pathlib import Path

import pytest

from menucero.carga import cargar_datos

PRUEBAS = Path(__file__).resolve().parent
EJEMPLO = PRUEBAS.parent / "data" / "ejemplo"
INVALIDOS = PRUEBAS / "datos"
HOY = date(2026, 11, 17)

INV_BASE = (
    "ingrediente_id,nombre,cantidad_kg,fecha_caducidad,costo_kg\n"
    "ING01,Crema ácida,2.0,2026-11-18,70.0\n"
    "ING02,Champiñones,1.5,2026-11-19,95.0\n"
)

REC_BASE = (
    "receta_id,platillo,tipo,ingrediente_id,kg_por_porcion\n"
    "REC01,Pollo a la crema,fijo,ING01,0.05\n"
    "REC02,Sopa de hongos,secundaria,ING02,0.08\n"
)

DEM_BASE = "receta_id,demanda_fija,demanda_menu_dia\nREC01,3,10\nREC02,0,8\n"


def _escribir_triada(
    carpeta: Path,
    inv: str = INV_BASE,
    rec: str = REC_BASE,
    dem: str = DEM_BASE,
    encoding: str = "utf-8",
) -> tuple[Path, Path, Path]:
    p_inv = carpeta / "inventario.csv"
    p_rec = carpeta / "recetas.csv"
    p_dem = carpeta / "demanda.csv"
    p_inv.write_text(inv, encoding=encoding)
    p_rec.write_text(rec, encoding=encoding)
    p_dem.write_text(dem, encoding=encoding)
    return p_inv, p_rec, p_dem


def test_carga_ejemplo_oficial():
    res = cargar_datos(
        EJEMPLO / "inventario.csv",
        EJEMPLO / "recetas.csv",
        EJEMPLO / "demanda.csv",
        hoy=HOY,
    )
    assert res.ok, [str(m) for m in res.errores]
    assert len(res.ingredientes) == 12
    assert len(res.recetas) == 7


def test_carga_valida_con_bom_y_fila_vacia(tmp_path: Path):
    inv_con_vacia = (
        "ingrediente_id,nombre,cantidad_kg,fecha_caducidad,costo_kg\n"
        "ING01,Crema ácida,2.0,2026-11-18,70.0\n"
        "\n"
        "ING02,Champiñones,-1.5,2026-11-19,95.0\n"
    )
    rutas = _escribir_triada(tmp_path, inv=inv_con_vacia, encoding="utf-8-sig")
    res = cargar_datos(*rutas, hoy=HOY)

    assert not res.ok
    assert len(res.errores) == 1
    err = res.errores[0]
    assert err.archivo == "inventario.csv"
    assert err.fila == 4
    assert err.columna == "cantidad_kg"


@pytest.mark.parametrize(
    ("caso", "archivo_esperado", "fila_esperada", "columna_esperada"),
    [
        ("columna_faltante", "inventario.csv", 1, "costo_kg"),
        ("cantidad_negativa", "inventario.csv", 3, "cantidad_kg"),
        ("fecha_mal_escrita", "inventario.csv", 2, "fecha_caducidad"),
    ],
)
def test_casos_invalidos_en_repo(
    caso: str, archivo_esperado: str, fila_esperada: int, columna_esperada: str
):
    carpeta = INVALIDOS / caso
    res = cargar_datos(
        carpeta / "inventario.csv",
        carpeta / "recetas.csv",
        carpeta / "demanda.csv",
        hoy=HOY,
    )
    assert not res.ok
    assert any(
        m.archivo == archivo_esperado and m.fila == fila_esperada and m.columna == columna_esperada
        for m in res.errores
    )


def test_coma_decimal_e_id_duplicado_acumulan_errores(tmp_path: Path):
    inv_malo = (
        "ingrediente_id,nombre,cantidad_kg,fecha_caducidad,costo_kg\n"
        'ING01,Crema ácida,"2,5",2026-11-18,70.0\n'
        "ING01,Crema repetida,1.0,2026-11-19,70.0\n"
    )
    rutas = _escribir_triada(tmp_path, inv=inv_malo)
    res = cargar_datos(*rutas, hoy=HOY)

    assert not res.ok
    assert len(res.errores) >= 2
    textos = " | ".join(str(m) for m in res.errores)
    assert "2,5" in textos
    assert "repetido" in textos


def test_advertencias_ingrediente_faltante_y_secundaria_con_demanda_fija(tmp_path: Path):
    rec_extra = REC_BASE + "REC02,Sopa de hongos,secundaria,ING99,0.05\n"
    dem_extra = "receta_id,demanda_fija,demanda_menu_dia\nREC01,3,10\nREC02,4,8\n"
    rutas = _escribir_triada(tmp_path, rec=rec_extra, dem=dem_extra)
    res = cargar_datos(*rutas, hoy=HOY)

    assert res.ok
    assert len(res.advertencias) >= 2
    rec_sec = next(r for r in res.recetas if r.id == "REC02")
    assert rec_sec.demanda_fija == 0
    assert rec_sec.ingredientes["ING99"] == pytest.approx(0.05)


def test_receta_sin_fila_de_demanda_genera_advertencia_y_cero(tmp_path: Path):
    dem_sin_rec02 = "receta_id,demanda_fija,demanda_menu_dia\nREC01,3,10\n"
    rutas = _escribir_triada(tmp_path, dem=dem_sin_rec02)
    res = cargar_datos(*rutas, hoy=HOY)

    assert res.ok
    assert any(m.archivo == "demanda.csv" for m in res.advertencias)
    rec_02 = next(r for r in res.recetas if r.id == "REC02")
    assert rec_02.demanda_fija == 0
    assert rec_02.demanda_menu_dia == 0
