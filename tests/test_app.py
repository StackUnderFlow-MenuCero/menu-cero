"""Pruebas automatizadas de la interfaz Streamlit (issue #26)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = str(Path(__file__).resolve().parents[1] / "src" / "menucero" / "app.py")
INVALIDOS = Path(__file__).resolve().parents[1] / "data" / "invalidos"


def test_app_estado_inicial_pide_datos() -> None:
    at = AppTest.from_file(APP_PATH)
    at.run()

    assert not at.exception
    assert any("Menú Cero" in t.value for t in at.title)
    assert any("Sube los tres CSV" in m.value for m in at.info)


def test_app_carga_ejemplo_y_genera_propuestas() -> None:
    at = AppTest.from_file(APP_PATH)
    at.run()

    # Seleccionar fecha de referencia de la instancia base (2026-11-16) y cargar ejemplo
    at.date_input[0].set_value(date(2026, 11, 16))
    btn_ejemplo = next(b for b in at.button if b.label == "Usar datos de ejemplo")
    btn_ejemplo.click().run()

    assert not at.exception
    assert len(at.dataframe) >= 1
    assert any("ingredientes" in c.value for c in at.caption)

    # Generar propuestas de menú del día
    btn_generar = next(b for b in at.button if b.label == "Generar menú del día")
    btn_generar.click().run()

    assert not at.exception
    assert "propuestas" in at.session_state
    propuestas = at.session_state["propuestas"]
    assert len(propuestas) >= 1

    # Debe mostrarse la tabla comparativa, pestañas y métricas de detalle
    assert len(at.tabs) == len(propuestas)
    assert len(at.metric) >= 4
    assert len(at.dataframe) >= 3


def test_app_limpia_propuestas_al_cambiar_fecha() -> None:
    at = AppTest.from_file(APP_PATH)
    at.run()

    at.date_input[0].set_value(date(2026, 11, 16))
    next(b for b in at.button if b.label == "Usar datos de ejemplo").click().run()
    next(b for b in at.button if b.label == "Generar menú del día").click().run()
    assert "propuestas" in at.session_state

    # Al cambiar la fecha de referencia se invalidan las propuestas previas
    at.date_input[0].set_value(date(2026, 11, 19)).run()

    assert not at.exception
    assert "propuestas" not in at.session_state


def test_app_reporta_errores_con_csv_invalidos() -> None:
    at = AppTest.from_file(APP_PATH)
    at.run()

    carpeta = INVALIDOS / "cantidad_negativa"
    at.session_state["fuentes"] = [
        carpeta / "inventario.csv",
        carpeta / "recetas.csv",
        carpeta / "demanda.csv",
    ]
    at.run()

    assert not at.exception
    assert len(at.error) >= 1
