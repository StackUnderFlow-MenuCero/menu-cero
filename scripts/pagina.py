"""Construye la página web pública del proyecto (#49).

Llena la plantilla de ``pagina/`` con las cifras, tablas y gráficas de
``resultados/``, los conteos de ``data/demo`` y el historial de ``main``. El
resultado es un sitio estático que el workflow ``pagina.yml`` publica en GitHub
Pages cada vez que algo entra a ``main``. Así, cuando se regeneran los
resultados (por ejemplo, con el voraz principal), la página se actualiza sola.

También arma ``simulador.html`` (#51): el catálogo de ``data/catalogo.json``,
los restaurantes de ejemplo y ``py/menucero-web.zip``, que lleva ``src/menucero``,
el prototipo v0 y ``scripts/simulador_web.py`` para correrlos en el navegador con
Pyodide. Como el paquete se arma con lo que hay en ``main``, el simulador usa
el voraz que esté ahí (hoy, el principal de #20; el v0 queda de respaldo).

Uso, desde la raíz del repositorio::

    uv run python scripts/pagina.py                 # escribe _site/
    uv run python -m http.server -d _site 8000      # http://localhost:8000

La comparación contra la fuerza bruta (#24, #27) se arma con
``resultados/calidad.csv`` y ``resultados/benchmark.csv`` en cuanto existan;
mientras no estén, la página dice que está en desarrollo. Su formato está en
``docs/formato_resultados.md``.

Los textos están en ``pagina/plantilla.html``. Cada ``{{ nombre }}`` se
reemplaza con un valor calculado aquí; si la plantilla usa un nombre que no
existe, la construcción falla en lugar de publicar la marca sin llenar.
"""

from __future__ import annotations

import argparse
import csv
import html
import importlib.metadata
import json
import re
import shutil
import subprocess
import sys
import zipfile
from collections.abc import Iterable, Sequence
from datetime import date, timedelta
from math import sqrt
from pathlib import Path

import simulador_web
import simular
from generar_demo import HOY_DEMO
from menucero.simulacion import voraz_por_omision

RAIZ = simular.RAIZ
PLANTILLA = RAIZ / "pagina" / "plantilla.html"
ESTILO = RAIZ / "pagina" / "estilo.css"
VISOR = RAIZ / "pagina" / "visor.js"
SITIO_JS = RAIZ / "pagina" / "sitio.js"
VISOR_HTML = RAIZ / "pagina" / "visor.html"
SIMULADOR = RAIZ / "pagina" / "simulador.html"
SIMULADOR_JS = RAIZ / "pagina" / "simulador.js"
CATALOGO = RAIZ / "data" / "catalogo.json"
PAQUETE = "py/menucero-web.zip"
PYODIDE = "0.29.5"
PYODIDE_PYTHON = "3.13"  # la de Pyodide 0.29, la misma del proyecto
RESULTADOS = RAIZ / "resultados"
DEMO = RAIZ / "data" / "demo"
REPO = "https://github.com/StackUnderFlow-MenuCero/menu-cero"
FIGURAS = ("merma_a_vs_b.png", "desperdicio_evitado.png", "sensibilidad_venta.png")
DESCARGAS = ("simulacion.csv", "resumen.csv", "sensibilidad_venta.csv")
T95 = {30: 2.045}  # t de Student al 95 % según el número de corridas
MARCA = re.compile(r"\{\{\s*(\w+)\s*\}\}")
PR = re.compile(r"\s*\(#(\d+)\)$")
SEMILLA_VISOR = 1
DIAS_VISOR = 7
DESCRIPCIONES = {
    "normal": "Una semana de clases con la demanda estimada.",
    "examenes": "Semana de exámenes: la demanda baja al 80 %.",
    "vacaciones": "Vacaciones: la demanda baja al 25 % con el mismo inventario.",
    "alta_caducidad": "Regreso de un puente: varios ingredientes ya caducaron o están por caducar.",
}

# Voraz contra fuerza bruta: el formato está en docs/formato_resultados.md.
CALIDAD = "calidad.csv"  # #24
BENCHMARK = "benchmark.csv"  # #27
COLUMNAS_CALIDAD = (
    "instancia",
    "semilla",
    "n",
    "m",
    "valor_voraz",
    "valor_optimo",
    "tiempo_voraz_ms",
    "tiempo_fuerza_bruta_ms",
)
COLUMNAS_BENCHMARK = (
    "algoritmo",
    "n",
    "m",
    "mediana_ms",
    "p25_ms",
    "p75_ms",
    "pico_kib",
    "extrapolado",
    "cpu",
    "python",
)
ALGORITMOS = ("voraz", "fuerza_bruta")
FIGURAS_FB = {  # nombre: (texto alternativo, pie de figura)
    "tiempo_vs_n.png": (
        "Gráfica del tiempo del voraz según el número de ingredientes, con la curva n log n de "
        "referencia. Los valores están en la Tabla 6.",
        "Tiempo del voraz contra el número de ingredientes, con la curva <var>n</var> log "
        "<var>n</var> de referencia.",
    ),
    "ram_vs_n.png": (
        "Gráfica del pico de memoria del voraz según el número de ingredientes. Los valores están "
        "en la Tabla 6.",
        "Pico de memoria del voraz contra el número de ingredientes.",
    ),
    "voraz_vs_fuerza_bruta.png": (
        "Gráfica en escala logarítmica del tiempo del voraz y de la fuerza bruta según el número "
        "de recetas. Los valores están en la Tabla 7.",
        "Tiempo del voraz y de la fuerza bruta, en escala logarítmica.",
    ),
}
FB_CALIDAD = RAIZ / "pagina" / "fuerza_bruta_calidad.html"
FB_EFICIENCIA = RAIZ / "pagina" / "fuerza_bruta_eficiencia.html"
FB_PENDIENTE_CALIDAD = """<div class="pendiente">
        <p class="estado proceso">En desarrollo · <a href="{{ repo }}/issues/24">#24</a></p>
        <h4>Calidad</h4>
        <p>Qué tan cerca del óptimo queda el voraz en instancias pequeñas.
        Se agrega aquí cuando estén sus resultados.</p>
      </div>"""
FB_PENDIENTE_EFICIENCIA = """<div class="pendiente">
        <p class="estado proceso">En desarrollo · <a href="{{ repo }}/issues/27">#27</a></p>
        <h4>Eficiencia</h4>
        <p>Tiempo y memoria con 20, 100, 500 y 1000 ingredientes.
        Se agrega aquí cuando estén sus resultados.</p>
      </div>"""


def leer(ruta: Path) -> list[dict[str, str]]:
    with open(ruta, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def llenar(plantilla: str, valores: dict[str, str]) -> str:
    """Reemplaza cada ``{{ nombre }}``; falla si falta alguno."""

    def valor(m: re.Match[str]) -> str:
        nombre = m.group(1)
        if nombre not in valores:
            raise KeyError(f"La plantilla usa {{{{ {nombre} }}}} y no hay un valor para él")
        return valores[nombre]

    return MARCA.sub(valor, plantilla)


# --- formato -------------------------------------------------------------------


def num(x: float, decimales: int = 1) -> str:
    """Número con separador de miles y signo menos tipográfico."""
    return f"{x:,.{decimales}f}".replace("-", "−")


def pm(prom: str | float, de: str | float, decimales: int = 2) -> str:
    return f"{num(float(prom), decimales)} ± {num(float(de), decimales)}"


def tabla(columnas: Sequence[str], filas: Iterable[Sequence[str]], numericas: int) -> str:
    """Tabla HTML; las últimas ``numericas`` columnas van alineadas a la derecha."""
    primeras = len(columnas) - numericas

    def celdas(valores: Sequence[str], etiqueta: str) -> str:
        return "".join(
            f'<{etiqueta} class="num">{v}</{etiqueta}>'
            if k >= primeras
            else f"<{etiqueta}>{v}</{etiqueta}>"
            for k, v in enumerate(valores)
        )

    cuerpo = "\n".join(f"      <tr>{celdas(f, 'td')}</tr>" for f in filas)
    return (
        '<div class="tabla">\n  <table>\n'
        f"    <thead><tr>{celdas(columnas, 'th')}</tr></thead>\n"
        f"    <tbody>\n{cuerpo}\n    </tbody>\n  </table>\n</div>"
    )


def _orden(resumen: list[dict], dias: str | None = None) -> list[dict]:
    """Filas en el orden de los escenarios de ``simular`` (y de un horizonte, si se da)."""
    filas = [r for r in resumen if dias is None or r["dias"] == dias]
    return sorted(filas, key=lambda r: (int(r["dias"]), simular.ESCENARIOS.index(r["escenario"])))


# --- tablas --------------------------------------------------------------------


def tabla_merma(resumen: list[dict]) -> str:
    filas = []
    for r in _orden(resumen):
        prom, de = float(r["desperdicio_evitado_pct_prom"]), float(r["desperdicio_evitado_pct_de"])
        evitado = pm(prom, de, 1)
        t = T95.get(int(r["corridas"]))
        if t is not None:
            margen = t * de / sqrt(int(r["corridas"]))
            evitado += f" [{num(prom - margen)}, {num(prom + margen)}]"
        filas.append(
            [
                simular.NOMBRES[r["escenario"]],
                r["dias"],
                pm(r["merma_a_kg_prom"], r["merma_a_kg_de"]),
                pm(r["merma_b_kg_prom"], r["merma_b_kg_de"]),
                evitado,
                pm(r["costo_ahorrado_prom"], r["costo_ahorrado_de"]),
            ]
        )
    columnas = [
        "Escenario",
        "Días",
        "Merma A (kg)",
        "Merma B (kg)",
        "Desperdicio evitado (%) [IC 95 %]",
        "Costo ahorrado ($)",
    ]
    return tabla(columnas, filas, numericas=5)


def tabla_urgentes(resumen: list[dict], simulacion: list[dict]) -> str:
    urgentes = {(f["escenario"], f["dias"]): float(f["urgentes_kg"]) for f in simulacion}
    filas = []
    for r in _orden(resumen, str(simular.DIAS_SENSIBILIDAD)):
        a, b = float(r["perdida_urgentes_a_pct_prom"]), float(r["perdida_urgentes_b_pct_prom"])
        filas.append(
            [
                simular.NOMBRES[r["escenario"]],
                num(urgentes[(r["escenario"], r["dias"])], 2),
                pm(a, r["perdida_urgentes_a_pct_de"], 1),
                pm(b, r["perdida_urgentes_b_pct_de"], 1),
                num(b - a),
            ]
        )
    columnas = [
        "Escenario",
        "Kg urgentes",
        "Se pierde en A (%)",
        "Se pierde en B (%)",
        "Diferencia (puntos)",
    ]
    return tabla(columnas, filas, numericas=4)


def tabla_no_atendidas(resumen: list[dict]) -> str:
    filas = []
    for r in _orden(resumen, str(simular.DIAS_SENSIBILIDAD)):
        # La diferencia sale de los valores tal como se muestran (1 decimal).
        a, b = round(float(r["no_atendidas_a_prom"]), 1), round(float(r["no_atendidas_b_prom"]), 1)
        d = round(b - a, 1)
        diferencia = "0" if d == 0 else f"{'+' if d > 0 else ''}{num(d)} ({num(100 * d / a)} %)"
        filas.append([simular.NOMBRES[r["escenario"]], num(a), num(b), diferencia])
    columnas = ["Escenario", "No atendidas en A", "No atendidas en B", "Diferencia"]
    return tabla(columnas, filas, numericas=3)


def tabla_sensibilidad(sensibilidad: list[dict]) -> str:
    resumen = simular.resumir(sensibilidad, ("escenario", "venta"))
    resumen.sort(key=lambda r: (simular.ESCENARIOS.index(r["escenario"]), -float(r["venta"])))
    filas = [
        [
            simular.NOMBRES[r["escenario"]],
            f"{float(r['venta']) * 100:.0f} %",
            pm(r["desperdicio_evitado_pct_prom"], r["desperdicio_evitado_pct_de"], 1)
            + f" [{num(r['desperdicio_evitado_pct_min'])}, "
            f"{num(r['desperdicio_evitado_pct_max'])}]",
            num(r["sobrantes_menu_dia_b_prom"]),
        ]
        for r in resumen
    ]
    columnas = [
        "Escenario",
        "Se vende",
        "Desperdicio evitado (%) [mín, máx]",
        "Porciones sobrantes de B",
    ]
    return tabla(columnas, filas, numericas=3)


# --- cifras del texto ----------------------------------------------------------


def _b_gana(filas: Iterable[dict]) -> tuple[int, int]:
    filas = list(filas)
    return sum(float(f["merma_b_kg"]) < float(f["merma_a_kg"]) for f in filas), len(filas)


def cifras(simulacion: list[dict], resumen: list[dict], sensibilidad: list[dict]) -> dict:
    """Los números que el texto de la página cita, calculados de ``resultados/``."""
    gana, pares = _b_gana(simulacion)
    evitado = [float(f["desperdicio_evitado_pct"]) for f in simulacion]
    promedios = [float(r["desperdicio_evitado_pct_prom"]) for r in resumen]
    ahorros = [float(r["costo_ahorrado_prom"]) for r in resumen]
    demo = next(
        r
        for r in resumen
        if r["escenario"] == "normal" and r["dias"] == str(simular.DIAS_SENSIBILIDAD)
    )
    urgentes = next(f for f in simulacion if f["escenario"] == "normal")
    valores = {
        "voraz": html.escape(simulacion[0]["voraz"]),
        "semillas": str(len({f["semilla"] for f in simulacion})),
        "escenarios": str(len({f["escenario"] for f in simulacion})),
        "horizontes": " y ".join(sorted({f["dias"] for f in simulacion}, key=int)),
        "pares": str(pares),
        "pares_b_menor": str(gana),
        "evitado_prom_min": f"{min(promedios):.0f}",
        "evitado_prom_max": f"{max(promedios):.0f}",
        "evitado_min": num(min(evitado)),
        "evitado_max": num(max(evitado)),
        "ahorro_min": f"${min(ahorros):,.0f}",
        "ahorro_max": f"${max(ahorros):,.0f}",
        "urgentes_kg": num(float(urgentes["urgentes_kg"])),
        "urgentes_a": num(float(demo["perdida_urgentes_a_pct_prom"])),
        "urgentes_b": num(float(demo["perdida_urgentes_b_pct_prom"])),
    }
    for venta in simular.VENTAS:
        g, n = _b_gana(f for f in sensibilidad if float(f["venta"]) == venta)
        valores[f"venta_{venta * 100:.0f}"] = f"{g} de {n}"
    return valores


def conteo_demo(carpeta: Path = DEMO, hoy: date = HOY_DEMO) -> dict[str, str]:
    """Ingredientes, recetas e ingredientes que vencen hoy o mañana en la demostración."""
    inventario = leer(carpeta / "inventario.csv")
    manana = hoy + timedelta(days=1)
    urgentes = [f for f in inventario if hoy <= date.fromisoformat(f["fecha_caducidad"]) <= manana]
    recetas = {f["receta_id"] for f in leer(carpeta / "recetas.csv")}
    return {
        "demo_ingredientes": str(len(inventario)),
        "demo_urgentes": str(len(urgentes)),
        "demo_recetas": str(len(recetas)),
        "demo_fecha": hoy.isoformat(),
    }


# --- voraz contra fuerza bruta (#24, #27) --------------------------------------


def _numero(fila: dict, columna: str, archivo: str, k: int) -> float:
    try:
        return float(fila[columna])
    except ValueError:
        # La fila 1 es el encabezado, como en una hoja de cálculo.
        raise ValueError(
            f"{archivo}, fila {k + 2}, columna {columna}: no es un número («{fila[columna]}»)"
        ) from None


def leer_opcional(ruta: Path, columnas: Sequence[str]) -> list[dict] | None:
    """Filas de un CSV que puede no existir todavía; falla si le faltan columnas."""
    if not ruta.is_file():
        return None
    filas = leer(ruta)
    if not filas:
        raise ValueError(f"{ruta.name}: no tiene filas")
    faltan = [c for c in columnas if c not in filas[0]]
    if faltan:
        raise ValueError(f"{ruta.name}: faltan las columnas {', '.join(faltan)}")
    return filas


def duracion(ms: float) -> str:
    """Tiempo en la unidad que se lee mejor, de milisegundos a años."""
    s = ms / 1000
    if ms < 1:
        return f"{num(ms, 3)} ms"
    if ms < 1000:
        return f"{num(ms, 1)} ms"
    if s < 60:
        return f"{num(s, 1)} s"
    if s < 3600:
        return f"{num(s / 60, 1)} min"
    if s < 86_400:
        return f"{num(s / 3600, 1)} h"
    dias = s / 86_400
    if dias < 365:
        return f"{num(dias, 0)} días"
    anios = dias / 365.25
    if anios < 1e6:
        return f"{num(anios, 0)} años"
    mantisa, exponente = f"{anios:.1e}".split("e")
    return f"{mantisa} × 10<sup>{int(exponente)}</sup> años"


def _mediana(xs: Sequence[float]) -> float:
    xs = sorted(xs)
    mitad = len(xs) // 2
    return xs[mitad] if len(xs) % 2 else (xs[mitad - 1] + xs[mitad]) / 2


def calidad(filas: list[dict]) -> list[dict]:
    """Cada instancia con su cociente V_voraz / V_óptimo; valida que el voraz no gane."""
    instancias = []
    for k, f in enumerate(filas):
        voraz = _numero(f, "valor_voraz", CALIDAD, k)
        optimo = _numero(f, "valor_optimo", CALIDAD, k)
        if voraz > optimo + 1e-6:
            raise ValueError(
                f"{CALIDAD}, fila {k + 2}: el voraz ({voraz}) supera al óptimo ({optimo}); "
                "la fuerza bruta debe usar la misma regla de llenado y la misma V"
            )
        instancias.append(
            {
                "m": int(_numero(f, "m", CALIDAD, k)),
                "cociente": 1.0 if optimo <= 1e-12 else voraz / optimo,
                "voraz_ms": _numero(f, "tiempo_voraz_ms", CALIDAD, k),
                "fuerza_bruta_ms": _numero(f, "tiempo_fuerza_bruta_ms", CALIDAD, k),
            }
        )
    return instancias


def _es_optimo(instancia: dict) -> bool:
    return instancia["cociente"] >= 1 - 1e-9


def tabla_calidad(instancias: list[dict]) -> str:
    filas = []
    for m in sorted({i["m"] for i in instancias}):
        grupo = [i for i in instancias if i["m"] == m]
        cocientes = [i["cociente"] for i in grupo]
        filas.append(
            [
                str(m),
                str(len(grupo)),
                f"{sum(map(_es_optimo, grupo))} de {len(grupo)}",
                num(100 * sum(cocientes) / len(cocientes)),
                num(100 * min(cocientes)),
                duracion(_mediana([i["voraz_ms"] for i in grupo])),
                duracion(_mediana([i["fuerza_bruta_ms"] for i in grupo])),
            ]
        )
    columnas = [
        "Recetas (m)",
        "Instancias",
        "Voraz = óptimo",
        "Promedio (%)",
        "Peor caso (%)",
        "Voraz",
        "Fuerza bruta",
    ]
    return tabla(columnas, filas, numericas=6)


def cifras_calidad(instancias: list[dict]) -> dict[str, str]:
    cocientes = [i["cociente"] for i in instancias]
    m_max = max(i["m"] for i in instancias)
    grandes = [i for i in instancias if i["m"] == m_max]
    voraz = _mediana([i["voraz_ms"] for i in grandes])
    veces = _mediana([i["fuerza_bruta_ms"] for i in grandes]) / voraz if voraz > 0 else 0
    return {
        "fb_instancias": str(len(instancias)),
        "fb_optimos": str(sum(map(_es_optimo, instancias))),
        "fb_m_min": str(min(i["m"] for i in instancias)),
        "fb_m_max": str(m_max),
        "fb_cociente_prom": num(100 * sum(cocientes) / len(cocientes)),
        "fb_cociente_min": num(100 * min(cocientes)),
        "fb_veces": num(veces, 0),
    }


def benchmark(filas: list[dict]) -> list[dict]:
    """Filas del benchmark con sus números; valida el algoritmo y la marca de estimado."""
    medidas = []
    for k, f in enumerate(filas):
        if f["algoritmo"] not in ALGORITMOS:
            raise ValueError(
                f"{BENCHMARK}, fila {k + 2}, columna algoritmo: debe ser "
                f"{' o '.join(ALGORITMOS)} («{f['algoritmo']}»)"
            )
        if f["extrapolado"] not in ("0", "1"):
            raise ValueError(
                f"{BENCHMARK}, fila {k + 2}, columna extrapolado: debe ser 0 o 1 "
                f"(«{f['extrapolado']}»)"
            )
        estimado = f["extrapolado"] == "1"
        medidas.append(
            {
                "algoritmo": f["algoritmo"],
                "n": int(_numero(f, "n", BENCHMARK, k)),
                "m": int(_numero(f, "m", BENCHMARK, k)),
                "mediana": _numero(f, "mediana_ms", BENCHMARK, k),
                # Lo estimado no se midió: puede no traer cuartiles ni memoria.
                "p25": None if estimado else _numero(f, "p25_ms", BENCHMARK, k),
                "p75": None if estimado else _numero(f, "p75_ms", BENCHMARK, k),
                "kib": None
                if estimado and not f["pico_kib"]
                else _numero(f, "pico_kib", BENCHMARK, k),
                "estimado": estimado,
                "cpu": f["cpu"],
                "python": f["python"],
            }
        )
    for algoritmo in ALGORITMOS:
        if not any(x["algoritmo"] == algoritmo and not x["estimado"] for x in medidas):
            raise ValueError(f"{BENCHMARK}: no hay mediciones de {algoritmo}")
    return medidas


def _kib(x: float | None) -> str:
    return "—" if x is None else num(x, 0)


def tabla_eficiencia_voraz(medidas: list[dict]) -> str:
    voraz = sorted((x for x in medidas if x["algoritmo"] == "voraz"), key=lambda x: x["n"])
    filas = [
        [
            num(x["n"], 0),
            num(x["m"], 0),
            duracion(x["mediana"])
            + ("" if x["estimado"] else f" [{duracion(x['p25'])}, {duracion(x['p75'])}]"),
            _kib(x["kib"]),
        ]
        for x in voraz
    ]
    columnas = [
        "Ingredientes (n)",
        "Recetas (m)",
        "Tiempo, mediana [p25, p75]",
        "Pico de RAM (KiB)",
    ]
    return tabla(columnas, filas, numericas=3)


def tabla_eficiencia_fuerza_bruta(medidas: list[dict]) -> str:
    fuerza = sorted(
        (x for x in medidas if x["algoritmo"] == "fuerza_bruta"), key=lambda x: (x["m"], x["n"])
    )
    filas = [
        [
            num(x["m"], 0),
            num(x["n"], 0),
            duracion(x["mediana"]),
            _kib(x["kib"]),
            "estimado" if x["estimado"] else "medido",
        ]
        for x in fuerza
    ]
    columnas = [
        "Recetas (m)",
        "Ingredientes (n)",
        "Tiempo (mediana)",
        "Pico de RAM (KiB)",
        "Origen",
    ]
    return tabla(columnas, filas, numericas=4)


def cifras_eficiencia(medidas: list[dict]) -> dict[str, str]:
    voraz = max(
        (x for x in medidas if x["algoritmo"] == "voraz" and not x["estimado"]),
        key=lambda x: x["n"],
    )
    fuerza = [x for x in medidas if x["algoritmo"] == "fuerza_bruta"]
    medida = max((x for x in fuerza if not x["estimado"]), key=lambda x: (x["m"], x["n"]))
    estimadas = [x for x in fuerza if x["estimado"]]
    extrapolacion = ""
    if estimadas:
        lejos = max(estimadas, key=lambda x: (x["m"], x["n"]))
        extrapolacion = (
            f" Al extrapolar, con {num(lejos['m'], 0)} recetas tardaría "
            f"{duracion(lejos['mediana'])}."
        )
    primera = medidas[0]
    return {
        "bm_n_max": num(voraz["n"], 0),
        "bm_voraz_tiempo": duracion(voraz["mediana"]),
        "bm_voraz_kib": _kib(voraz["kib"]),
        "bm_fb_m": num(medida["m"], 0),
        "bm_fb_tiempo": duracion(medida["mediana"]),
        "bm_fb_extrapolacion": extrapolacion,
        "bm_equipo": html.escape(f"{primera['cpu']}, Python {primera['python']}"),
    }


def figuras_fuerza_bruta(resultados: Path) -> str:
    """Las gráficas de #27 que ya existan en ``resultados/``."""
    presentes = [
        (n, alt, pie) for n, (alt, pie) in FIGURAS_FB.items() if (resultados / n).is_file()
    ]
    if not presentes:
        return ""
    figuras = "\n".join(
        f'        <figure>\n          <a href="resultados/{n}"><img src="resultados/{n}" '
        f'alt="{html.escape(alt)}" loading="lazy"></a>\n'
        f"          <figcaption><strong>Figura {4 + k}.</strong> {pie}</figcaption>\n"
        "        </figure>"
        for k, (n, alt, pie) in enumerate(presentes)
    )
    return f'<div class="figuras">\n{figuras}\n      </div>'


def fuerza_bruta(resultados: Path = RESULTADOS) -> dict[str, str]:
    """La comparación contra la fuerza bruta, o el aviso de pendiente si aún no hay datos.

    Lee ``calidad.csv`` (#24) y ``benchmark.csv`` (#27) de ``resultados``; cada
    parte se muestra en cuanto existe su archivo. El formato está en
    ``docs/formato_resultados.md``.
    """
    filas_calidad = leer_opcional(resultados / CALIDAD, COLUMNAS_CALIDAD)
    filas_benchmark = leer_opcional(resultados / BENCHMARK, COLUMNAS_BENCHMARK)
    valores = {"repo": REPO}

    if filas_calidad is None:
        parte_calidad = FB_PENDIENTE_CALIDAD
    else:
        instancias = calidad(filas_calidad)
        valores |= cifras_calidad(instancias) | {"tabla_calidad": tabla_calidad(instancias)}
        parte_calidad = FB_CALIDAD.read_text(encoding="utf-8")

    if filas_benchmark is None:
        parte_eficiencia = FB_PENDIENTE_EFICIENCIA
    else:
        medidas = benchmark(filas_benchmark)
        valores |= cifras_eficiencia(medidas) | {
            "tabla_eficiencia_voraz": tabla_eficiencia_voraz(medidas),
            "tabla_eficiencia_fuerza_bruta": tabla_eficiencia_fuerza_bruta(medidas),
            "figuras_fb": figuras_fuerza_bruta(resultados),
        }
        parte_eficiencia = FB_EFICIENCIA.read_text(encoding="utf-8")

    listo = filas_calidad is not None and filas_benchmark is not None
    enlace = '<a href="{{ repo }}/issues/{n}">#{n}</a>'
    issues = (24, 27) if listo else (24, 27, 29)
    estado = ", ".join(enlace.replace("{n}", str(n)) for n in issues)
    descargas = "".join(
        f' ·\n            <a href="resultados/{archivo}" download>{nombre}</a>'
        for archivo, nombre, filas in (
            (CALIDAD, "Calidad", filas_calidad),
            (BENCHMARK, "Benchmark", filas_benchmark),
        )
        if filas is not None
    )
    return {
        "fb_estado": llenar(
            f'<p class="estado hecho">Implementado · {estado}</p>'
            if listo
            else f'<p class="estado proceso">En desarrollo · {estado}</p>',
            valores,
        ),
        "fb_calidad": llenar(parte_calidad, valores),
        "fb_eficiencia": llenar(parte_eficiencia, valores),
        "descargas_fb": descargas,
    }


def archivos_fuerza_bruta(resultados: Path = RESULTADOS) -> list[str]:
    """Los archivos de #24 y #27 que existen y hay que copiar al sitio."""
    nombres = (CALIDAD, BENCHMARK, *FIGURAS_FB)
    return [n for n in nombres if (resultados / n).is_file()]


# --- evidencias del desarrollo -------------------------------------------------


def parsear_historial(texto: str) -> list[dict[str, str]]:
    """Líneas ``hash<TAB>fecha<TAB>asunto`` de ``git log`` → cambios con su PR."""
    cambios = []
    for linea in texto.strip().splitlines():
        corto, fecha, asunto = linea.split("\t", 2)
        m = PR.search(asunto)
        cambios.append(
            {
                "commit": corto,
                "fecha": fecha,
                "asunto": PR.sub("", asunto),
                "pr": m.group(1) if m else "",
            }
        )
    return cambios


def _git(*args: str) -> str | None:
    try:
        salida = subprocess.run(
            ["git", *args], cwd=RAIZ, capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return salida.stdout


def historial() -> list[dict[str, str]]:
    texto = _git("log", "--first-parent", "--date=short", "--format=%h%x09%ad%x09%s", "HEAD")
    return parsear_historial(texto) if texto else []


def tabla_historial(cambios: list[dict[str, str]]) -> str:
    if not cambios:
        return "<p>El historial no está disponible en esta copia del repositorio.</p>"
    filas = []
    for c in cambios:
        enlace = (
            f'<a href="{REPO}/pull/{c["pr"]}">#{c["pr"]}</a>'
            if c["pr"]
            else f'<a href="{REPO}/commit/{c["commit"]}"><code>{c["commit"]}</code></a>'
        )
        filas.append([c["fecha"], html.escape(c["asunto"]), enlace])
    return tabla(["Fecha", "Cambio", "PR"], filas, numericas=0)


def contar_pruebas() -> int | None:
    """Pruebas que recolecta pytest (sin correrlas)."""
    try:
        salida = subprocess.run(
            # Sin los addopts del proyecto, para que imprima «N tests collected».
            [sys.executable, "-m", "pytest", "-o", "addopts=", "--collect-only", "-q"],
            cwd=RAIZ,
            capture_output=True,
            text=True,
        ).stdout
    except OSError:
        return None
    m = re.search(r"(\d+) tests? collected", salida)
    return int(m.group(1)) if m else None


def evidencias(pruebas: int | None) -> dict[str, str]:
    cambios = historial()
    commit = cambios[0] if cambios else {"commit": "—", "fecha": "—"}
    return {
        "historial": tabla_historial(cambios),
        "cambios": str(len(cambios)),
        "prs": str(sum(1 for c in cambios if c["pr"])),
        "pruebas": str(pruebas) if pruebas is not None else "Todas las",
        "commit": html.escape(commit["commit"]),
        "fecha_commit": html.escape(commit["fecha"]),
    }


# --- visor día por día ---------------------------------------------------------


def datos_visor(
    datos: Path = RAIZ / "data" / "escenarios",
    semilla: int = SEMILLA_VISOR,
    dias: int = DIAS_VISOR,
) -> dict:
    """Una corrida día por día de A y B en cada escenario, con el simulador real.

    Usa la misma configuración que ``simular.correr`` (demanda Poisson con
    ``semilla``), así que el total de merma coincide con esa fila de
    ``resultados/simulacion.csv``.
    """
    generador = voraz_por_omision()
    escenarios = []
    for escenario in simular.ESCENARIOS:
        ingredientes, recetas = simular.leer_escenario(datos / escenario, HOY_DEMO)
        corrida = simulador_web.escenario_visor(
            ingredientes, recetas, HOY_DEMO, dias, semilla, True, generador
        )
        escenarios.append(
            {
                "id": escenario,
                "nombre": simular.NOMBRES[escenario],
                "descripcion": DESCRIPCIONES[escenario],
                **corrida,
            }
        )
    return {
        "semilla": semilla,
        "voraz": simulador_web.nombre_voraz(generador),
        "fechas": [simulador_web.fecha_corta(HOY_DEMO + timedelta(days=t)) for t in range(dias)],
        "escenarios": escenarios,
    }


def json_en_html(datos: dict) -> str:
    """JSON que se puede poner dentro de ``<script>`` sin cerrarlo antes de tiempo."""
    return json.dumps(datos, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


# --- simulador en el navegador (#51) ---------------------------------------------


def catalogo() -> dict:
    datos = json.loads(CATALOGO.read_text(encoding="utf-8"))
    errores = simulador_web.errores_del_catalogo(datos)
    if errores:
        raise ValueError(f"{CATALOGO.name}: " + "; ".join(errores))
    return datos


def paquete_python(destino: Path) -> Path:
    """Zip con lo que el simulador corre en Pyodide, con la estructura del repositorio.

    Lleva todo ``src/menucero`` (así el voraz principal entra solo cuando exista),
    ``prototipo/voraz_v0.py`` en la ruta que espera ``simulacion.py`` y el puente
    ``scripts/simulador_web.py``. ``menucero/__init__.py`` lee su versión de los
    metadatos del paquete, así que también van sus ``METADATA``.
    """
    version = importlib.metadata.version("menucero")
    destino.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        paquete = RAIZ / "src" / "menucero"
        for ruta in sorted(paquete.rglob("*.py")):
            z.write(ruta, (Path("src") / ruta.relative_to(RAIZ / "src")).as_posix())
        z.writestr(
            f"src/menucero-{version}.dist-info/METADATA",
            f"Metadata-Version: 2.1\nName: menucero\nVersion: {version}\n",
        )
        z.write(RAIZ / "prototipo" / "voraz_v0.py", "prototipo/voraz_v0.py")
        z.write(RAIZ / "scripts" / "simulador_web.py", "scripts/simulador_web.py")
    return destino


def valores_simulador() -> dict[str, str]:
    datos = catalogo()
    return {
        "visor": VISOR_HTML.read_text(encoding="utf-8"),
        "catalogo": json_en_html(datos),
        "ejemplos": json_en_html(simulador_web.restaurantes_ejemplo(datos)),
        "paquete": PAQUETE,
        "pyodide": PYODIDE,
        "pyodide_python": PYODIDE_PYTHON,
        "voraz": simulador_web.nombre_voraz(voraz_por_omision()),
        "n_ingredientes": str(len(datos["ingredientes"])),
        "n_recetas": str(sum(len(c["recetas"]) for c in datos["cocinas"].values())),
        "n_cocinas": str(len(datos["cocinas"])),
        "repo": REPO,
    }


# --- construcción --------------------------------------------------------------


def valores(resultados: Path = RESULTADOS, pruebas: int | None = None) -> dict[str, str]:
    simulacion = leer(resultados / "simulacion.csv")
    resumen = leer(resultados / "resumen.csv")
    sensibilidad = leer(resultados / "sensibilidad_venta.csv")
    return {
        "repo": REPO,
        "tabla_merma": tabla_merma(resumen),
        "tabla_urgentes": tabla_urgentes(resumen, simulacion),
        "tabla_no_atendidas": tabla_no_atendidas(resumen),
        "tabla_sensibilidad": tabla_sensibilidad(sensibilidad),
        **cifras(simulacion, resumen, sensibilidad),
        **fuerza_bruta(resultados),
        **conteo_demo(),
        **evidencias(pruebas),
        "datos_visor": json_en_html(datos_visor()),
        "visor": VISOR_HTML.read_text(encoding="utf-8"),
        "semilla_visor": str(SEMILLA_VISOR),
        "dias_visor": str(DIAS_VISOR),
    }


def construir(salida: Path, con_pruebas: bool = True, resultados: Path = RESULTADOS) -> Path:
    """Escribe el sitio en ``salida`` y devuelve la ruta de ``index.html``."""
    pruebas = contar_pruebas() if con_pruebas else None
    pagina = llenar(PLANTILLA.read_text(encoding="utf-8"), valores(resultados, pruebas))

    salida.mkdir(parents=True, exist_ok=True)
    (salida / "resultados").mkdir(exist_ok=True)
    for nombre in (*FIGURAS, *DESCARGAS, *archivos_fuerza_bruta(resultados)):
        shutil.copy2(resultados / nombre, salida / "resultados" / nombre)
    shutil.copy2(ESTILO, salida / "estilo.css")
    shutil.copy2(VISOR, salida / "visor.js")
    shutil.copy2(SIMULADOR_JS, salida / "simulador.js")
    shutil.copy2(SITIO_JS, salida / "sitio.js")
    paquete_python(salida / PAQUETE)
    simulador = llenar(SIMULADOR.read_text(encoding="utf-8"), valores_simulador())
    (salida / "simulador.html").write_text(simulador, encoding="utf-8")
    (salida / ".nojekyll").touch()  # GitHub Pages sirve los archivos tal cual
    indice = salida / "index.html"
    indice.write_text(pagina, encoding="utf-8")
    return indice


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--salida", type=Path, default=RAIZ / "_site", help="carpeta del sitio")
    parser.add_argument(
        "--sin-pruebas", action="store_true", help="no contar las pruebas con pytest"
    )
    args = parser.parse_args(argv)
    print(construir(args.salida, con_pruebas=not args.sin_pruebas))


if __name__ == "__main__":
    main()
