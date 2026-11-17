"""Pruebas de humo: el paquete se importa, la app abre y el comando apunta a ella."""

import importlib
import sys

import pytest
from streamlit.testing.v1 import AppTest

import menucero
from menucero import cli

MODULOS = [
    "modelos",
    "carga",
    "prioridad",
    "voraz",
    "fuerza_bruta",
    "metricas",
    "simulacion",
    "generador",
    "cli",
]


def test_version():
    assert menucero.__version__ == "0.1.0"


@pytest.mark.parametrize("nombre", MODULOS)
def test_modulos_se_importan(nombre):
    importlib.import_module(f"menucero.{nombre}")


def test_app_abre_sin_errores():
    app = AppTest.from_file(str(cli.APP)).run()
    assert not app.exception
    assert app.title[0].value == "Menú Cero"


def test_comando_lanza_streamlit_con_la_app(monkeypatch):
    llamado = {}

    def falso_main():
        llamado["argv"] = list(sys.argv)
        return 0

    monkeypatch.setattr("streamlit.web.cli.main", falso_main)
    monkeypatch.setattr(sys, "argv", ["menucero", "--server.port", "8502"])
    with pytest.raises(SystemExit) as salida:
        cli.main()
    assert salida.value.code == 0
    assert llamado["argv"] == ["streamlit", "run", str(cli.APP), "--server.port", "8502"]
