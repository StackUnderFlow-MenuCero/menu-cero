"""Días para caducar, prioridad 1/(días + 1), reserva del menú fijo y kg en riesgo.

Implementación del cálculo de urgencias y ordenamiento determinista (issue #12),
sin dependencias de Pandas, Streamlit ni de la fecha del sistema.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date

from menucero.modelos import Ingrediente, Receta


@dataclass(frozen=True, slots=True)
class IngredientePriorizado:
    """Resumen de urgencia de un ingrediente vigente para una fecha ``hoy``.

    Attributes:
        ingrediente: Ingrediente vigente evaluado.
        dias: Días restantes para caducar (0 si caduca hoy).
        prioridad: Prioridad ``1 / (dias + 1)`` en ``(0, 1]``.
        reserva_diaria_kg: Consumo diario del menú fijo (kg/día).
        disponible_hoy_kg: Existencia disponible hoy tras reservar el menú fijo (kg).
        kg_en_riesgo: Cantidad que no se consumirá en el menú fijo antes de caducar (kg).
        valor_en_riesgo: Valor económico en riesgo ``kg_en_riesgo * costo_kg`` (MXN).
    """

    ingrediente: Ingrediente
    dias: int
    prioridad: float
    reserva_diaria_kg: float
    disponible_hoy_kg: float
    kg_en_riesgo: float
    valor_en_riesgo: float


@dataclass(frozen=True, slots=True)
class MermaPerdida:
    """Ingrediente ya caducado en la fecha de referencia (merma ya perdida).

    Attributes:
        ingrediente: Ingrediente caducado excluido del menú.
        dias: Días respecto a ``hoy`` (valor negativo, ej. ``-1`` si caducó ayer).
        cantidad_kg: Cantidad total perdida por caducidad (kg).
        costo_perdido: Valor económico perdido ``cantidad_kg * costo_kg`` (MXN).
    """

    ingrediente: Ingrediente
    dias: int
    cantidad_kg: float
    costo_perdido: float


def dias_para_caducar(ingrediente: Ingrediente, hoy: date) -> int:
    """Calcula los días para caducar respecto a la fecha explícita ``hoy``.

    Retorna ``0`` si caduca hoy, positivo si aún está vigente y negativo si ya
    caducó. Nunca consulta la fecha del sistema.
    """
    return (ingrediente.fecha_caducidad - hoy).days


def prioridad(dias: int) -> float:
    """Calcula la prioridad ``1 / (dias + 1)`` para un ingrediente vigente.

    Ejemplos: ``0 -> 1.0`` (hoy), ``1 -> 0.5`` (mañana), ``7 -> 0.125``.
    Para ``dias < 0`` (caducado) retorna ``0.0``.
    """
    if dias < 0:
        return 0.0
    return 1.0 / (dias + 1)


def _iter_ingredientes(
    ingredientes: Iterable[Ingrediente] | Mapping[str, Ingrediente],
) -> Iterable[Ingrediente]:
    if isinstance(ingredientes, Mapping):
        return ingredientes.values()
    return ingredientes


def _iter_recetas(
    recetas: Iterable[Receta] | Mapping[str, Receta] | None,
) -> Iterable[Receta]:
    if recetas is None:
        return ()
    if isinstance(recetas, Mapping):
        return recetas.values()
    return recetas


def calcular_reserva_fija(
    recetas: Iterable[Receta] | Mapping[str, Receta] | None,
) -> dict[str, float]:
    """Calcula la reserva diaria del menú fijo por ingrediente (kg/día).

    Solo suma las recetas con ``tipo == "fijo"``:
    ``reserva[i] = sum(receta.demanda_fija * kg_por_porcion)``.
    """
    reserva: dict[str, float] = {}
    for receta in _iter_recetas(recetas):
        if receta.tipo != "fijo" or receta.demanda_fija <= 0:
            continue
        for ing_id, kg_por_porcion in receta.ingredientes.items():
            reserva[ing_id] = reserva.get(ing_id, 0.0) + receta.demanda_fija * kg_por_porcion
    return reserva


def kg_disponible_hoy(ingrediente: Ingrediente, reserva_diaria_kg: float = 0.0) -> float:
    """Calcula la existencia disponible hoy tras la reserva del menú fijo (kg)."""
    return max(0.0, ingrediente.cantidad_kg - reserva_diaria_kg)


def kg_en_riesgo(
    ingrediente: Ingrediente,
    dias: int,
    reserva_diaria_kg: float = 0.0,
) -> float:
    """Calcula los kg en riesgo de caducar antes de consumirse en el menú fijo (kg).

    Fórmula: ``max(0.0, cantidad_kg - reserva_diaria_kg * (dias + 1))`` para
    ingredientes vigentes (``dias >= 0``); ``0.0`` si ya caducó.
    """
    if dias < 0:
        return 0.0
    return max(0.0, ingrediente.cantidad_kg - reserva_diaria_kg * (dias + 1))


def ordenar_por_prioridad(
    ingredientes: Iterable[Ingrediente] | Mapping[str, Ingrediente],
    hoy: date,
    recetas: Iterable[Receta] | Mapping[str, Receta] | None = None,
) -> tuple[list[IngredientePriorizado], list[MermaPerdida]]:
    """Separa los ingredientes vigentes de los caducados y ordena por urgencia.

    Los ingredientes ya caducados (``dias < 0``) se excluyen de la lista activa
    y se devuelven en el segundo elemento como merma ya perdida.

    El orden de los vigentes es determinista:
    1. ``prioridad`` descendente (menor ``dias`` primero).
    2. ``valor_en_riesgo`` descendente (``kg_en_riesgo * costo_kg`` en MXN).
    3. ``ingrediente.id`` ascendente.

    Args:
        ingredientes: Colección o mapeo de ingredientes del inventario.
        hoy: Fecha de referencia explícita.
        recetas: Colección o mapeo opcional de recetas para descontar la reserva
            del menú fijo al calcular los kg en riesgo. Si es ``None``, la reserva
            diaria se asume ``0.0``.

    Returns:
        Tupla ``(vigentes_ordenados, merma_perdida)``.
    """
    reserva_por_id = calcular_reserva_fija(recetas)
    vigentes: list[IngredientePriorizado] = []
    caducados: list[MermaPerdida] = []

    for ing in _iter_ingredientes(ingredientes):
        dias = dias_para_caducar(ing, hoy)
        if dias < 0:
            caducados.append(
                MermaPerdida(
                    ingrediente=ing,
                    dias=dias,
                    cantidad_kg=ing.cantidad_kg,
                    costo_perdido=ing.cantidad_kg * ing.costo_kg,
                )
            )
            continue

        reserva = reserva_por_id.get(ing.id, 0.0)
        riesgo = kg_en_riesgo(ing, dias, reserva)
        vigentes.append(
            IngredientePriorizado(
                ingrediente=ing,
                dias=dias,
                prioridad=prioridad(dias),
                reserva_diaria_kg=reserva,
                disponible_hoy_kg=kg_disponible_hoy(ing, reserva),
                kg_en_riesgo=riesgo,
                valor_en_riesgo=riesgo * ing.costo_kg,
            )
        )

    vigentes.sort(key=lambda item: (-item.prioridad, -item.valor_en_riesgo, item.ingrediente.id))
    caducados.sort(key=lambda item: (item.dias, -item.costo_perdido, item.ingrediente.id))
    return vigentes, caducados
