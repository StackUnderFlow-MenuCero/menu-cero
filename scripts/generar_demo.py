"""Genera el dataset de demostración (data/demo/) y los escenarios (data/escenarios/) (#19).

No es aleatorio: sale del negocio tipo de ``docs/datos.md`` (#8) con reglas fijas, así
que con la misma fecha siempre da los mismos archivos. Con otra fecha, todas las
caducidades se recorren igual.

Cómo se calcula el inventario de cada ingrediente:

- ``reserva``: kg que el menú fijo usa al día (Σ demanda_fija × kg_por_porcion).
- ``cobertura``: días que cubre cada compra, ``min(ciclo de compra, vida útil)``.
- ``compra``: ``reserva × cobertura`` redondeado hacia arriba a múltiplos de la compra
  mínima del proveedor. Ese redondeo es el que deja sobrantes en los platillos poco pedidos.
- ``edad``: días desde que se compró el lote. Días para caducar = vida útil − 1 − edad.
  Cada lote tiene que alcanzar todavía para el menú fijo de hoy; si no, el negocio ya
  habría vuelto a comprar y el script lo rechaza.
- ``cantidad``: ``compra − consumo diario × edad``. El consumo usa el factor de demanda
  del escenario; la compra no, porque el negocio compra por costumbre.

Uso, desde la raíz del repositorio::

    uv run python scripts/generar_demo.py                   # hoy = 2026-11-25
    uv run python scripts/generar_demo.py --hoy 2026-12-01  # otra fecha
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import date, timedelta
from math import ceil, floor
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
HOY_DEMO = date(2026, 11, 25)  # entrega de la demostración A vs B (#30)

# Días que cubre cada compra, por cómo compra el negocio (docs/datos.md, «El negocio»).
CICLO = {
    "pollo": 3, "res": 3, "cerdo": 3, "pescado": 3,  # 2 o 3 veces por semana
    "verdura": 3, "fruta": 3,  # mercado, 2 veces por semana
    "lacteo": 5, "embutido": 5, "huevo": 5, "hongo": 5,  # una vez por semana
    "tortilla": 1,  # diario
}  # fmt: skip


@dataclass(frozen=True)
class Ingrediente:
    id: str
    nombre: str
    categoria: str
    vida_util: int  # días, dentro del rango de la caracterización
    edad: int  # días desde la compra del lote
    costo_kg: float
    compra_minima: float  # kg


@dataclass(frozen=True)
class Receta:
    id: str
    platillo: str
    tipo: str
    demanda_fija: int
    demanda_menu_dia: int
    kg_por_porcion: tuple[tuple[str, float], ...]


# ING01–ING12 y REC01–REC07 conservan los id de data/ejemplo.
INGREDIENTES = [
    # Caracterización (#8)
    Ingrediente("ING01", "Crema ácida", "lacteo", 6, 4, 70, 1),
    Ingrediente("ING02", "Champiñones", "hongo", 5, 3, 95, 1),
    Ingrediente("ING03", "Pechuga de pollo", "pollo", 4, 1, 120, 3),
    Ingrediente("ING04", "Tortilla de maíz", "tortilla", 3, 0, 25, 3),
    Ingrediente("ING05", "Bistec de res", "res", 5, 1, 180, 3),
    Ingrediente("ING06", "Queso fresco", "lacteo", 7, 3, 120, 1),
    Ingrediente("ING07", "Jitomate saladet", "verdura", 6, 2, 25, 5),
    Ingrediente("ING08", "Cebolla blanca", "verdura", 15, 2, 30, 3),
    Ingrediente("ING09", "Chile poblano", "verdura", 5, 3, 45, 2),
    Ingrediente("ING10", "Calabacita", "verdura", 6, 3, 30, 2),
    Ingrediente("ING11", "Carne molida de res", "res", 2, 0, 130, 2),
    Ingrediente("ING12", "Papa blanca", "verdura", 18, 2, 35, 4),
    Ingrediente("ING13", "Filete de tilapia", "pescado", 2, 1, 100, 2),
    Ingrediente("ING14", "Huevo", "huevo", 28, 3, 45, 1.8),
    Ingrediente("ING15", "Lechuga romana", "verdura", 5, 1, 45, 1),
    Ingrediente("ING16", "Aguacate Hass", "fruta", 3, 2, 40, 2),
    Ingrediente("ING17", "Chile serrano", "verdura", 9, 2, 40, 0.5),
    Ingrediente("ING18", "Limón", "fruta", 12, 2, 30, 1),
    # Ampliación para la demo: desayunos, bebidas y más guisados
    Ingrediente("ING19", "Chuleta de cerdo", "cerdo", 4, 1, 110, 2),
    Ingrediente("ING20", "Pierna y muslo de pollo", "pollo", 3, 1, 100, 3),
    Ingrediente("ING21", "Nopales", "verdura", 4, 3, 25, 2),
    Ingrediente("ING22", "Tomate verde", "verdura", 10, 2, 28, 2),
    Ingrediente("ING23", "Cilantro", "verdura", 5, 2, 40, 0.5),
    Ingrediente("ING24", "Zanahoria", "verdura", 14, 2, 20, 2),
    Ingrediente("ING25", "Chayote", "verdura", 10, 2, 25, 2),
    Ingrediente("ING26", "Ejotes", "verdura", 6, 2, 35, 1),
    Ingrediente("ING27", "Elote", "verdura", 5, 2, 20, 2),
    Ingrediente("ING28", "Brócoli", "verdura", 6, 2, 40, 1),
    Ingrediente("ING29", "Pimiento morrón", "verdura", 8, 2, 50, 1),
    Ingrediente("ING30", "Melón", "fruta", 5, 2, 22, 2),
    Ingrediente("ING31", "Papaya", "fruta", 5, 2, 25, 2),
    Ingrediente("ING32", "Piña", "fruta", 6, 2, 22, 2),
    Ingrediente("ING33", "Plátano", "fruta", 5, 2, 22, 2),
    Ingrediente("ING34", "Bolillo", "tortilla", 3, 0, 35, 3),
    Ingrediente("ING35", "Queso chihuahua", "lacteo", 10, 3, 130, 1),
    Ingrediente("ING36", "Yogur natural", "lacteo", 10, 3, 60, 1),
    Ingrediente("ING37", "Leche entera", "lacteo", 7, 3, 28, 3),
    Ingrediente("ING38", "Mantequilla", "lacteo", 30, 3, 130, 1),
    Ingrediente("ING39", "Jamón de pavo", "embutido", 8, 3, 110, 1),
    Ingrediente("ING40", "Chorizo", "embutido", 10, 3, 95, 1),
]

RECETAS = [
    # Caracterización (#8): menú fijo
    Receta("REC01", "Pollo a la crema con champiñones", "fijo", 3, 12,
           (("ING03", 0.150), ("ING01", 0.040), ("ING02", 0.030))),
    Receta("REC02", "Tacos de bistec", "fijo", 25, 5, (("ING05", 0.120), ("ING04", 0.090))),
    Receta("REC03", "Enchiladas suizas", "fijo", 6, 10,
           (("ING03", 0.100), ("ING01", 0.050), ("ING04", 0.080))),
    Receta("REC04", "Chiles rellenos de queso", "fijo", 2, 8,
           (("ING09", 0.150), ("ING06", 0.070), ("ING07", 0.080), ("ING08", 0.020))),
    Receta("REC05", "Picadillo de res con papa", "fijo", 12, 6,
           (("ING11", 0.120), ("ING12", 0.080), ("ING10", 0.050), ("ING07", 0.040),
            ("ING08", 0.015))),
    Receta("REC08", "Chilaquiles rojos con pollo", "fijo", 30, 3,
           (("ING04", 0.090), ("ING03", 0.080), ("ING07", 0.060), ("ING01", 0.020),
            ("ING06", 0.020))),
    Receta("REC09", "Milanesa de pollo con arroz y frijoles", "fijo", 20, 4,
           (("ING03", 0.150), ("ING14", 0.030), ("ING15", 0.030), ("ING07", 0.030))),
    Receta("REC10", "Huevos al gusto", "fijo", 15, 3,
           (("ING14", 0.110), ("ING04", 0.060), ("ING07", 0.040), ("ING08", 0.010),
            ("ING17", 0.005))),
    Receta("REC11", "Bistec a la mexicana", "fijo", 10, 6,
           (("ING05", 0.150), ("ING04", 0.090), ("ING07", 0.080), ("ING08", 0.030),
            ("ING17", 0.010))),
    Receta("REC12", "Filete de pescado a la plancha", "fijo", 2, 6,
           (("ING13", 0.180), ("ING15", 0.040), ("ING07", 0.030), ("ING18", 0.020))),
    # Caracterización (#8): secundarias
    Receta("REC06", "Calabacitas con queso", "secundaria", 0, 8,
           (("ING10", 0.150), ("ING06", 0.040), ("ING07", 0.050), ("ING08", 0.020))),
    Receta("REC07", "Crema de champiñones", "secundaria", 0, 10,
           (("ING02", 0.080), ("ING01", 0.050))),
    Receta("REC13", "Sopa de tortilla", "secundaria", 0, 10,
           (("ING07", 0.080), ("ING04", 0.060), ("ING16", 0.030), ("ING01", 0.020),
            ("ING06", 0.020))),
    Receta("REC14", "Tostadas de tinga de pollo", "secundaria", 0, 8,
           (("ING03", 0.080), ("ING07", 0.060), ("ING04", 0.060), ("ING08", 0.040),
            ("ING15", 0.030), ("ING01", 0.020))),
    # Ampliación para la demo: menú fijo
    Receta("REC15", "Chuleta de cerdo en salsa verde", "fijo", 8, 6,
           (("ING19", 0.180), ("ING22", 0.080), ("ING08", 0.020), ("ING17", 0.010),
            ("ING23", 0.005))),
    Receta("REC16", "Caldo de pollo con verduras", "fijo", 10, 5,
           (("ING20", 0.200), ("ING25", 0.060), ("ING24", 0.050), ("ING27", 0.050),
            ("ING10", 0.040), ("ING26", 0.030), ("ING18", 0.010), ("ING23", 0.005))),
    Receta("REC17", "Molletes con pico de gallo", "fijo", 12, 4,
           (("ING34", 0.140), ("ING35", 0.050), ("ING07", 0.030), ("ING08", 0.010),
            ("ING23", 0.003), ("ING17", 0.003))),
    Receta("REC18", "Torta de jamón", "fijo", 8, 4,
           (("ING34", 0.070), ("ING39", 0.060), ("ING35", 0.030), ("ING16", 0.030),
            ("ING07", 0.020), ("ING15", 0.015))),
    Receta("REC19", "Huevos con chorizo", "fijo", 6, 4,
           (("ING14", 0.110), ("ING40", 0.050), ("ING04", 0.060))),
    Receta("REC20", "Nopales a la mexicana con queso", "fijo", 2, 8,
           (("ING21", 0.200), ("ING07", 0.060), ("ING06", 0.030), ("ING08", 0.020),
            ("ING17", 0.005))),
    Receta("REC21", "Coctel de fruta con yogur", "fijo", 6, 8,
           (("ING30", 0.070), ("ING31", 0.070), ("ING32", 0.070), ("ING36", 0.060),
            ("ING33", 0.050))),
    Receta("REC22", "Pollo con brócoli y verduras", "fijo", 3, 8,
           (("ING03", 0.150), ("ING28", 0.080), ("ING24", 0.040), ("ING29", 0.040),
            ("ING08", 0.020))),
    Receta("REC23", "Hotcakes con mantequilla", "fijo", 8, 4,
           (("ING37", 0.080), ("ING14", 0.030), ("ING38", 0.020))),
    Receta("REC24", "Licuado de plátano", "fijo", 10, 5, (("ING37", 0.250), ("ING33", 0.120))),
    # Ampliación para la demo: secundarias
    Receta("REC25", "Sopa de verduras", "secundaria", 0, 10,
           (("ING12", 0.040), ("ING24", 0.040), ("ING25", 0.040), ("ING10", 0.040),
            ("ING26", 0.030), ("ING27", 0.030), ("ING07", 0.030))),
    Receta("REC26", "Rajas con crema y elote", "secundaria", 0, 8,
           (("ING09", 0.100), ("ING27", 0.060), ("ING01", 0.040), ("ING06", 0.030),
            ("ING08", 0.015))),
]  # fmt: skip


@dataclass(frozen=True)
class Escenario:
    nombre: str
    descripcion: str
    factor: float  # multiplica demanda_fija y demanda_menu_dia (docs/datos.md)
    dias_extra: int = 0  # días que los lotes envejecen sin vender nada


ESCENARIOS = [
    Escenario("normal", "Semana normal de clases (factor 1.00); igual a data/demo.", 1.0),
    Escenario("examenes", "Exámenes y fin de semestre (factor 0.80).", 0.8),
    Escenario("vacaciones", "Vacaciones (factor 0.25): baja demanda.", 0.25),
    Escenario(
        "alta_caducidad",
        "Regreso de un puente: el local cerró 2 días y los lotes envejecieron sin venderse.",
        1.0,
        dias_extra=2,
    ),
]  # fmt: skip


def redondear(x: float) -> int:
    return floor(x + 0.5)


def reserva_diaria(factor: float = 1.0) -> dict[str, float]:
    reserva = {i.id: 0.0 for i in INGREDIENTES}
    for r in RECETAS:
        if r.tipo == "fijo":
            for i, q in r.kg_por_porcion:
                reserva[i] += redondear(r.demanda_fija * factor) * q
    return reserva


def inventario(hoy: date, escenario: Escenario) -> list[dict[str, str]]:
    habitual = reserva_diaria()  # el negocio compra por costumbre
    real = reserva_diaria(escenario.factor)  # lo que de verdad se vendió desde la compra
    filas = []
    for ing in INGREDIENTES:
        cobertura = min(CICLO[ing.categoria], ing.vida_util)
        compra = ceil(round(habitual[ing.id] * cobertura / ing.compra_minima, 9))
        compra = max(1, compra) * ing.compra_minima
        cantidad = compra - real[ing.id] * ing.edad
        if cantidad < real[ing.id] or cantidad <= 0:
            # El lote ya no alcanzaría para el menú fijo de hoy: el negocio habría vuelto a comprar.
            raise ValueError(
                f"{ing.id}: con edad {ing.edad} quedan {cantidad:.2f} kg, menos que un día"
            )
        dias = ing.vida_util - 1 - ing.edad - escenario.dias_extra
        filas.append(
            {
                "ingrediente_id": ing.id,
                "nombre": ing.nombre,
                "cantidad_kg": f"{cantidad:.2f}",
                "fecha_caducidad": (hoy + timedelta(days=dias)).isoformat(),
                "costo_kg": f"{ing.costo_kg:.2f}",
            }
        )
    return filas


def recetas() -> list[dict[str, str]]:
    return [
        {
            "receta_id": r.id,
            "platillo": r.platillo,
            "tipo": r.tipo,
            "ingrediente_id": i,
            "kg_por_porcion": f"{q:.3f}",
        }
        for r in RECETAS
        for i, q in r.kg_por_porcion
    ]


def demanda(factor: float) -> list[dict[str, str]]:
    return [
        {
            "receta_id": r.id,
            "demanda_fija": str(redondear(r.demanda_fija * factor)),
            "demanda_menu_dia": str(redondear(r.demanda_menu_dia * factor)),
        }
        for r in RECETAS
    ]


def escribir(carpeta: Path, nombre: str, filas: list[dict[str, str]]) -> None:
    carpeta.mkdir(parents=True, exist_ok=True)
    with open(carpeta / nombre, "w", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=list(filas[0]), lineterminator="\n")
        escritor.writeheader()
        escritor.writerows(filas)


def generar(hoy: date, raiz: Path) -> None:
    for esc in ESCENARIOS:
        carpetas = [raiz / "escenarios" / esc.nombre]
        if esc.nombre == "normal":
            carpetas.append(raiz / "demo")
        for carpeta in carpetas:
            escribir(carpeta, "inventario.csv", inventario(hoy, esc))
            escribir(carpeta, "recetas.csv", recetas())
            escribir(carpeta, "demanda.csv", demanda(esc.factor))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--hoy",
        type=date.fromisoformat,
        default=HOY_DEMO,
        help=f"fecha de referencia AAAA-MM-DD (por omisión {HOY_DEMO})",
    )
    parser.add_argument(
        "--salida",
        type=Path,
        default=RAIZ / "data",
        help="carpeta donde se escriben demo/ y escenarios/ (por omisión data/)",
    )
    args = parser.parse_args(argv)
    generar(args.hoy, args.salida)
    print(f"Escritos {args.salida / 'demo'} y {args.salida / 'escenarios'} con hoy = {args.hoy}")


if __name__ == "__main__":
    main()
