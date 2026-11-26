"""Estructuras de datos del algoritmo: Ingrediente, Receta y MenuGenerado.

Modelos independientes de Pandas y de Streamlit (issue #11).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

TIPOS = ("fijo", "secundaria")


@dataclass(frozen=True, slots=True)
class Ingrediente:
    """Un ingrediente perecedero en existencia (inmutable).

    Attributes:
        id: Identificador único del ingrediente (ej. ``"ING01"``).
        nombre: Nombre descriptivo del ingrediente.
        cantidad_kg: Existencia disponible en inventario (kg).
        fecha_caducidad: Último día utilizable del ingrediente.
        costo_kg: Costo de compra por kilogramo (MXN/kg).
    """

    id: str
    nombre: str
    cantidad_kg: float
    fecha_caducidad: date
    costo_kg: float

    def __post_init__(self) -> None:
        if self.cantidad_kg < 0:
            raise ValueError(f"{self.id}: cantidad_kg no puede ser negativa")
        if self.costo_kg < 0:
            raise ValueError(f"{self.id}: costo_kg no puede ser negativo")


@dataclass(frozen=True, slots=True)
class Receta:
    """Un platillo y los kg de cada ingrediente por porción (inmutable).

    Attributes:
        id: Identificador único de la receta (ej. ``"REC01"``).
        platillo: Nombre del platillo.
        tipo: ``"fijo"`` (en la carta) o ``"secundaria"`` (solo como menú del día).
        ingredientes: Mapeo ``{ingrediente_id: kg_por_porcion}`` en kg/porción.
            Regla del equipo: no modificar este diccionario tras la construcción.
        demanda_fija: Porciones vendidas al día con el menú fijo (porciones/día).
        demanda_menu_dia: Porciones adicionales máximas al día si sale como menú
            del día (porciones/día).
    """

    id: str
    platillo: str
    tipo: str
    ingredientes: dict[str, float]
    demanda_fija: int = 0
    demanda_menu_dia: int = 0

    def __post_init__(self) -> None:
        if self.tipo not in TIPOS:
            raise ValueError(f"{self.id}: tipo debe ser fijo o secundaria, no {self.tipo!r}")
        if any(kg <= 0 for kg in self.ingredientes.values()):
            raise ValueError(f"{self.id}: kg por porción debe ser mayor que 0")
        if self.demanda_fija < 0 or self.demanda_menu_dia < 0:
            raise ValueError(f"{self.id}: la demanda no puede ser negativa")


@dataclass(slots=True)
class MenuGenerado:
    """Una propuesta de menú del día generada por el algoritmo o armada a mano.

    Attributes:
        variante: Nombre de la variante o estrategia (ej. ``"base"``).
        porciones: Mapeo ``{receta_id: porciones}`` del menú del día (porciones/día).
        valor: Valor de la función objetivo ``V`` de la propuesta (kg ponderados).
        tiempo_ms: Tiempo de ejecución empleado para generar la propuesta (ms).
        orden_uso: Plan ordenado de uso de ingredientes (llenado por ``metricas``).
        metricas: Métricas de aprovechamiento y costo en MXN (llenado por ``metricas``).
    """

    variante: str
    porciones: dict[str, int]
    valor: float = 0.0
    tiempo_ms: float = 0.0
    orden_uso: list[Any] = field(default_factory=list)
    metricas: dict[str, Any] = field(default_factory=dict)

    @property
    def total_porciones(self) -> int:
        """Suma total de porciones asignadas en la propuesta (porciones/día)."""
        return sum(self.porciones.values())
