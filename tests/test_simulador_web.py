"""Pruebas del simulador de la página (scripts/simulador_web.py, #51)."""

import csv
import io
import json
import re
import subprocess
import sys
import zipfile
from datetime import date

import pytest

import pagina
import simulador_web as sw
import simular
from menucero.simulacion import simular as simular_directo
from menucero.simulacion import voraz_por_omision

HOY = date(2026, 11, 25)


@pytest.fixture(scope="module")
def catalogo():
    return pagina.catalogo()


@pytest.fixture(scope="module")
def ejemplos(catalogo):
    return sw.restaurantes_ejemplo(catalogo)


def merma(corrida, lado):
    return sum(sum(d["merma"]) for d in corrida[lado])


# --- catálogo --------------------------------------------------------------------


def test_el_catalogo_es_valido_para_los_modelos(catalogo):
    assert sw.errores_del_catalogo(catalogo) == []
    assert len(catalogo["cocinas"]) >= 3
    assert len(catalogo["ingredientes"]) >= 60


def test_el_catalogo_detecta_errores(catalogo):
    malo = json.loads(json.dumps(catalogo))
    receta = malo["cocinas"]["italiana"]["recetas"][0]
    receta["ingredientes"]["no_existe"] = 0.1
    receta["ingredientes"]["jitomate"] = 0
    errores = sw.errores_del_catalogo(malo)
    assert any("no_existe" in e for e in errores)
    assert any("kg por porción" in e for e in errores)


def test_los_valores_del_negocio_tipo_coinciden_con_los_datos_demo(catalogo):
    """Lo marcado con fuente docs/datos.md tiene el costo de data/demo."""
    with open(pagina.DEMO / "inventario.csv", encoding="utf-8") as f:
        costos = {r["nombre"]: float(r["costo_kg"]) for r in csv.DictReader(f)}
    revisados = 0
    for ing in catalogo["ingredientes"].values():
        if ing["fuente"] == "docs/datos.md" and ing["nombre"] in costos:
            assert ing["costo_kg"] == costos[ing["nombre"]], ing["nombre"]
            revisados += 1
    assert revisados >= 10


# --- inventario al azar -------------------------------------------------------------


def test_aleatorizar_trae_lo_que_usan_los_platillos_y_se_repite_con_la_semilla(catalogo):
    platillos = sw.platillos_por_omision(catalogo, ["IT01", "IT02", "IT11"])
    inventario = sw.aleatorizar(catalogo, platillos, semilla=7)
    usados = {
        i for rid in platillos for i in sw.recetas_del_catalogo(catalogo)[rid]["ingredientes"]
    }
    assert {f["ingrediente"] for f in inventario} == usados
    assert all(f["cantidad_kg"] > 0 and f["vence_en"] >= 0 for f in inventario)
    assert sw.aleatorizar(catalogo, platillos, semilla=7) == inventario
    assert sw.aleatorizar(catalogo, platillos, semilla=8) != inventario


def test_los_ejemplos_tienen_algo_por_vencer(ejemplos):
    assert len(ejemplos) == 3
    for r in ejemplos:
        assert any(f["vence_en"] <= 1 for f in r["inventario"]), r["nombre"]


# --- simulación ------------------------------------------------------------------------


def test_el_puente_da_lo_mismo_que_llamar_al_simulador(catalogo, ejemplos):
    for r in ejemplos:
        datos = sw.simular_restaurante(catalogo, r, HOY)
        corrida = datos["escenarios"][0]
        ingredientes, recetas = sw.modelos(catalogo, r, HOY)
        comun = {"dias": r["dias"], "semilla": r["semilla"], "ruido": r["ruido"]}
        a = simular_directo(ingredientes, recetas, HOY, escenario="A", **comun)
        b = simular_directo(
            ingredientes, recetas, HOY, escenario="B", generador=voraz_por_omision(), **comun
        )
        assert merma(corrida, "A") == pytest.approx(a.merma_total_kg, abs=0.01)
        assert merma(corrida, "B") == pytest.approx(b.merma_total_kg, abs=0.01)
        assert len(datos["fechas"]) == r["dias"]


def test_usa_el_voraz_que_se_le_pase(catalogo, ejemplos):
    """Así entra el voraz principal (#20): sin menú del día, B es igual que A."""

    def sin_menu(ingredientes, recetas, hoy):
        return {}

    corrida = sw.simular_restaurante(catalogo, ejemplos[0], HOY, generador=sin_menu)
    e = corrida["escenarios"][0]
    assert merma(e, "B") == pytest.approx(merma(e, "A"))
    assert all(not d["menu"] for d in e["B"])


def test_nombre_del_voraz():
    def generar_menu(ingredientes, recetas, hoy):
        return {}

    assert sw.nombre_voraz(generar_menu) == "v0 (prototipo)"
    generar_menu.__module__ = "menucero.voraz"
    assert sw.nombre_voraz(generar_menu) == "voraz (#20)"


def test_la_demanda_de_un_platillo_solo_de_menu_del_dia_no_cuenta_en_la_carta(catalogo):
    r = {
        "nombre": "Prueba",
        "cocina": "mexicana",
        "platillos": {"MX02": {"tipo": "secundaria", "demanda_fija": 25, "demanda_menu_dia": 5}},
        "inventario": [{"ingrediente": "bistec_res", "cantidad_kg": 3, "vence_en": 2}],
    }
    _, recetas = sw.modelos(catalogo, r, HOY)
    assert recetas[0].tipo == "secundaria" and recetas[0].demanda_fija == 0


@pytest.mark.parametrize(
    ("cambio", "texto"),
    [
        ({"inventario": []}, "inventario está vacío"),
        ({"platillos": {}}, "al menos un platillo"),
        (
            {"inventario": [{"ingrediente": "unicornio", "cantidad_kg": 1, "vence_en": 1}]},
            "catálogo",
        ),
        ({"dias": 30}, "de 1 a 14"),
    ],
)
def test_los_errores_llegan_como_mensaje(catalogo, ejemplos, cambio, texto):
    sw.iniciar(json.dumps(catalogo))
    peticion = {"accion": "simular", "restaurante": {**ejemplos[0], **cambio}, "hoy": "2026-11-25"}
    respuesta = json.loads(sw.ejecutar(json.dumps(peticion)))
    assert respuesta["ok"] is False
    assert texto in respuesta["error"]


def test_un_ingrediente_repetido_es_un_error(catalogo, ejemplos):
    r = ejemplos[0]
    with pytest.raises(ValueError, match="dos veces"):
        sw.modelos(catalogo, {**r, "inventario": r["inventario"] + r["inventario"][:1]}, HOY)


# --- CSV oficiales ----------------------------------------------------------------------------


def test_los_csv_se_leen_como_los_de_data(catalogo, ejemplos, tmp_path):
    r = {**ejemplos[1], "inventario": ejemplos[1]["inventario"][1:]}  # falta un ingrediente
    archivos = sw.a_csv(catalogo, r, HOY)
    encabezados = {
        "inventario.csv": "ingrediente_id,nombre,cantidad_kg,fecha_caducidad,costo_kg",
        "recetas.csv": "receta_id,platillo,tipo,ingrediente_id,kg_por_porcion",
        "demanda.csv": "receta_id,demanda_fija,demanda_menu_dia",
    }
    for nombre, texto in archivos.items():
        assert texto.splitlines()[0] == encabezados[nombre]
        (tmp_path / nombre).write_text(texto, encoding="utf-8")

    ingredientes, recetas = simular.leer_escenario(tmp_path, HOY)
    ids = {ing.id for ing in ingredientes}
    assert all(re.fullmatch(r"ING\d{2}", i) for i in ids)
    assert all(i in ids for rec in recetas for i in rec.ingredientes)
    assert len(recetas) == len(r["platillos"])
    assert sum(ing.cantidad_kg == 0 for ing in ingredientes) == 1  # el que faltaba, en 0 kg

    with zipfile.ZipFile(io.BytesIO(sw.zip_csv(catalogo, r, HOY))) as z:
        assert sorted(z.namelist()) == sorted(archivos)


# --- lo que se publica ---------------------------------------------------------------------------

PRUEBA_AISLADA = """
import json, sys
raiz, catalogo = sys.argv[1], open(sys.argv[2], encoding="utf-8").read()
sys.path[:0] = [raiz + "/src", raiz + "/scripts"]
import menucero, simulador_web
assert menucero.__file__.startswith(raiz), menucero.__file__
print(simulador_web.iniciar(catalogo))
ejemplo = simulador_web.restaurantes_ejemplo(json.loads(catalogo))[0]
peticion = {"accion": "simular", "restaurante": ejemplo, "hoy": "2026-11-25"}
print(simulador_web.ejecutar(json.dumps(peticion)))
"""


def test_el_paquete_para_el_navegador_corre_solo(tmp_path, catalogo, ejemplos):
    """El zip corre con la biblioteca estándar, sin site-packages, como en Pyodide."""
    destino = pagina.paquete_python(tmp_path / "paquete.zip")
    with zipfile.ZipFile(destino) as z:
        nombres = set(z.namelist())
        z.extractall(tmp_path / "web")
    necesarios = {"src/menucero/simulacion.py", "prototipo/voraz_v0.py", "scripts/simulador_web.py"}
    assert necesarios <= nombres
    assert any(n.endswith(".dist-info/METADATA") for n in nombres)

    salida = subprocess.run(
        [sys.executable, "-I", "-S", "-c", PRUEBA_AISLADA, str(tmp_path / "web"), pagina.CATALOGO],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    assert salida[0] == sw.nombre_voraz(voraz_por_omision())
    respuesta = json.loads(salida[1])
    esperado = sw.simular_restaurante(catalogo, ejemplos[0], HOY)
    assert respuesta["ok"] is True
    assert respuesta["escenarios"] == json.loads(json.dumps(esperado["escenarios"]))


def test_la_vista_del_simulador_se_construye(tmp_path):
    pagina.construir(tmp_path, con_pruebas=False)
    html = (tmp_path / "simulador.html").read_text(encoding="utf-8")
    assert not pagina.MARCA.search(html)  # el JSON sí lleva «}}», pero ninguna marca sin llenar
    for ruta in ("simulador.js", "visor.js", "sitio.js", "estilo.css", pagina.PAQUETE):
        assert (tmp_path / ruta).is_file(), ruta
    for id_ in ("catalogo", "restaurantes-ejemplo", "config-simulador"):
        m = re.search(rf'<script id="{id_}" type="application/json">(.*?)</script>', html, re.S)
        assert json.loads(m.group(1)), id_
    assert 'id="visor"' in html
    assert 'href="simulador.html"' in (tmp_path / "index.html").read_text(encoding="utf-8")


def test_el_simulador_va_por_pasos(tmp_path):
    """Un paso a la vez: cinco secciones, cada una con «Retroceder» y/o «Siguiente»."""
    pagina.construir(tmp_path, con_pruebas=False)
    html = (tmp_path / "simulador.html").read_text(encoding="utf-8")
    secciones = re.findall(r'<section id="([^"]+)" data-paso="(\d)">(.*?)</section>', html, re.S)
    assert [(s[0], s[1]) for s in secciones] == [
        ("restaurante", "1"),
        ("platillos", "2"),
        ("inventario", "3"),
        ("simular", "4"),
        ("resultado", "5"),
    ]
    for i, (id_, _, cuerpo) in enumerate(secciones):
        assert 'class="sim-navegacion"' in cuerpo, id_
        assert ('data-ir="anterior"' in cuerpo) == (i > 0), id_
        assert f'href="#{id_}"' in html, id_  # la guía de pasos enlaza a cada uno
    assert 'id="sim-simular"' in secciones[3][2]
    assert 'id="visor"' in secciones[4][2]
