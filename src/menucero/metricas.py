"""Métricas de aprovechamiento por propuesta y de evaluación A vs B."""

from dataclasses import dataclass
from datetime import date

from menucero.modelos import Ingrediente, MenuGenerado, Receta
from menucero.prioridad import dias_para_caducar, kg_en_riesgo

EPS = 1e-9


@dataclass(frozen=True, slots=True)
class UsoIngrediente:
    ingrediente_id: str
    nombre: str
    dias: int
    kg_a_usar: float
    platillos: tuple[str, ...]


def _consumo_y_platillos(
    menu: MenuGenerado,
    recetas: list[Receta],
) -> tuple[dict[str, float], dict[str, list[str]]]:
    recetas_por_id = {r.id: r for r in recetas}
    usado: dict[str, float] = {}
    platillos_por_ing: dict[str, list[str]] = {}

    for rec_id, porciones in menu.porciones.items():
        if porciones <= 0:
            continue
        receta = recetas_por_id.get(rec_id)
        if receta is None:
            continue
        for ing_id, kg_porcion in receta.ingredientes.items():
            kg_total = porciones * kg_porcion
            if kg_total > EPS:
                usado[ing_id] = usado.get(ing_id, 0.0) + kg_total
                lista_platillos = platillos_por_ing.setdefault(ing_id, [])
                if receta.platillo not in lista_platillos:
                    lista_platillos.append(receta.platillo)

    return usado, platillos_por_ing


def orden_de_uso(
    menu: MenuGenerado,
    ingredientes: list[Ingrediente],
    recetas: list[Receta],
    hoy: date,
) -> list[UsoIngrediente]:
    """Devuelve los ingredientes usados ordenados por urgencia (días asc., luego id)."""
    usado, platillos_por_ing = _consumo_y_platillos(menu, recetas)
    ing_por_id = {ing.id: ing for ing in ingredientes}

    items: list[tuple[int, str, UsoIngrediente]] = []
    for ing_id, kg_total in usado.items():
        ing = ing_por_id.get(ing_id)
        if ing is None:
            continue
        dias = dias_para_caducar(ing, hoy)
        uso = UsoIngrediente(
            ingrediente_id=ing.id,
            nombre=ing.nombre,
            dias=dias,
            kg_a_usar=kg_total,
            platillos=tuple(platillos_por_ing.get(ing_id, [])),
        )
        items.append((dias, ing.id, uso))

    items.sort(key=lambda tupla: (tupla[0], tupla[1]))
    return [uso for _, _, uso in items]


def metricas_propuesta(
    menu: MenuGenerado,
    ingredientes: list[Ingrediente],
    recetas: list[Receta],
    hoy: date,
) -> dict[str, float]:
    """Calcula métricas de aprovechamiento en riesgo y volumen para una propuesta."""
    riesgo_por_ing = kg_en_riesgo(ingredientes, recetas, hoy)
    usado_por_ing, _ = _consumo_y_platillos(menu, recetas)
    costo_por_ing = {ing.id: ing.costo_kg for ing in ingredientes}

    total_riesgo = sum(riesgo_por_ing.values())
    total_rescatado = 0.0
    total_costo_recuperado = 0.0

    for ing_id, riesgo_kg in riesgo_por_ing.items():
        usado_kg = usado_por_ing.get(ing_id, 0.0)
        rescatado_kg = min(usado_kg, riesgo_kg)
        total_rescatado += rescatado_kg
        total_costo_recuperado += costo_por_ing.get(ing_id, 0.0) * rescatado_kg

    pct_aprovechamiento = 0.0 if total_riesgo <= EPS else 100.0 * total_rescatado / total_riesgo

    porciones_totales = float(sum(p for p in menu.porciones.values() if p > 0))
    platillos_activos = float(sum(1 for p in menu.porciones.values() if p > 0))

    return {
        "kg_en_riesgo": total_riesgo,
        "kg_rescatados": total_rescatado,
        "pct_aprovechamiento": pct_aprovechamiento,
        "costo_recuperado": total_costo_recuperado,
        "porciones": porciones_totales,
        "platillos": platillos_activos,
    }


def desperdicio_evitado(
    merma_a: dict[str, float],
    merma_b: dict[str, float],
) -> float | None:
    """Porcentaje de desperdicio evitado de B frente a A; None si merma_a es 0."""
    total_a = sum(merma_a.values())
    if abs(total_a) <= EPS:
        return None
    total_b = sum(merma_b.values())
    return 100.0 * (total_a - total_b) / total_a


def costo_ahorrado(
    merma_a: dict[str, float],
    merma_b: dict[str, float],
    costos: dict[str, float],
) -> float:
    """Ahorro monetario por reducción de merma entre escenario A y B."""
    ids = set(merma_a.keys()) | set(merma_b.keys())
    return sum(
        costos.get(ing_id, 0.0) * (merma_a.get(ing_id, 0.0) - merma_b.get(ing_id, 0.0))
        for ing_id in ids
    )
