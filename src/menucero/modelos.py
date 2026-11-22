"""Estructuras de datos del algoritmo: Ingrediente, Receta y MenuGenerado."""

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True, slots=True)
class Ingrediente:
    id: str
    nombre: str
    cantidad_kg: float
    fecha_caducidad: date
    costo_kg: float


@dataclass(frozen=True, slots=True)
class Receta:
    id: str
    platillo: str
    tipo: str  # "fijo" | "secundaria"
    ingredientes: dict[str, float]  # ingrediente_id -> kg por porción
    demanda_fija: int = 0
    demanda_menu_dia: int = 0


@dataclass(slots=True)
class MenuGenerado:
    variante: str
    porciones: dict[str, int]  # receta_id -> porciones del menú del día
    valor: float = 0.0
    tiempo_ms: float = 0.0
    orden_uso: list = field(default_factory=list)
    metricas: dict = field(default_factory=dict)
