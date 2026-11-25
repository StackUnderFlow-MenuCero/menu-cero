"""Algoritmo voraz para generar propuestas de menú del día (issues #20 y #23).

Implementación independiente de Pandas, Streamlit y de la fecha del sistema.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from math import ceil, floor

from menucero.modelos import Ingrediente, Receta
from menucero.prioridad import (
    dias_para_caducar,
    kg_en_riesgo,
    ordenar_por_prioridad,
    prioridad,
    reserva_diaria,
    separar_caducados,
)

EPS = 1e-9
VARIANTES = ("base", "sin_principal", "economica", "eficiencia", "secundarias")


def _iter_ingredientes(
    ingredientes: Iterable[Ingrediente] | Mapping[str, Ingrediente],
) -> Iterable[Ingrediente]:
    if isinstance(ingredientes, Mapping):
        return ingredientes.values()
    return ingredientes


def _iter_recetas(
    recetas: Iterable[Receta] | Mapping[str, Receta],
) -> Iterable[Receta]:
    if isinstance(recetas, Mapping):
        return recetas.values()
    return recetas


@dataclass(slots=True)
class Estado:
    """Datos precalculados de una instancia para una fecha ``hoy``.

    Attributes:
        ingredientes: Ingredientes vigentes indexados por ``id``.
        recetas: Recetas existentes indexadas por ``id``.
        p: Prioridad ``1 / (d + 1)`` de cada ingrediente vigente.
        disponible: Existencia disponible hoy tras reservar el menú fijo (kg).
            Los ingredientes faltantes o caducados no aparecen (equivalen a 0 kg).
        riesgo: Kilogramos en riesgo antes de caducar por ingrediente vigente (kg).
        usa: Índice invertido ``{ingrediente_id: [receta_id, ...]}``.
        orden: Lista ``L`` de ``ingrediente_id`` con ``riesgo > EPS``, ordenados
            por prioridad descendente, valor en riesgo descendente e ``id``.
    """

    ingredientes: dict[str, Ingrediente]
    recetas: dict[str, Receta]
    p: dict[str, float]
    disponible: dict[str, float]
    riesgo: dict[str, float]
    usa: dict[str, list[str]]
    orden: list[str]


def preparar(
    ingredientes: Iterable[Ingrediente] | Mapping[str, Ingrediente],
    recetas: Iterable[Receta] | Mapping[str, Receta],
    hoy: date,
) -> Estado:
    """Precalcula urgencias, inventario disponible, riesgo e índice invertido.

    Separa y descarta los ingredientes ya caducados respecto de ``hoy`` y deja
    lista la estructura ``Estado`` para ejecutar una o varias pasadas de llenado
    sin repetir el preprocesamiento.
    """
    lista_recetas = list(_iter_recetas(recetas))
    vigentes, _ = separar_caducados(_iter_ingredientes(ingredientes), hoy)

    ing_por_id = {ing.id: ing for ing in vigentes}
    rec_por_id = {rec.id: rec for rec in lista_recetas}

    reserva = reserva_diaria(lista_recetas)
    riesgo = kg_en_riesgo(vigentes, lista_recetas, hoy)
    p = {ing.id: prioridad(dias_para_caducar(ing, hoy)) for ing in vigentes}
    disponible = {ing.id: max(0.0, ing.cantidad_kg - reserva.get(ing.id, 0.0)) for ing in vigentes}

    usa: defaultdict[str, list[str]] = defaultdict(list)
    for rec in lista_recetas:
        for ing_id in rec.ingredientes:
            usa[ing_id].append(rec.id)

    orden = [
        ing.id
        for ing in ordenar_por_prioridad(vigentes, hoy, riesgo)
        if riesgo.get(ing.id, 0.0) > EPS
    ]

    return Estado(
        ingredientes=ing_por_id,
        recetas=rec_por_id,
        p=p,
        disponible=disponible,
        riesgo=riesgo,
        usa=dict(usa),
        orden=orden,
    )


def valor_objetivo(porciones: Mapping[str, int], estado: Estado) -> float:
    """Evalúa ``V(x) = Σ_i p_i · min(usado_i, riesgo_i)`` para una asignación."""
    usado: defaultdict[str, float] = defaultdict(float)
    for rec_id, x in porciones.items():
        if x <= 0:
            continue
        receta = estado.recetas[rec_id]
        for ing_id, kg_por_porcion in receta.ingredientes.items():
            usado[ing_id] += x * kg_por_porcion

    return sum(
        estado.p[ing_id] * min(kg_usado, estado.riesgo[ing_id])
        for ing_id, kg_usado in usado.items()
        if estado.riesgo.get(ing_id, 0.0) > EPS
    )


def _puntaje_receta(receta: Receta, variante: str, estado: Estado) -> float:
    """Calcula el puntaje de ordenamiento de ``receta`` según ``variante``."""
    if variante == "base":
        return sum(
            estado.p[h] * kg
            for h, kg in receta.ingredientes.items()
            if estado.riesgo.get(h, 0.0) > EPS
        )
    raise NotImplementedError(f"variante pendiente de implementar: {variante!r}")


def _porciones_posibles(
    receta: Receta,
    ing_id: str,
    porciones: Mapping[str, int],
    resto: Mapping[str, float],
    pendiente: Mapping[str, float],
) -> int:
    """Porciones asignables respetando demanda, inventario y riesgo pendiente."""
    q = receta.ingredientes
    if not q or ing_id not in q:
        return 0
    tope_demanda = receta.demanda_menu_dia - porciones.get(receta.id, 0)
    if tope_demanda <= 0:
        return 0
    tope_stock = min(floor(resto.get(h, 0.0) / kg + EPS) for h, kg in q.items())
    if tope_stock <= 0:
        return 0
    necesarias = ceil(pendiente[ing_id] / q[ing_id] - EPS)
    return max(0, min(tope_demanda, tope_stock, necesarias))


def llenar(
    estado: Estado,
    variante: str = "base",
    excluidas: Collection[str] = frozenset(),
    permitidas: Collection[str] | None = None,
) -> dict[str, int]:
    """Asigna porciones de forma voraz en dos pasadas (``fijo`` y ``secundaria``).

    Args:
        estado: Estructura precalculada por ``preparar``.
        variante: Nombre de la estrategia en ``VARIANTES``.
        excluidas: Identificadores de recetas que no deben proponerse.
        permitidas: Si no es ``None``, subconjunto exclusivo de recetas que
            pueden considerarse (usado por ejemplo en búsqueda por subconjuntos).

    Returns:
        Diccionario ``{receta_id: porciones}`` solo con entradas ``>= 1``.
    """
    if variante not in VARIANTES:
        raise ValueError(f"variante desconocida: {variante!r}; opciones: {VARIANTES}")

    excluidas_set = excluidas if isinstance(excluidas, (set, frozenset)) else set(excluidas)
    permitidas_set = (
        None
        if permitidas is None
        else (permitidas if isinstance(permitidas, (set, frozenset)) else set(permitidas))
    )

    puntajes = {
        rec_id: _puntaje_receta(rec, variante, estado) for rec_id, rec in estado.recetas.items()
    }
    resto = dict(estado.disponible)
    pendiente = dict(estado.riesgo)
    porciones: dict[str, int] = {}

    for tipo in ("fijo", "secundaria"):
        for ing_id in estado.orden:
            if pendiente.get(ing_id, 0.0) <= EPS:
                continue
            candidatas = [
                rec_id
                for rec_id in estado.usa.get(ing_id, ())
                if estado.recetas[rec_id].tipo == tipo
                and rec_id not in excluidas_set
                and (permitidas_set is None or rec_id in permitidas_set)
            ]
            candidatas.sort(key=lambda rec_id: (-puntajes[rec_id], rec_id))
            for rec_id in candidatas:
                receta = estado.recetas[rec_id]
                x = _porciones_posibles(receta, ing_id, porciones, resto, pendiente)
                if x >= 1:
                    porciones[rec_id] = porciones.get(rec_id, 0) + x
                    for h, kg in receta.ingredientes.items():
                        resto[h] = max(0.0, resto.get(h, 0.0) - x * kg)
                        if h in pendiente:
                            pendiente[h] = max(0.0, pendiente[h] - x * kg)
                if pendiente[ing_id] <= EPS:
                    break

    return porciones
