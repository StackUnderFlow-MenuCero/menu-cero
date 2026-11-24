"""Días para caducar, prioridad 1/(días + 1), reserva del menú fijo y kg en riesgo.

Implementación pura sobre los modelos de ``menucero.modelos`` (issue #12),
sin dependencias de Pandas, Streamlit ni de la fecha del sistema.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date

from menucero.modelos import Ingrediente, Receta


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


def dias_para_caducar(ingrediente: Ingrediente, hoy: date) -> int:
    """Días desde ``hoy`` hasta la fecha de caducidad del ingrediente.

    Retorna ``0`` si vence hoy, positivo si sigue vigente y negativo si ya
    caducó. Nunca consulta la fecha del sistema.
    """
    return (ingrediente.fecha_caducidad - hoy).days


def prioridad(dias: int) -> float:
    """Prioridad ``1 / (días + 1)`` para un ingrediente vigente.

    Ejemplos: hoy (``0``) -> ``1.0``, mañana (``1``) -> ``0.5``,
    en 7 días (``7``) -> ``0.125``.

    Raises:
        ValueError: Si ``dias < 0`` (ingrediente ya caducado).
    """
    if dias < 0:
        raise ValueError("un ingrediente caducado no tiene prioridad")
    return 1.0 / (dias + 1)


def separar_caducados(
    ingredientes: Iterable[Ingrediente] | Mapping[str, Ingrediente],
    hoy: date,
) -> tuple[list[Ingrediente], list[Ingrediente]]:
    """Separa los ingredientes en ``(vigentes, caducados)`` conservando el orden.

    Los ingredientes con ``dias_para_caducar(ing, hoy) < 0`` se clasifican como
    caducados (merma ya perdida) y quedan excluidos de ``vigentes``.
    """
    vigentes: list[Ingrediente] = []
    caducados: list[Ingrediente] = []
    for ing in _iter_ingredientes(ingredientes):
        if dias_para_caducar(ing, hoy) < 0:
            caducados.append(ing)
        else:
            vigentes.append(ing)
    return vigentes, caducados


def ordenar_por_prioridad(
    ingredientes: Iterable[Ingrediente] | Mapping[str, Ingrediente],
    hoy: date,
    riesgo: dict[str, float] | None = None,
) -> list[Ingrediente]:
    """Devuelve los ingredientes vigentes ordenados de mayor a menor prioridad.

    Excluye los ingredientes ya caducados. El desempate es determinista:
    1. ``prioridad`` descendente.
    2. Valor en riesgo descendente (``riesgo[id] * costo_kg`` en MXN si se
       proporciona ``riesgo``; en caso contrario, valor del inventario
       ``cantidad_kg * costo_kg``).
    3. ``id`` ascendente.
    """
    vigentes, _ = separar_caducados(ingredientes, hoy)

    def _clave(ing: Ingrediente) -> tuple[float, float, str]:
        p = prioridad(dias_para_caducar(ing, hoy))
        kg = riesgo.get(ing.id, 0.0) if riesgo is not None else ing.cantidad_kg
        return (-p, -(kg * ing.costo_kg), ing.id)

    return sorted(vigentes, key=_clave)


def reserva_diaria(
    recetas: Iterable[Receta] | Mapping[str, Receta],
) -> dict[str, float]:
    """Kg por día que consume el menú fijo por ingrediente (kg/día).

    Calcula ``sum(demanda_fija * kg_por_porcion)`` considerando únicamente las
    recetas con ``tipo == "fijo"``.
    """
    reserva: dict[str, float] = {}
    for receta in _iter_recetas(recetas):
        if receta.tipo != "fijo" or receta.demanda_fija <= 0:
            continue
        for ing_id, kg_por_porcion in receta.ingredientes.items():
            reserva[ing_id] = reserva.get(ing_id, 0.0) + receta.demanda_fija * kg_por_porcion
    return reserva


def kg_en_riesgo(
    ingredientes: Iterable[Ingrediente] | Mapping[str, Ingrediente],
    recetas: Iterable[Receta] | Mapping[str, Receta],
    hoy: date,
) -> dict[str, float]:
    """Calcula ``max(0.0, cantidad_kg - reserva * (d + 1))`` por ingrediente (kg).

    Para ingredientes ya caducados (``d < 0``) devuelve ``0.0``, pues ya se
    cuentan como merma perdida.
    """
    reserva = reserva_diaria(recetas)
    resultado: dict[str, float] = {}
    for ing in _iter_ingredientes(ingredientes):
        d = dias_para_caducar(ing, hoy)
        if d < 0:
            resultado[ing.id] = 0.0
        else:
            resultado[ing.id] = max(0.0, ing.cantidad_kg - reserva.get(ing.id, 0.0) * (d + 1))
    return resultado
