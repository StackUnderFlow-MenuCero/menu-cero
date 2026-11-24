"""Simulación día por día de los escenarios A (menú fijo) y B (menú fijo + menú del día).

El simulador avanza ``dias`` días a partir de ``hoy`` con el inventario inicial y
**sin reposición**. Cada día, en este orden:

1. Lo que ya estaba caducado al empezar cuenta como merma del primer día.
2. Solo en B: se genera el menú del día con el voraz sobre el inventario de ese
   día (lo agotado o caducado va con 0 kg).
3. Se atiende el menú fijo, receta por receta en orden de id. Un platillo se
   sirve hasta donde alcance el inventario; lo que falta son porciones no
   atendidas.
4. Solo en B: se venden las porciones del menú del día con lo que quedó. El menú
   fijo va primero, así que el menú del día nunca le quita porciones ese día.
5. Lo que llega a su fecha de caducidad sin usarse es merma de ese día.

Con ``ruido=True``, la demanda de cada platillo es Poisson con media la demanda
estimada, y la del menú del día limita lo que se vende de cada propuesta. Las
demandas se sortean al inicio, antes de cualquier decisión, para que A y B con
la misma semilla vean exactamente los mismos clientes.

El voraz se puede pasar en ``generador``. Si no se pasa, se usa
``menucero.voraz.generar_menu`` (#20) y, mientras no esté en ``main``, el
prototipo ``prototipo/voraz_v0.py``.
"""

from __future__ import annotations

import importlib.util
import random
import sys
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from math import exp, floor
from pathlib import Path
from typing import Any

EPS = 1e-9
ESCENARIOS = ("A", "B")
PROTOTIPO_V0 = Path(__file__).resolve().parents[2] / "prototipo" / "voraz_v0.py"

Generador = Callable[[list[Any], list[Any], date], Any]


@dataclass
class ResultadoSimulacion:
    """Resultado de simular un escenario (contrato de la sección 4.5 de las guías).

    ``consumo_diario`` tiene un registro por día con las llaves ``fecha``,
    ``consumo_kg`` y ``merma_kg`` (por ingrediente), ``porciones_fijas``,
    ``porciones_menu_dia`` y ``no_atendidas`` (por receta). ``menus`` guarda el
    menú del día propuesto cada día (vacío en A).
    """

    escenario: str
    dias: int
    merma_kg: dict[str, float]
    merma_costo: float
    porciones_no_atendidas: int
    consumo_diario: list[dict] = field(default_factory=list)
    menus: list[dict[str, int]] = field(default_factory=list)
    inventario_final: dict[str, float] = field(default_factory=dict)

    @property
    def merma_total_kg(self) -> float:
        return sum(self.merma_kg.values())


def simular(
    ingredientes: Iterable[Any] | Mapping[str, Any],
    recetas: Iterable[Any] | Mapping[str, Any],
    hoy: date,
    dias: int = 7,
    escenario: str = "A",
    semilla: int | None = None,
    ruido: bool = False,
    generador: Generador | None = None,
) -> ResultadoSimulacion:
    """Simula ``dias`` días del escenario ``"A"`` o ``"B"`` a partir de ``hoy``.

    ``ingredientes`` y ``recetas`` son los ``Ingrediente`` y ``Receta`` de
    ``modelos.py`` (o cualquier dataclass con los mismos campos), en lista o en
    diccionario por id. ``generador(ingredientes, recetas, fecha)`` devuelve el
    menú del día como ``{receta_id: porciones}`` o como un objeto con
    ``.porciones`` (``MenuGenerado``).
    """
    if escenario not in ESCENARIOS:
        raise ValueError(f"escenario debe ser 'A' o 'B', no {escenario!r}")
    if dias < 1:
        raise ValueError("dias debe ser al menos 1")

    ingredientes = _lista(ingredientes)
    recetas = sorted(_lista(recetas), key=lambda r: r.id)
    if escenario == "B" and generador is None:
        generador = voraz_por_omision()

    por_id = {ing.id: ing for ing in ingredientes}
    stock = {ing.id: ing.cantidad_kg for ing in ingredientes}
    costo = {ing.id: ing.costo_kg for ing in ingredientes}
    merma = dict.fromkeys(stock, 0.0)
    demanda_fija, demanda_menu = _sortear_demandas(recetas, dias, semilla, ruido)

    registro: list[dict] = []
    menus: list[dict[str, int]] = []
    no_atendidas_total = 0

    for t in range(dias):
        fecha = hoy + timedelta(days=t)
        consumo = dict.fromkeys(stock, 0.0)
        merma_dia = dict.fromkeys(stock, 0.0)

        if t == 0:
            for i, ing in por_id.items():
                if ing.fecha_caducidad < hoy and stock[i] > EPS:
                    merma_dia[i] += stock[i]
                    stock[i] = 0.0

        propuesta: dict[str, int] = {}
        if escenario == "B":
            # El inventario del día tal como lo cargaría el negocio: mismas filas, con
            # lo que queda de cada ingrediente (0 si se agotó o ya caducó).
            del_dia = [replace(ing, cantidad_kg=_cero(stock[i])) for i, ing in por_id.items()]
            propuesta = _porciones(generador(del_dia, recetas, fecha))
            menus.append(propuesta)

        servidas: dict[str, int] = {}
        no_atendidas: dict[str, int] = {}
        for receta in recetas:
            if receta.tipo != "fijo" or demanda_fija[t][receta.id] == 0:
                continue
            pedidas = demanda_fija[t][receta.id]
            x = min(pedidas, _maximo(receta, stock, por_id, fecha))
            _consumir(receta, x, stock, consumo)
            servidas[receta.id] = x
            if x < pedidas:
                no_atendidas[receta.id] = pedidas - x

        vendidas: dict[str, int] = {}
        for receta in recetas:
            if receta.id not in propuesta:
                continue
            x = min(
                propuesta[receta.id],
                demanda_menu[t][receta.id],
                _maximo(receta, stock, por_id, fecha),
            )
            if x > 0:
                _consumir(receta, x, stock, consumo)
                vendidas[receta.id] = x

        for i, ing in por_id.items():
            if ing.fecha_caducidad == fecha and stock[i] > EPS:
                merma_dia[i] += stock[i]
                stock[i] = 0.0

        for i, kg in merma_dia.items():
            merma[i] += kg
        no_atendidas_total += sum(no_atendidas.values())
        registro.append(
            {
                "dia": t + 1,
                "fecha": fecha,
                "consumo_kg": _limpiar(consumo),
                "merma_kg": _limpiar(merma_dia),
                "porciones_fijas": servidas,
                "porciones_menu_dia": vendidas,
                "no_atendidas": no_atendidas,
            }
        )

    merma = {i: _cero(kg) for i, kg in merma.items()}
    return ResultadoSimulacion(
        escenario=escenario,
        dias=dias,
        merma_kg=merma,
        merma_costo=sum(costo[i] * kg for i, kg in merma.items()),
        porciones_no_atendidas=no_atendidas_total,
        consumo_diario=registro,
        menus=menus,
        inventario_final={i: _cero(kg) for i, kg in stock.items()},
    )


def voraz_por_omision() -> Generador:
    """El voraz principal (#20) si ya existe; si no, el prototipo v0."""
    try:
        from menucero import voraz

        return voraz.generar_menu
    except (ImportError, AttributeError):
        return _cargar_voraz_v0()


def _cargar_voraz_v0() -> Generador:
    """Adapta ``prototipo/voraz_v0.py`` a la firma del contrato."""
    v0 = sys.modules.get("voraz_v0")
    if v0 is None:
        spec = importlib.util.spec_from_file_location("voraz_v0", PROTOTIPO_V0)
        if spec is None or spec.loader is None or not PROTOTIPO_V0.exists():
            raise RuntimeError(
                "No hay voraz para el escenario B: falta menucero.voraz.generar_menu (#20) "
                f"y no se encontró {PROTOTIPO_V0}."
            )
        v0 = importlib.util.module_from_spec(spec)
        sys.modules["voraz_v0"] = v0  # dataclasses lo necesita registrado
        spec.loader.exec_module(v0)

    def generar(ingredientes: list[Any], recetas: list[Any], hoy: date) -> dict[str, int]:
        ings = {
            ing.id: v0.Ingrediente(
                ing.id, ing.nombre, ing.cantidad_kg, ing.fecha_caducidad, ing.costo_kg
            )
            for ing in ingredientes
        }
        recs = {
            r.id: v0.Receta(
                r.id, r.platillo, r.tipo, dict(r.ingredientes), r.demanda_fija, r.demanda_menu_dia
            )
            for r in recetas
        }
        return v0.generar_menu(ings, recs, hoy).porciones

    return generar


def _lista(datos: Iterable[Any] | Mapping[str, Any]) -> list[Any]:
    return list(datos.values()) if isinstance(datos, Mapping) else list(datos)


def _porciones(menu: Any) -> dict[str, int]:
    porciones = getattr(menu, "porciones", menu)
    return {j: int(x) for j, x in porciones.items() if x > 0}


def _maximo(receta: Any, stock: dict[str, float], por_id: dict[str, Any], fecha: date) -> int:
    """Porciones de ``receta`` que alcanzan con el inventario vigente en ``fecha``."""
    maximo = None
    for i, q in receta.ingredientes.items():
        if i not in por_id or por_id[i].fecha_caducidad < fecha:
            return 0
        n = floor(stock[i] / q + EPS)
        maximo = n if maximo is None else min(maximo, n)
    return maximo or 0


def _consumir(receta: Any, x: int, stock: dict[str, float], consumo: dict[str, float]) -> None:
    for i, q in receta.ingredientes.items():
        kg = min(stock[i], x * q)
        stock[i] -= kg
        consumo[i] += kg


def _sortear_demandas(
    recetas: list[Any], dias: int, semilla: int | None, ruido: bool
) -> tuple[list[dict[str, int]], list[dict[str, int]]]:
    """Demanda fija y del menú del día de cada receta, día por día."""
    rng = random.Random(semilla)
    fija, menu = [], []
    for _ in range(dias):
        f, m = {}, {}
        for r in recetas:
            f[r.id] = _poisson(rng, r.demanda_fija) if ruido else r.demanda_fija
            m[r.id] = _poisson(rng, r.demanda_menu_dia) if ruido else r.demanda_menu_dia
        fija.append(f)
        menu.append(m)
    return fija, menu


def _poisson(rng: random.Random, media: float) -> int:
    """Número de clientes con distribución de Poisson (método de Knuth)."""
    if media <= 0:
        return 0
    limite, k, p = exp(-media), 0, rng.random()
    while p > limite:
        k += 1
        p *= rng.random()
    return k


def _cero(kg: float) -> float:
    return 0.0 if abs(kg) < EPS else kg


def _limpiar(kg: dict[str, float]) -> dict[str, float]:
    return {i: v for i, v in kg.items() if v > EPS}
