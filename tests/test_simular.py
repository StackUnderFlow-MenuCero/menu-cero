"""Pruebas de las corridas de simulación (scripts/simular.py, #28)."""

import csv
from pathlib import Path

import pytest

import simular

RESULTADOS = Path(__file__).resolve().parents[1] / "resultados"
ARCHIVOS = ("simulacion.csv", "resumen.csv", "resumen.md", "sensibilidad_venta.csv")


def leer(ruta: Path) -> list[dict[str, str]]:
    with open(ruta, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


@pytest.fixture(scope="module")
def corrida(tmp_path_factory):
    salida = tmp_path_factory.mktemp("resultados")
    simular.main(["--semillas", "3", "--salida", str(salida)])
    return salida


def test_escribe_una_fila_por_escenario_horizonte_y_semilla(corrida):
    filas = leer(corrida / "simulacion.csv")
    assert list(filas[0]) == simular.COLUMNAS
    assert len(filas) == 4 * 2 * 3
    claves = {(f["escenario"], f["dias"], f["semilla"]) for f in filas}
    assert len(claves) == len(filas)
    assert len(leer(corrida / "resumen.csv")) == 4 * 2


def test_las_metricas_de_cada_fila_son_coherentes(corrida):
    for f in leer(corrida / "simulacion.csv"):
        a, b = float(f["merma_a_kg"]), float(f["merma_b_kg"])
        assert float(f["desperdicio_evitado_pct"]) == pytest.approx(100 * (a - b) / a, abs=0.02)
        ahorro = float(f["merma_a_costo"]) - float(f["merma_b_costo"])
        assert float(f["costo_ahorrado"]) == pytest.approx(ahorro, abs=0.02)


def test_genera_las_graficas(corrida):
    for nombre in ("merma_a_vs_b.png", "desperdicio_evitado.png", "sensibilidad_venta.png"):
        assert (corrida / nombre).stat().st_size > 10_000


def test_se_repite_con_las_mismas_semillas(corrida, tmp_path):
    simular.main(["--semillas", "3", "--salida", str(tmp_path), "--sin-graficas"])
    for archivo in ARCHIVOS:
        assert (tmp_path / archivo).read_text() == (corrida / archivo).read_text()


def test_los_resultados_guardados_estan_al_dia(tmp_path):
    simular.main(["--salida", str(tmp_path), "--sin-graficas"])
    for archivo in ARCHIVOS:
        assert (tmp_path / archivo).read_text() == (RESULTADOS / archivo).read_text()


def test_formulas_de_evaluacion_con_el_ejemplo_de_la_guia():
    a = {"ING01": 1.20, "ING02": 1.00}
    b = {"ING01": 0.20, "ING02": 0.40}
    assert simular.desperdicio_evitado(a, b) == pytest.approx(72.727, abs=1e-3)
    assert simular.costo_ahorrado(a, b, {"ING01": 70.0, "ING02": 95.0}) == pytest.approx(127.0)
    assert simular.desperdicio_evitado({}, {}) is None


def test_la_perdida_de_urgentes_sale_de_sus_kg(corrida):
    for f in leer(corrida / "simulacion.csv"):
        urgentes = float(f["urgentes_kg"])
        assert urgentes > 0
        for esc in ("a", "b"):
            merma = float(f[f"merma_urgentes_{esc}_kg"])
            assert 0 <= merma <= urgentes + 1e-9
            assert float(f[f"perdida_urgentes_{esc}_pct"]) == pytest.approx(
                100 * merma / urgentes, abs=0.01
            )


def test_la_sensibilidad_cubre_cada_venta_y_tira_los_sobrantes(corrida):
    filas = leer(corrida / "sensibilidad_venta.csv")
    assert len(filas) == len(simular.VENTAS) * 4 * 3
    assert {f["dias"] for f in filas} == {str(simular.DIAS_SENSIBILIDAD)}
    por_venta = {}
    for f in filas:
        por_venta.setdefault(float(f["venta"]), []).append(int(f["sobrantes_menu_dia_b"]))
    # Mientras menos se vende, más porciones del menú del día sobran.
    assert sum(por_venta[0.5]) > sum(por_venta[0.75]) > sum(por_venta[1.0])
    # A no depende del supuesto de venta del menú del día.
    merma_a = {(f["escenario"], f["semilla"], f["venta"]): f["merma_a_kg"] for f in filas}
    for (escenario, semilla, _), kg in merma_a.items():
        assert kg == merma_a[(escenario, semilla, "1.0")]
