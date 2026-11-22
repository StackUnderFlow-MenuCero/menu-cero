"""Días para caducar, prioridad 1/(días + 1), reserva del menú fijo y kg en riesgo."""

from datetime import date

from menucero.modelos import Ingrediente, Receta


def dias_para_caducar(ingrediente: Ingrediente, hoy: date) -> int:
    return (ingrediente.fecha_caducidad - hoy).days


def prioridad(dias: int) -> float:
    if dias < 0:
        return 0.0
    return 1.0 / (dias + 1)


def ordenar_por_prioridad(
    ingredientes: list[Ingrediente],
    hoy: date,
    riesgo: dict[str, float] | None = None,
) -> list[Ingrediente]:
    def _clave(ing: Ingrediente):
        d = dias_para_caducar(ing, hoy)
        r = riesgo.get(ing.id, 0.0) if riesgo is not None else 0.0
        # Menor días primero, mayor riesgo después y desempate por id.
        return (d, -r, ing.id)

    return sorted(ingredientes, key=_clave)


def reserva_diaria(recetas: list[Receta]) -> dict[str, float]:
    reserva: dict[str, float] = {}
    for receta in recetas:
        if receta.tipo == "fijo" and receta.demanda_fija > 0:
            for ing_id, kg_por_porcion in receta.ingredientes.items():
                reserva[ing_id] = reserva.get(ing_id, 0.0) + (receta.demanda_fija * kg_por_porcion)
    return reserva


def kg_en_riesgo(
    ingredientes: list[Ingrediente],
    recetas: list[Receta],
    hoy: date,
) -> dict[str, float]:
    reservas = reserva_diaria(recetas)
    en_riesgo: dict[str, float] = {}
    for ing in ingredientes:
        d = dias_para_caducar(ing, hoy)
        if d < 0:
            en_riesgo[ing.id] = 0.0
            continue
        res_dia = reservas.get(ing.id, 0.0)
        uso_antes_vencer = res_dia * (d + 1)
        en_riesgo[ing.id] = max(0.0, ing.cantidad_kg - uso_antes_vencer)
    return en_riesgo
