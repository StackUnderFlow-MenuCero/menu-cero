"""Pruebas de la página web pública (scripts/pagina.py, #49)."""

import json
import re

import pytest

import pagina
import simular

SECCIONES = (
    "problema",
    "equipo",
    "algoritmos",
    "metodologia",
    "dia-a-dia",
    "resultados",
    "conclusiones",
    "enlaces",
    "evidencias",
)


@pytest.fixture(scope="module")
def sitio(tmp_path_factory):
    salida = tmp_path_factory.mktemp("sitio")
    indice = pagina.construir(salida, con_pruebas=False)
    return salida, indice.read_text(encoding="utf-8")


def test_tiene_el_contenido_minimo_que_pide_el_curso(sitio):
    _, html = sitio
    for seccion in SECCIONES:
        assert f'<section id="{seccion}">' in html
        assert f'href="#{seccion}"' in html  # y está en la barra de navegación


def test_no_quedan_marcas_sin_llenar(sitio):
    _, html = sitio
    assert "{{" not in html and "}}" not in html


def test_los_enlaces_locales_apuntan_a_archivos_del_sitio(sitio):
    salida, html = sitio
    locales = {
        r
        for r in re.findall(r'(?:src|href)="([^"]+)"', html)
        if not r.startswith(("http", "#", "mailto:"))
    }
    assert {f"resultados/{n}" for n in pagina.FIGURAS + pagina.DESCARGAS} <= locales
    for ruta in locales:
        assert (salida / ruta).is_file(), ruta


def test_las_figuras_tienen_texto_alternativo(sitio):
    _, html = sitio
    imagenes = re.findall(r"<img [^>]*>", html)
    assert len(imagenes) == len(pagina.FIGURAS)
    for img in imagenes:
        assert re.search(r'alt="[^"]{20,}"', img), img


def test_la_tabla_de_merma_sale_del_resumen(sitio):
    _, html = sitio
    resumen = pagina.leer(pagina.RESULTADOS / "resumen.csv")
    tabla = html[html.index("<strong>Tabla 1.</strong>") : html.index("<strong>Figura 1.</strong>")]
    assert tabla.count("<tr><td>") == len(resumen)
    for r in resumen:
        celda = pagina.pm(r["merma_a_kg_prom"], r["merma_a_kg_de"])
        assert f'<td class="num">{celda}</td>' in tabla


def test_las_cifras_del_texto_coinciden_con_las_corridas():
    filas = pagina.leer(pagina.RESULTADOS / "simulacion.csv")
    resumen = pagina.leer(pagina.RESULTADOS / "resumen.csv")
    sens = pagina.leer(pagina.RESULTADOS / "sensibilidad_venta.csv")
    c = pagina.cifras(filas, resumen, sens)

    assert c["pares"] == str(len(filas))
    gana = sum(float(f["merma_b_kg"]) < float(f["merma_a_kg"]) for f in filas)
    assert c["pares_b_menor"] == str(gana)
    assert int(c["evitado_prom_min"]) <= int(c["evitado_prom_max"])
    assert c["semillas"] == "30"
    total = len(sens) // len(simular.VENTAS)
    for venta in ("100", "75", "50"):
        assert c[f"venta_{venta}"].endswith(f"de {total}")


def test_la_demostracion_tiene_40_ingredientes_y_8_urgentes():
    conteo = pagina.conteo_demo()
    assert conteo["demo_ingredientes"] == "40"
    assert conteo["demo_urgentes"] == "8"


def test_llenar_falla_si_la_plantilla_usa_un_valor_que_no_existe():
    assert pagina.llenar("{{ a }} y {{b}}", {"a": "1", "b": "2"}) == "1 y 2"
    with pytest.raises(KeyError, match="falta"):
        pagina.llenar("{{ falta }}", {})


def test_el_historial_separa_el_numero_de_pr_y_escapa_el_texto():
    texto = (
        "da90ce3\t2026-11-24\tdocs: Análisis (#48)\n"
        "d343f0b\t2026-11-15\tInitial commit\n"
        "abc1234\t2026-11-20\tfix: <script> en el asunto (#7)\n"
    )
    cambios = pagina.parsear_historial(texto)
    assert [c["pr"] for c in cambios] == ["48", "", "7"]
    assert cambios[0]["asunto"] == "docs: Análisis"

    tabla = pagina.tabla_historial(cambios)
    assert "/pull/48" in tabla and "/commit/d343f0b" in tabla
    assert "<script>" not in tabla and "&lt;script&gt;" in tabla


@pytest.mark.parametrize(("x", "esperado"), [(1149.684, "1,149.7"), (-29.0, "−29.0")])
def test_formato_de_numeros(x, esperado):
    assert pagina.num(x) == esperado


@pytest.fixture(scope="module")
def visor():
    return pagina.datos_visor()


def test_el_visor_da_la_misma_merma_que_la_corrida_guardada(visor):
    filas = {
        (f["escenario"], f["dias"], f["semilla"]): f
        for f in pagina.leer(pagina.RESULTADOS / "simulacion.csv")
    }
    assert [e["id"] for e in visor["escenarios"]] == list(simular.ESCENARIOS)
    for e in visor["escenarios"]:
        fila = filas[(e["id"], str(pagina.DIAS_VISOR), str(pagina.SEMILLA_VISOR))]
        for lado in ("A", "B"):
            assert len(e[lado]) == pagina.DIAS_VISOR
            total = sum(sum(d["merma"]) for d in e[lado])
            assert total == pytest.approx(float(fila[f"merma_{lado.lower()}_kg"]), abs=0.01)


def test_el_inventario_del_visor_se_conserva_dia_con_dia(visor):
    for e in visor["escenarios"]:
        for lado in ("A", "B"):
            dias = e[lado]
            for hoy, manana in zip(dias, dias[1:], strict=False):
                for i, kg in enumerate(manana["stock"]):
                    esperado = hoy["stock"][i] - hoy["consumo"][i] - hoy["merma"][i]
                    assert kg == pytest.approx(max(esperado, 0.0), abs=0.002)
        assert all(not d["menu"] for d in e["A"])  # A nunca tiene menú del día


def test_la_pagina_trae_el_visor_con_sus_datos(sitio):
    salida, html = sitio
    assert (salida / "visor.js").is_file()
    m = re.search(r'<script id="datos-visor" type="application/json">(.*?)</script>', html, re.S)
    datos = json.loads(m.group(1))
    assert len(datos["fechas"]) == pagina.DIAS_VISOR
    assert {e["nombre"] for e in datos["escenarios"]} == set(simular.NOMBRES.values())


def test_el_json_no_cierra_el_script_antes_de_tiempo():
    texto = pagina.json_en_html({"nombre": "</script><b>"})
    assert "</" not in texto
    assert json.loads(texto) == {"nombre": "</script><b>"}
