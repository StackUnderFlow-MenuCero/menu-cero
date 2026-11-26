"""Corridas de simulación A contra B en los cuatro escenarios (#28).

Para cada escenario de ``data/escenarios``, cada horizonte (3 y 7 días) y cada
semilla (30 por omisión), simula A (solo menú fijo) y B (menú fijo + menú del
día) con demanda Poisson y escribe en ``resultados/``:

- ``simulacion.csv``: una fila por escenario, horizonte y semilla.
- ``resumen.csv`` y ``resumen.md``: promedio, desviación estándar, mínimo y
  máximo por escenario y horizonte.
- ``merma_a_vs_b.png``: merma promedio de A y B por escenario.
- ``desperdicio_evitado.png``: distribución del % de desperdicio evitado.
- ``sensibilidad_venta.csv``: prueba del supuesto de venta (#31). Con 3 días,
  el menú del día se prepara completo, se vende el 100, 75 o 50 % de su demanda
  estimada y lo que sobra se tira como merma.

Uso, desde la raíz del repositorio::

    uv run python scripts/simular.py

Siempre da los mismos números con las mismas semillas y los mismos datos.
"""

from __future__ import annotations

import argparse
import csv
import statistics
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from generar_demo import HOY_DEMO
from menucero.simulacion import simular, voraz_por_omision

RAIZ = Path(__file__).resolve().parents[1]
ESCENARIOS = ("normal", "examenes", "vacaciones", "alta_caducidad")
NOMBRES = {
    "normal": "Normal",
    "examenes": "Exámenes",
    "vacaciones": "Vacaciones",
    "alta_caducidad": "Alta caducidad",
}
HORIZONTES = (3, 7)
VENTAS = (1.0, 0.75, 0.5)
DIAS_SENSIBILIDAD = 3
COLUMNAS = [
    "escenario",
    "dias",
    "semilla",
    "voraz",
    "inventario_kg",
    "urgentes_kg",
    "merma_a_kg",
    "merma_b_kg",
    "merma_a_costo",
    "merma_b_costo",
    "merma_urgentes_a_kg",
    "merma_urgentes_b_kg",
    "perdida_urgentes_a_pct",
    "perdida_urgentes_b_pct",
    "perdida_inventario_a_pct",
    "perdida_inventario_b_pct",
    "desperdicio_evitado_pct",
    "costo_ahorrado",
    "no_atendidas_a",
    "no_atendidas_b",
    "porciones_menu_dia_b",
    "sobrantes_menu_dia_b",
]
METRICAS = [
    "merma_a_kg",
    "merma_b_kg",
    "perdida_urgentes_a_pct",
    "perdida_urgentes_b_pct",
    "perdida_inventario_a_pct",
    "perdida_inventario_b_pct",
    "desperdicio_evitado_pct",
    "costo_ahorrado",
    "no_atendidas_a",
    "no_atendidas_b",
    "sobrantes_menu_dia_b",
]

# Colores de la paleta categórica de referencia (A = 1, B = 2) y tinta de texto.
COLOR_A, COLOR_B = "#2a78d6", "#eb6834"
COLORES_ESCENARIO = dict(zip(ESCENARIOS, ("#2a78d6", "#eb6834", "#1baf7a", "#eda100"), strict=True))
MARCAS_ESCENARIO = dict(zip(ESCENARIOS, ("o", "s", "D", "^"), strict=True))
FONDO, TINTA, TINTA_2, REJILLA = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"


# Mismos campos que modelos.py en el contrato (#11). Solo se usan si la carga
# validada (#13) todavía no está en main.
@dataclass(frozen=True)
class Ingrediente:
    id: str
    nombre: str
    cantidad_kg: float
    fecha_caducidad: date
    costo_kg: float


@dataclass(frozen=True)
class Receta:
    id: str
    platillo: str
    tipo: str
    ingredientes: dict[str, float] = field(default_factory=dict)
    demanda_fija: int = 0
    demanda_menu_dia: int = 0


def leer_escenario(carpeta: Path, hoy: date) -> tuple[list, list]:
    """Inventario y recetas de ``carpeta``: con ``cargar_datos`` (#13) si ya existe."""
    archivos = [carpeta / f"{n}.csv" for n in ("inventario", "recetas", "demanda")]
    try:
        from menucero.carga import cargar_datos
    except ImportError:
        return _leer_sin_validar(*archivos)
    resultado = cargar_datos(*archivos, hoy=hoy)
    if resultado.errores:
        raise ValueError(f"{carpeta}: {resultado.errores[0]}")
    return resultado.ingredientes, resultado.recetas


def _leer_sin_validar(inventario: Path, recetas: Path, demanda: Path) -> tuple[list, list]:
    with open(inventario, encoding="utf-8-sig", newline="") as f:
        ingredientes = [
            Ingrediente(
                r["ingrediente_id"],
                r["nombre"],
                float(r["cantidad_kg"]),
                date.fromisoformat(r["fecha_caducidad"]),
                float(r["costo_kg"]),
            )
            for r in csv.DictReader(f)
        ]
    filas: dict[str, dict] = {}
    with open(recetas, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            fila = filas.setdefault(
                r["receta_id"], {"platillo": r["platillo"], "tipo": r["tipo"], "kg": {}}
            )
            fila["kg"][r["ingrediente_id"]] = float(r["kg_por_porcion"])
    with open(demanda, encoding="utf-8-sig", newline="") as f:
        dem = {r["receta_id"]: r for r in csv.DictReader(f)}
    return ingredientes, [
        Receta(
            j,
            f["platillo"],
            f["tipo"],
            f["kg"],
            int(dem[j]["demanda_fija"]),
            int(dem[j]["demanda_menu_dia"]),
        )
        for j, f in filas.items()
    ]


def desperdicio_evitado(merma_a: dict[str, float], merma_b: dict[str, float]) -> float | None:
    """``100 × (Σa − Σb) / Σa``; ``None`` si en A no hubo merma (fórmula de #22)."""
    total_a = sum(merma_a.values())
    if total_a <= 0:
        return None
    return 100 * (total_a - sum(merma_b.values())) / total_a


def costo_ahorrado(
    merma_a: dict[str, float], merma_b: dict[str, float], costos: dict[str, float]
) -> float:
    """``Σ costo_i × (a_i − b_i)``; lo que falta en un diccionario cuenta como 0 (#22)."""
    ids = set(merma_a) | set(merma_b)
    return sum(costos.get(i, 0.0) * (merma_a.get(i, 0.0) - merma_b.get(i, 0.0)) for i in ids)


def nombre_voraz() -> str:
    from menucero import voraz

    return "voraz (#20)" if hasattr(voraz, "generar_menu") else "v0 (prototipo)"


def correr(
    datos: Path,
    escenarios: Sequence[str],
    horizontes: Sequence[int],
    semillas: Sequence[int],
    venta: float = 1.0,
    sobrante_es_merma: bool = False,
) -> list[dict]:
    """Una fila por escenario, horizonte y semilla con A y B.

    Los ingredientes *urgentes* son los que vencen hoy o mañana (0 o 1 días): los
    «8 que vencen en menos de 48 horas» de la demostración.
    """
    generador = voraz_por_omision()
    voraz = nombre_voraz()
    filas = []
    for escenario in escenarios:
        ingredientes, recetas = leer_escenario(datos / escenario, HOY_DEMO)
        costos = {ing.id: ing.costo_kg for ing in ingredientes}
        inventario_kg = sum(ing.cantidad_kg for ing in ingredientes)
        urgentes = {
            ing.id: ing.cantidad_kg
            for ing in ingredientes
            if 0 <= (ing.fecha_caducidad - HOY_DEMO).days <= 1
        }
        urgentes_kg = sum(urgentes.values())
        for dias in horizontes:
            for semilla in semillas:
                comun = {"dias": dias, "semilla": semilla, "ruido": True}
                a = simular(ingredientes, recetas, HOY_DEMO, escenario="A", **comun)
                b = simular(
                    ingredientes,
                    recetas,
                    HOY_DEMO,
                    escenario="B",
                    generador=generador,
                    venta=venta,
                    sobrante_es_merma=sobrante_es_merma,
                    **comun,
                )
                evitado = desperdicio_evitado(a.merma_kg, b.merma_kg)
                urg_a = sum(a.merma_kg[i] for i in urgentes)
                urg_b = sum(b.merma_kg[i] for i in urgentes)
                filas.append(
                    {
                        "escenario": escenario,
                        "dias": dias,
                        "semilla": semilla,
                        "voraz": voraz,
                        "inventario_kg": round(inventario_kg, 4),
                        "urgentes_kg": round(urgentes_kg, 4),
                        "merma_a_kg": round(a.merma_total_kg, 4),
                        "merma_b_kg": round(b.merma_total_kg, 4),
                        "merma_a_costo": round(a.merma_costo, 2),
                        "merma_b_costo": round(b.merma_costo, 2),
                        "merma_urgentes_a_kg": round(urg_a, 4),
                        "merma_urgentes_b_kg": round(urg_b, 4),
                        "perdida_urgentes_a_pct": _pct(urg_a, urgentes_kg),
                        "perdida_urgentes_b_pct": _pct(urg_b, urgentes_kg),
                        "perdida_inventario_a_pct": _pct(a.merma_total_kg, inventario_kg),
                        "perdida_inventario_b_pct": _pct(b.merma_total_kg, inventario_kg),
                        "desperdicio_evitado_pct": "" if evitado is None else round(evitado, 2),
                        "costo_ahorrado": round(costo_ahorrado(a.merma_kg, b.merma_kg, costos), 2),
                        "no_atendidas_a": a.porciones_no_atendidas,
                        "no_atendidas_b": b.porciones_no_atendidas,
                        "porciones_menu_dia_b": sum(
                            sum(r["porciones_menu_dia"].values()) for r in b.consumo_diario
                        ),
                        "sobrantes_menu_dia_b": sum(
                            sum(r["sobrantes_menu_dia"].values()) for r in b.consumo_diario
                        ),
                    }
                )
    return filas


def _pct(parte: float, total: float) -> float | str:
    return round(100 * parte / total, 2) if total > 0 else ""


def sensibilidad(datos: Path, semillas: Sequence[int]) -> list[dict]:
    """El menú del día se prepara completo y se vende el 100, 75 o 50 % de lo estimado."""
    filas = []
    for venta in VENTAS:
        for fila in correr(
            datos, ESCENARIOS, [DIAS_SENSIBILIDAD], semillas, venta=venta, sobrante_es_merma=True
        ):
            filas.append({"venta": venta, **fila})
    return filas


def resumir(filas: list[dict], llaves: Sequence[str] = ("escenario", "dias")) -> list[dict]:
    """Promedio, desviación estándar, mínimo y máximo por escenario y horizonte."""
    grupos: dict[tuple, list[dict]] = {}
    for f in filas:
        grupos.setdefault(tuple(f[k] for k in llaves), []).append(f)
    resumen = []
    for clave, grupo in grupos.items():
        fila = {**dict(zip(llaves, clave, strict=True)), "corridas": len(grupo)}
        for m in METRICAS:
            valores = [float(f[m]) for f in grupo if f[m] != ""]
            fila[f"{m}_prom"] = round(statistics.fmean(valores), 2)
            fila[f"{m}_de"] = round(statistics.stdev(valores), 2) if len(valores) > 1 else 0.0
            fila[f"{m}_min"] = round(min(valores), 2)
            fila[f"{m}_max"] = round(max(valores), 2)
        resumen.append(fila)
    return resumen


def tabla_markdown(resumen: list[dict], voraz: str, semillas: int) -> str:
    lineas = [
        f"# Simulación A vs B ({semillas} semillas por escenario, voraz: {voraz})",
        "",
        f"Fecha de inicio {HOY_DEMO.isoformat()}, demanda Poisson, sin reposición. "
        "Promedio ± desviación estándar; entre corchetes, mínimo y máximo.",
        "",
        "| Escenario | Días | Merma A (kg) | Merma B (kg) | Desperdicio evitado (%) "
        "| Costo ahorrado ($) | No atendidas A | No atendidas B |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in sorted(resumen, key=lambda r: (r["dias"], ESCENARIOS.index(r["escenario"]))):
        ev = (
            f"{r['desperdicio_evitado_pct_prom']:.1f} ± {r['desperdicio_evitado_pct_de']:.1f} "
            f"[{r['desperdicio_evitado_pct_min']:.1f}, {r['desperdicio_evitado_pct_max']:.1f}]"
        )
        lineas.append(
            f"| {NOMBRES[r['escenario']]} | {r['dias']} "
            f"| {r['merma_a_kg_prom']:.2f} ± {r['merma_a_kg_de']:.2f} "
            f"| {r['merma_b_kg_prom']:.2f} ± {r['merma_b_kg_de']:.2f} "
            f"| {ev} "
            f"| {r['costo_ahorrado_prom']:,.2f} ± {r['costo_ahorrado_de']:,.2f} "
            f"| {r['no_atendidas_a_prom']:.1f} | {r['no_atendidas_b_prom']:.1f} |"
        )

    lineas += [
        "",
        "## Pérdida de los ingredientes urgentes y del inventario",
        "",
        "Urgentes: los que vencen hoy o mañana al empezar. Porcentaje de sus kg "
        "iniciales que terminan como merma.",
        "",
        "| Escenario | Días | Urgentes A (%) | Urgentes B (%) | Inventario A (%) "
        "| Inventario B (%) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in sorted(resumen, key=lambda r: (r["dias"], ESCENARIOS.index(r["escenario"]))):
        lineas.append(
            f"| {NOMBRES[r['escenario']]} | {r['dias']} "
            f"| {r['perdida_urgentes_a_pct_prom']:.1f} ± {r['perdida_urgentes_a_pct_de']:.1f} "
            f"| {r['perdida_urgentes_b_pct_prom']:.1f} ± {r['perdida_urgentes_b_pct_de']:.1f} "
            f"| {r['perdida_inventario_a_pct_prom']:.1f} "
            f"| {r['perdida_inventario_b_pct_prom']:.1f} |"
        )
    return "\n".join(lineas) + "\n"


def tabla_sensibilidad(resumen: list[dict]) -> str:
    lineas = [
        "",
        f"## Sensibilidad al supuesto de venta ({DIAS_SENSIBILIDAD} días)",
        "",
        "El menú del día se prepara completo al inicio del día; se vende la fracción "
        "indicada de su demanda estimada y lo que sobra se tira como merma.",
        "",
        "| Escenario | Venta | Merma A (kg) | Merma B (kg) | Desperdicio evitado (%) "
        "| Porciones sobrantes B |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in sorted(resumen, key=lambda r: (ESCENARIOS.index(r["escenario"]), -r["venta"])):
        lineas.append(
            f"| {NOMBRES[r['escenario']]} | {r['venta']:.0%} "
            f"| {r['merma_a_kg_prom']:.2f} | {r['merma_b_kg_prom']:.2f} "
            f"| {r['desperdicio_evitado_pct_prom']:.1f} ± {r['desperdicio_evitado_pct_de']:.1f} "
            f"[{r['desperdicio_evitado_pct_min']:.1f}, {r['desperdicio_evitado_pct_max']:.1f}] "
            f"| {r['sobrantes_menu_dia_b_prom']:.1f} |"
        )
    return "\n".join(lineas) + "\n"


def escribir_csv(ruta: Path, filas: list[dict], columnas: list[str]) -> None:
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=columnas, lineterminator="\n")
        escritor.writeheader()
        escritor.writerows(filas)


def graficar(filas: list[dict], resumen: list[dict], salida: Path) -> None:
    plt = _pyplot()
    horizontes = sorted({r["dias"] for r in resumen})
    escenarios = [e for e in ESCENARIOS if any(r["escenario"] == e for r in resumen)]
    por_clave = {(r["escenario"], r["dias"]): r for r in resumen}
    x = range(len(escenarios))
    ancho = 0.36

    # 1. Merma promedio de A y B por escenario, un panel por horizonte.
    fig, ejes = plt.subplots(
        1, len(horizontes), figsize=(5.2 * len(horizontes), 4.2), sharey=True, squeeze=False
    )
    fig.patch.set_facecolor(FONDO)
    for eje, dias in zip(ejes[0], horizontes, strict=True):
        _estilo(eje)
        for desplazamiento, clave, color, nombre in (
            (-ancho / 2 - 0.01, "merma_a_kg", COLOR_A, "A · solo menú fijo"),
            (ancho / 2 + 0.01, "merma_b_kg", COLOR_B, "B · fijo + menú del día"),
        ):
            prom = [por_clave[(e, dias)][f"{clave}_prom"] for e in escenarios]
            de = [por_clave[(e, dias)][f"{clave}_de"] for e in escenarios]
            barras = eje.bar(
                [i + desplazamiento for i in x],
                prom,
                ancho,
                yerr=de,
                color=color,
                label=nombre,
                error_kw={"ecolor": TINTA_2, "elinewidth": 1, "capsize": 3},
                zorder=2,
            )
            eje.bar_label(barras, fmt="%.1f", padding=3, fontsize=8, color=TINTA_2)
        eje.set_xticks(list(x), [NOMBRES[e] for e in escenarios])
        eje.set_title(f"{dias} días", fontsize=10, color=TINTA, loc="left")
    ejes[0][0].set_ylabel("Merma promedio (kg)")
    manejadores, etiquetas = ejes[0][0].get_legend_handles_labels()
    fig.legend(manejadores, etiquetas, loc="upper right", ncol=2, frameon=False)
    fig.suptitle(
        "Merma con solo el menú fijo (A) y con el menú del día (B)",
        x=0.01,
        ha="left",
        fontsize=12,
        color=TINTA,
    )
    fig.text(
        0.01,
        0.005,
        f"Promedio de {len({f['semilla'] for f in filas})} semillas; la línea es ± 1 desviación "
        "estándar.",
        fontsize=8,
        color=TINTA_2,
    )
    fig.tight_layout(rect=(0, 0.03, 1, 0.93))
    fig.savefig(salida / "merma_a_vs_b.png", dpi=150, facecolor=FONDO, metadata={"Software": None})
    plt.close(fig)

    # 2. Distribución del % de desperdicio evitado.
    fig, ejes = plt.subplots(
        1, len(horizontes), figsize=(5.2 * len(horizontes), 4.2), sharey=True, squeeze=False
    )
    fig.patch.set_facecolor(FONDO)
    for eje, dias in zip(ejes[0], horizontes, strict=True):
        _estilo(eje)
        datos = [
            [
                float(f["desperdicio_evitado_pct"])
                for f in filas
                if f["escenario"] == e and f["dias"] == dias and f["desperdicio_evitado_pct"] != ""
            ]
            for e in escenarios
        ]
        caja = eje.boxplot(
            datos,
            positions=list(x),
            widths=0.45,
            patch_artist=True,
            showfliers=False,
            medianprops={"color": TINTA, "linewidth": 1.5},
            whiskerprops={"color": TINTA_2},
            capprops={"color": TINTA_2},
            zorder=2,
        )
        for parche in caja["boxes"]:
            parche.set(facecolor=COLOR_A + "33", edgecolor=COLOR_A)
        for i, valores in enumerate(datos):
            n = len(valores)
            desplazamientos = [((k * 7) % n / max(n - 1, 1) - 0.5) * 0.3 for k in range(n)]
            eje.scatter(
                [i + d for d in desplazamientos],
                valores,
                s=12,
                color=COLOR_A,
                edgecolors=FONDO,
                linewidths=0.5,
                zorder=3,
            )
        eje.axhline(0, color=TINTA_2, linewidth=0.8, zorder=1)
        eje.set_xticks(list(x), [NOMBRES[e] for e in escenarios])
        eje.set_title(f"{dias} días", fontsize=10, color=TINTA, loc="left")
    ejes[0][0].set_ylabel("Desperdicio evitado (%)")
    fig.suptitle(
        "Desperdicio evitado por el menú del día, por semilla",
        x=0.01,
        ha="left",
        fontsize=12,
        color=TINTA,
    )
    fig.text(
        0.01,
        0.005,
        "Cada punto es una semilla: 100 × (merma A − merma B) / merma A.",
        fontsize=8,
        color=TINTA_2,
    )
    fig.tight_layout(rect=(0, 0.03, 1, 0.93))
    fig.savefig(
        salida / "desperdicio_evitado.png", dpi=150, facecolor=FONDO, metadata={"Software": None}
    )
    plt.close(fig)


def graficar_sensibilidad(resumen: list[dict], salida: Path) -> None:
    """% evitado promedio según la fracción vendida del menú del día."""
    plt = _pyplot()
    fig, eje = plt.subplots(figsize=(7.2, 4.4))
    fig.patch.set_facecolor(FONDO)
    _estilo(eje)
    ventas = sorted({r["venta"] for r in resumen}, reverse=True)
    finales = {}
    for escenario in ESCENARIOS:
        puntos = {r["venta"]: r for r in resumen if r["escenario"] == escenario}
        y = [puntos[v]["desperdicio_evitado_pct_prom"] for v in ventas]
        color = COLORES_ESCENARIO[escenario]
        eje.plot(
            [100 * v for v in ventas],
            y,
            color=color,
            linewidth=2,
            marker=MARCAS_ESCENARIO[escenario],
            markersize=7,
            markeredgecolor=FONDO,
            markeredgewidth=1.5,
            label=NOMBRES[escenario],
            zorder=3,
        )
        finales[escenario] = y[-1]
    # Etiquetas al final de cada línea, separadas para que no se encimen.
    alto = eje.get_ylim()[1] - eje.get_ylim()[0]
    previa = None
    for escenario, valor in sorted(finales.items(), key=lambda par: par[1]):
        posicion = valor if previa is None else max(valor, previa + 0.05 * alto)
        previa = posicion
        eje.annotate(
            f"{NOMBRES[escenario]} {valor:.1f} %",
            (100 * ventas[-1], valor),
            xytext=(100 * ventas[-1] - 3, posicion),
            textcoords="data",
            va="center",
            fontsize=8,
            color=TINTA_2,
        )
    eje.axhline(0, color=TINTA_2, linewidth=0.8, zorder=1)
    eje.set_xlim(100 * ventas[0] + 3, 100 * ventas[-1] - 22)
    eje.set_xticks([100 * v for v in ventas], [f"{100 * v:.0f} %" for v in ventas])
    eje.set_xlabel("Parte vendida de la demanda estimada del menú del día")
    eje.set_ylabel("Desperdicio evitado promedio (%)")
    eje.legend(loc="lower left", frameon=False, fontsize=8)
    fig.suptitle(
        "Si el menú del día no se vende completo, lo que sobra se tira",
        x=0.01,
        ha="left",
        fontsize=12,
        color=TINTA,
    )
    fig.text(
        0.01,
        0.005,
        f"{DIAS_SENSIBILIDAD} días; menú del día preparado completo; promedio de "
        f"{resumen[0]['corridas']} semillas. Bajo 0, B tira más que A.",
        fontsize=8,
        color=TINTA_2,
    )
    fig.tight_layout(rect=(0, 0.03, 1, 0.94))
    fig.savefig(
        salida / "sensibilidad_venta.png", dpi=150, facecolor=FONDO, metadata={"Software": None}
    )
    plt.close(fig)


def _pyplot():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "font.size": 10,
            "axes.edgecolor": REJILLA,
            "axes.labelcolor": TINTA_2,
            "xtick.color": TINTA_2,
            "ytick.color": TINTA_2,
            "text.color": TINTA,
            "svg.hashsalt": "menucero",
        }
    )
    return plt


def _estilo(eje) -> None:
    eje.set_facecolor(FONDO)
    eje.grid(axis="y", color=REJILLA, linewidth=0.8, zorder=0)
    eje.spines[["top", "right", "left"]].set_visible(False)
    eje.tick_params(axis="both", length=0)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Simulación A vs B en los cuatro escenarios.")
    parser.add_argument("--semillas", type=int, default=30, help="número de semillas (1..N)")
    parser.add_argument("--dias", type=int, nargs="+", default=list(HORIZONTES))
    parser.add_argument("--datos", type=Path, default=RAIZ / "data" / "escenarios")
    parser.add_argument("--salida", type=Path, default=RAIZ / "resultados")
    parser.add_argument("--sin-graficas", action="store_true")
    parser.add_argument("--sin-sensibilidad", action="store_true")
    args = parser.parse_args(argv)

    filas = correr(args.datos, ESCENARIOS, args.dias, range(1, args.semillas + 1))
    resumen = resumir(filas)
    args.salida.mkdir(parents=True, exist_ok=True)
    escribir_csv(args.salida / "simulacion.csv", filas, COLUMNAS)
    escribir_csv(args.salida / "resumen.csv", resumen, list(resumen[0]))
    tabla = tabla_markdown(resumen, filas[0]["voraz"], args.semillas)
    if not args.sin_sensibilidad:
        filas_s = sensibilidad(args.datos, range(1, args.semillas + 1))
        escribir_csv(args.salida / "sensibilidad_venta.csv", filas_s, ["venta", *COLUMNAS])
        resumen_s = resumir(filas_s, ("escenario", "venta"))
        tabla += tabla_sensibilidad(resumen_s)
        if not args.sin_graficas:
            graficar_sensibilidad(resumen_s, args.salida)
    (args.salida / "resumen.md").write_text(tabla, encoding="utf-8")
    if not args.sin_graficas:
        graficar(filas, resumen, args.salida)
    print(tabla)


if __name__ == "__main__":
    main()
