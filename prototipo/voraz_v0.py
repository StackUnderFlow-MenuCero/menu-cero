"""Prototipo v0 del voraz de Menú Cero (Checkpoint 1).

Primera solución ejecutable, en un solo archivo y sin dependencias externas:

1. Lee los tres CSV (inventario, recetas y demanda) sin validarlos.
2. Calcula los días para caducar, la prioridad p = 1/(d + 1) y los kg en riesgo:
   lo que el menú fijo no alcanza a usar antes de que el ingrediente caduque.
3. Da a cada receta un puntaje: lo que aprovecha, por porción, de los
   ingredientes en riesgo, pesado por su prioridad.
4. Recorre las recetas de mayor a menor puntaje y a cada una le asigna todas
   las porciones posibles sin pasar su demanda ni el inventario.

Es una versión deliberadamente simple. El voraz definitivo (#20 y #23) se
programa en ``src/menucero/voraz.py`` y mejora tres cosas: recorre primero los
ingredientes más urgentes, no prepara más porciones de las que hacen falta para
salvar un ingrediente y genera de 3 a 5 propuestas.

Uso, desde la raíz del repositorio::

    uv run python prototipo/voraz_v0.py data/ejemplo --hoy 2026-11-17
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass, field
from datetime import date
from math import floor
from pathlib import Path
from time import perf_counter

EPS = 1e-9
CARPETA_EJEMPLO = Path(__file__).resolve().parents[1] / "data" / "ejemplo"


@dataclass(frozen=True)
class Ingrediente:
    id: str
    nombre: str
    cantidad_kg: float
    caducidad: date
    costo_kg: float


@dataclass
class Receta:
    id: str
    platillo: str
    tipo: str
    kg_por_porcion: dict[str, float] = field(default_factory=dict)
    demanda_fija: int = 0
    demanda_menu_dia: int = 0


@dataclass(frozen=True)
class Urgencia:
    """Lo que se calcula de cada ingrediente vigente para el día ``hoy``."""

    dias: int
    prioridad: float
    reserva_kg: float  # lo que el menú fijo usa cada día
    disponible_kg: float  # lo que queda hoy para el menú del día
    riesgo_kg: float  # lo que se desperdicia si solo se vende el menú fijo


@dataclass
class Resultado:
    porciones: dict[str, int]
    usado_kg: dict[str, float]
    valor: float  # V = Σ p · min(usado, riesgo)
    riesgo_total_kg: float
    aprovechado_kg: float

    @property
    def porcentaje(self) -> float:
        if self.riesgo_total_kg <= EPS:
            return 0.0
        return 100 * self.aprovechado_kg / self.riesgo_total_kg


def leer_csv(carpeta: Path) -> tuple[dict[str, Ingrediente], dict[str, Receta]]:
    """Lee los tres CSV de ``carpeta`` (formato de ``docs/datos.md``)."""
    ingredientes = {}
    with open(carpeta / "inventario.csv", encoding="utf-8-sig", newline="") as f:
        for fila in csv.DictReader(f):
            ingredientes[fila["ingrediente_id"]] = Ingrediente(
                id=fila["ingrediente_id"],
                nombre=fila["nombre"],
                cantidad_kg=float(fila["cantidad_kg"]),
                caducidad=date.fromisoformat(fila["fecha_caducidad"]),
                costo_kg=float(fila["costo_kg"]),
            )

    recetas: dict[str, Receta] = {}
    with open(carpeta / "recetas.csv", encoding="utf-8-sig", newline="") as f:
        for fila in csv.DictReader(f):
            receta = recetas.setdefault(
                fila["receta_id"], Receta(fila["receta_id"], fila["platillo"], fila["tipo"])
            )
            receta.kg_por_porcion[fila["ingrediente_id"]] = float(fila["kg_por_porcion"])

    with open(carpeta / "demanda.csv", encoding="utf-8-sig", newline="") as f:
        for fila in csv.DictReader(f):
            receta = recetas[fila["receta_id"]]
            receta.demanda_fija = int(fila["demanda_fija"])
            receta.demanda_menu_dia = int(fila["demanda_menu_dia"])

    return ingredientes, recetas


def calcular_urgencias(
    ingredientes: dict[str, Ingrediente], recetas: dict[str, Receta], hoy: date
) -> dict[str, Urgencia]:
    """Urgencia de cada ingrediente vigente. Los caducados no aparecen."""
    reserva = dict.fromkeys(ingredientes, 0.0)
    for receta in recetas.values():
        if receta.tipo == "fijo":
            for i, q in receta.kg_por_porcion.items():
                reserva[i] += receta.demanda_fija * q

    urgencias = {}
    for i, ing in ingredientes.items():
        dias = (ing.caducidad - hoy).days
        if dias < 0:
            continue
        urgencias[i] = Urgencia(
            dias=dias,
            prioridad=1 / (dias + 1),
            reserva_kg=reserva[i],
            disponible_kg=max(0.0, ing.cantidad_kg - reserva[i]),
            riesgo_kg=max(0.0, ing.cantidad_kg - reserva[i] * (dias + 1)),
        )
    return urgencias


def puntaje(receta: Receta, urgencias: dict[str, Urgencia]) -> float:
    """Valor de una porción: Σ p · min(q, riesgo) sobre sus ingredientes."""
    total = 0.0
    for i, q in receta.kg_por_porcion.items():
        u = urgencias.get(i)
        if u is not None:
            total += u.prioridad * min(q, u.riesgo_kg)
    return total


def generar_menu(
    ingredientes: dict[str, Ingrediente], recetas: dict[str, Receta], hoy: date
) -> Resultado:
    """Voraz v0: recetas por puntaje descendente, cada una con todas las porciones posibles."""
    urgencias = calcular_urgencias(ingredientes, recetas, hoy)
    resto = {i: u.disponible_kg for i, u in urgencias.items()}

    candidatas = []
    for receta in recetas.values():
        # Una receta con un ingrediente caducado o inexistente no se puede preparar.
        if all(i in urgencias for i in receta.kg_por_porcion):
            p = puntaje(receta, urgencias)
            if p > EPS:
                candidatas.append((p, receta))
    candidatas.sort(key=lambda par: (-par[0], par[1].id))

    porciones: dict[str, int] = {}
    for _, receta in candidatas:
        por_inventario = min(floor(resto[i] / q + EPS) for i, q in receta.kg_por_porcion.items())
        x = min(receta.demanda_menu_dia, por_inventario)
        if x >= 1:
            porciones[receta.id] = x
            for i, q in receta.kg_por_porcion.items():
                resto[i] -= x * q

    usado = {i: urgencias[i].disponible_kg - resto[i] for i in urgencias}
    salvado = {i: min(usado[i], u.riesgo_kg) for i, u in urgencias.items()}
    return Resultado(
        porciones=porciones,
        usado_kg=usado,
        valor=sum(urgencias[i].prioridad * kg for i, kg in salvado.items()),
        riesgo_total_kg=sum(u.riesgo_kg for u in urgencias.values()),
        aprovechado_kg=sum(salvado.values()),
    )


def reporte(
    ingredientes: dict[str, Ingrediente],
    recetas: dict[str, Receta],
    hoy: date,
    resultado: Resultado,
    ms: float,
) -> str:
    """Texto que se imprime en la terminal."""
    urgencias = calcular_urgencias(ingredientes, recetas, hoy)
    lineas = [f"Menú Cero · voraz v0 · hoy = {hoy.isoformat()}", ""]

    lineas.append("Ingredientes en riesgo, del más urgente al menos urgente")
    lineas.append(f"  {'id':<6}{'ingrediente':<20}{'días':>5}{'p':>7}{'riesgo':>9}{'usado':>8}")
    en_riesgo = [i for i, u in urgencias.items() if u.riesgo_kg > EPS]
    en_riesgo.sort(key=lambda i: (-urgencias[i].prioridad, -urgencias[i].riesgo_kg, i))
    for i in en_riesgo:
        u = urgencias[i]
        lineas.append(
            f"  {i:<6}{ingredientes[i].nombre[:19]:<20}{u.dias:>5}{u.prioridad:>7.2f}"
            f"{u.riesgo_kg:>7.2f}kg{resultado.usado_kg[i]:>6.2f}kg"
        )
    caducados = sorted(set(ingredientes) - set(urgencias))
    if caducados:
        lineas.append(f"  Caducados (no se usan): {', '.join(caducados)}")

    lineas += ["", "Menú del día propuesto"]
    for j, x in resultado.porciones.items():
        lineas.append(f"  {j}  {recetas[j].platillo[:34]:<34}{x:>4} porciones")
    if not resultado.porciones:
        lineas.append("  (ninguna receta aprovecha ingredientes en riesgo)")

    lineas += [
        "",
        f"Kg en riesgo aprovechados: {resultado.aprovechado_kg:.2f} de "
        f"{resultado.riesgo_total_kg:.2f} kg ({resultado.porcentaje:.1f} %)",
        f"V = Σ p·min(usado, riesgo) = {resultado.valor:.5f}",
        f"Tiempo del voraz: {ms:.3f} ms",
    ]
    return "\n".join(lineas)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Prototipo v0 del voraz de Menú Cero.")
    parser.add_argument(
        "carpeta",
        nargs="?",
        type=Path,
        default=CARPETA_EJEMPLO,
        help="carpeta con inventario.csv, recetas.csv y demanda.csv (por omisión, data/ejemplo)",
    )
    parser.add_argument(
        "--hoy",
        type=date.fromisoformat,
        default=date.today(),
        help="fecha de referencia AAAA-MM-DD (los datos de ejemplo usan 2026-11-17)",
    )
    args = parser.parse_args(argv)

    ingredientes, recetas = leer_csv(args.carpeta)
    inicio = perf_counter()
    resultado = generar_menu(ingredientes, recetas, args.hoy)
    ms = (perf_counter() - inicio) * 1000
    print(reporte(ingredientes, recetas, args.hoy, resultado, ms))


if __name__ == "__main__":
    main()
