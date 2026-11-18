"""Estructuras de datos del algoritmo: Ingrediente, Receta y MenuGenerado.

Modelos independientes de Pandas y de Streamlit (issue #11).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

TipoReceta = Literal["fijo", "secundaria"]


@dataclass(frozen=True, slots=True)
class Ingrediente:
    """Ingrediente perecedero disponible en el inventario (inmutable).

    Attributes:
        id: Identificador único del ingrediente (ej. ``"ING01"``).
        nombre: Nombre descriptivo del ingrediente.
        cantidad_kg: Existencia actual en inventario (kg).
        fecha_caducidad: Último día en que el ingrediente puede usarse.
        costo_kg: Costo de compra por kilogramo (MXN/kg).
    """

    id: str
    nombre: str
    cantidad_kg: float
    fecha_caducidad: date
    costo_kg: float


@dataclass(slots=True)
class Receta:
    """Receta de un platillo con sus ingredientes y demanda diaria estimada.

    Attributes:
        id: Identificador único de la receta (ej. ``"REC01"``).
        platillo: Nombre del platillo.
        tipo: ``"fijo"`` si pertenece a la carta fija o ``"secundaria"`` si solo
            se ofrece como menú del día.
        ingredientes: Mapeo ``{ingrediente_id: kg_por_porcion}`` con la cantidad
            requerida de cada ingrediente por porción (kg/porción).
        demanda_fija: Porciones vendidas al día en el menú fijo (porciones/día).
        demanda_menu_dia: Porciones adicionales máximas estimadas si se promueve
            como menú del día (porciones/día).
    """

    id: str
    platillo: str
    tipo: TipoReceta
    ingredientes: dict[str, float] = field(default_factory=dict)
    demanda_fija: int = 0
    demanda_menu_dia: int = 0


@dataclass(slots=True)
class MenuGenerado:
    """Propuesta de menú del día generada por el algoritmo o armada manualmente.

    Attributes:
        variante: Nombre de la variante o estrategia que originó la propuesta
            (ej. ``"base"``, ``"sin_principal"``, ``"secundarias"``).
        porciones: Mapeo ``{receta_id: porciones}`` con las porciones asignadas a
            cada receta (porciones/día).
        orden_uso: Secuencia ordenada con el plan de uso de ingredientes
            priorizados (ingrediente, urgencia, kg y platillos que lo usan).
        metricas: Diccionario de métricas agregadas de aprovechamiento y costo
            (kg en riesgo, kg rescatados, % de aprovechamiento, costo en MXN).
        tiempo_ms: Tiempo de ejecución empleado para generar la propuesta (ms).
    """

    variante: str
    porciones: dict[str, int] = field(default_factory=dict)
    orden_uso: list[Any] = field(default_factory=list)
    metricas: dict[str, Any] = field(default_factory=dict)
    tiempo_ms: float = 0.0
