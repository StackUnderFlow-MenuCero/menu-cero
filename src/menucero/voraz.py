"""Algoritmo voraz para generar propuestas de menú del día (issues #20 y #23).

Implementación independiente de Pandas, Streamlit y de la fecha del sistema.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date
from math import ceil, floor
from time import perf_counter

from menucero.modelos import Ingrediente, MenuGenerado, Receta
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

# (tipo_receta -> (ingrediente_id -> tupla ordenada de receta_id viables))
_CandidatasPorTipo = dict[str, dict[str, tuple[str, ...]]]


def _valores[T](coleccion: Iterable[T] | Mapping[str, T]) -> Iterable[T]:
    if isinstance(coleccion, Mapping):
        return coleccion.values()
    return coleccion


def _a_conjunto(items: Collection[str]) -> set[str] | frozenset[str]:
    if isinstance(items, (set, frozenset)):
        return items
    return set(items)


def _platillo_principal(porciones: Mapping[str, int]) -> str:
    return max(porciones, key=lambda rec_id: (porciones[rec_id], rec_id))


@dataclass(slots=True)
class Estado:
    """Datos precalculados de una instancia para una fecha ``hoy``.

    Attributes:
        ingredientes: Ingredientes vigentes indexados por ``id``.
        recetas: Recetas existentes indexados por ``id``.
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
    _candidatas_cache: dict[str, _CandidatasPorTipo] = field(
        default_factory=dict, init=False, repr=False, compare=False
    )


def preparar(
    ingredientes: Iterable[Ingrediente] | Mapping[str, Ingrediente],
    recetas: Iterable[Receta] | Mapping[str, Receta],
    hoy: date,
) -> Estado:
    """Precalcula urgencias, inventario disponible, riesgo e índice invertido.

    Separa y descarta los ingredientes ya caducados respecto de ``hoy``, deduplica
    entradas por ``id`` y deja lista la estructura ``Estado`` para ejecutar una o
    varias pasadas de llenado sin repetir el preprocesamiento.
    """
    ing_unicos = list({ing.id: ing for ing in _valores(ingredientes)}.values())
    rec_por_id = {rec.id: rec for rec in _valores(recetas)}
    lista_recetas = list(rec_por_id.values())

    vigentes, _ = separar_caducados(ing_unicos, hoy)
    ing_por_id = {ing.id: ing for ing in vigentes}

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
    if not porciones:
        return 0.0

    recetas = estado.recetas
    riesgo = estado.riesgo
    prioridades = estado.p

    usado: dict[str, float] = {}
    for rec_id, x in porciones.items():
        if x <= 0:
            continue
        for ing_id, kg_por_porcion in recetas[rec_id].ingredientes.items():
            if riesgo.get(ing_id, 0.0) > EPS:
                usado[ing_id] = usado.get(ing_id, 0.0) + x * kg_por_porcion

    return sum(
        prioridades[ing_id] * (kg_usado if kg_usado < riesgo[ing_id] else riesgo[ing_id])
        for ing_id, kg_usado in usado.items()
    )


def _clave_criterio(variante: str) -> str:
    if variante in ("base", "sin_principal", "secundarias"):
        return "base"
    if variante in ("economica", "eficiencia"):
        return variante
    raise ValueError(f"variante desconocida: {variante!r}; opciones: {VARIANTES}")


def _puntaje_receta(receta: Receta, criterio: str, estado: Estado) -> float:
    """Calcula el puntaje de ordenamiento de ``receta`` según ``criterio``."""
    riesgo = estado.riesgo
    prioridades = estado.p
    if criterio == "base":
        return sum(
            prioridades[h] * kg for h, kg in receta.ingredientes.items() if riesgo.get(h, 0.0) > EPS
        )
    if criterio == "economica":
        ingredientes = estado.ingredientes
        return sum(
            prioridades[h] * kg * ingredientes[h].costo_kg
            for h, kg in receta.ingredientes.items()
            if riesgo.get(h, 0.0) > EPS
        )
    total_kg = sum(receta.ingredientes.values())
    if total_kg <= EPS:
        return 0.0
    rescate = sum(
        prioridades[h] * kg for h, kg in receta.ingredientes.items() if riesgo.get(h, 0.0) > EPS
    )
    return rescate / total_kg


def _es_receta_viable(receta: Receta, disponible: Mapping[str, float]) -> bool:
    """Indica si ``receta`` puede preparar al menos 1 porción con el stock inicial."""
    if receta.demanda_menu_dia <= 0 or not receta.ingredientes:
        return False
    return all(
        floor(disponible.get(h, 0.0) / kg + EPS) >= 1 for h, kg in receta.ingredientes.items()
    )


def _obtener_candidatas_ordenadas(estado: Estado, variante: str) -> _CandidatasPorTipo:
    """Obtiene (y cachea en ``estado``) las recetas viables ordenadas por ingrediente."""
    criterio = _clave_criterio(variante)
    cacheadas = estado._candidatas_cache.get(criterio)
    if cacheadas is not None:
        return cacheadas

    disponible = estado.disponible
    recetas = estado.recetas
    viables = {rec_id for rec_id, rec in recetas.items() if _es_receta_viable(rec, disponible)}
    puntajes = {rec_id: _puntaje_receta(recetas[rec_id], criterio, estado) for rec_id in viables}

    por_tipo: _CandidatasPorTipo = {"fijo": {}, "secundaria": {}}
    for ing_id in estado.orden:
        por_receta_tipo: dict[str, list[str]] = {"fijo": [], "secundaria": []}
        for rec_id in estado.usa.get(ing_id, ()):
            if rec_id in viables:
                por_receta_tipo[recetas[rec_id].tipo].append(rec_id)
        for tipo, lista in por_receta_tipo.items():
            if lista:
                lista.sort(key=lambda r_id: (-puntajes[r_id], r_id))
                por_tipo[tipo][ing_id] = tuple(lista)

    estado._candidatas_cache[criterio] = por_tipo
    return por_tipo


def _porciones_posibles(
    receta: Receta,
    ing_id: str,
    porciones: Mapping[str, int],
    resto: Mapping[str, float],
    pendiente: Mapping[str, float],
) -> int:
    """Porciones asignables respetando demanda, inventario y riesgo pendiente."""
    q = receta.ingredientes
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
    if not estado.orden:
        return {}

    permitidas_set = None if permitidas is None else _a_conjunto(permitidas)
    if permitidas_set is not None and not permitidas_set:
        return {}
    excluidas_set = _a_conjunto(excluidas) if excluidas else frozenset()

    candidatas_por_tipo = _obtener_candidatas_ordenadas(estado, variante)
    recetas = estado.recetas
    resto = dict(estado.disponible)
    pendiente = dict(estado.riesgo)
    porciones: dict[str, int] = {}

    pasadas = ("secundaria",) if variante == "secundarias" else ("fijo", "secundaria")
    for tipo in pasadas:
        mapa_tipo = candidatas_por_tipo[tipo]
        if not mapa_tipo:
            continue
        for ing_id in estado.orden:
            if pendiente[ing_id] <= EPS:
                continue
            candidatas = mapa_tipo.get(ing_id)
            if not candidatas:
                continue
            for rec_id in candidatas:
                if excluidas_set and rec_id in excluidas_set:
                    continue
                if permitidas_set is not None and rec_id not in permitidas_set:
                    continue
                receta = recetas[rec_id]
                x = _porciones_posibles(receta, ing_id, porciones, resto, pendiente)
                if x >= 1:
                    porciones[rec_id] = porciones.get(rec_id, 0) + x
                    for h, kg in receta.ingredientes.items():
                        resto[h] = max(0.0, resto[h] - x * kg)
                        if h in pendiente:
                            pendiente[h] = max(0.0, pendiente[h] - x * kg)
                    if pendiente[ing_id] <= EPS:
                        break

    return porciones


def generar_menu(
    ingredientes: Iterable[Ingrediente] | Mapping[str, Ingrediente],
    recetas: Iterable[Receta] | Mapping[str, Receta],
    hoy: date,
    variante: str = "base",
    excluidas: Collection[str] = frozenset(),
    permitidas: Collection[str] | None = None,
) -> MenuGenerado:
    """Genera una propuesta de menú del día midiendo su tiempo de ejecución (ms)."""
    t0 = perf_counter()
    estado = preparar(ingredientes, recetas, hoy)
    if variante == "sin_principal" and not excluidas:
        porciones_base = llenar(estado, variante="base", permitidas=permitidas)
        if porciones_base:
            excluidas = frozenset({_platillo_principal(porciones_base)})
    porciones = llenar(estado, variante=variante, excluidas=excluidas, permitidas=permitidas)
    valor = valor_objetivo(porciones, estado)
    tiempo_ms = (perf_counter() - t0) * 1000.0
    return MenuGenerado(variante=variante, porciones=porciones, valor=valor, tiempo_ms=tiempo_ms)


def generar_propuestas(
    ingredientes: Iterable[Ingrediente] | Mapping[str, Ingrediente],
    recetas: Iterable[Receta] | Mapping[str, Receta],
    hoy: date,
    k: int = 5,
) -> list[MenuGenerado]:
    """Genera hasta ``k`` propuestas distintas de menú del día ordenadas por ``V``.

    Prepara el estado una sola vez, evalúa las variantes en ``VARIANTES[:k]``,
    descarta propuestas vacías o con asignaciones de porciones repetidas y
    asigna el tiempo total de generación (ms) a cada propuesta devuelta.
    """
    if k < 1:
        raise ValueError(f"k debe ser al menos 1, no {k}")

    t0 = perf_counter()
    estado = preparar(ingredientes, recetas, hoy)

    propuestas: list[MenuGenerado] = []
    vistas: set[tuple[tuple[str, int], ...]] = set()
    principal: str | None = None

    for variante in VARIANTES[:k]:
        excluidas: frozenset[str] = frozenset()
        if variante == "sin_principal" and principal is not None:
            excluidas = frozenset({principal})

        porciones = llenar(estado, variante=variante, excluidas=excluidas)
        if variante == "base" and porciones:
            principal = _platillo_principal(porciones)

        llave = tuple(sorted(porciones.items()))
        if porciones and llave not in vistas:
            vistas.add(llave)
            valor = valor_objetivo(porciones, estado)
            propuestas.append(MenuGenerado(variante=variante, porciones=porciones, valor=valor))

    tiempo_ms = (perf_counter() - t0) * 1000.0
    for propuesta in propuestas:
        propuesta.tiempo_ms = tiempo_ms

    return sorted(propuestas, key=lambda p: -p.valor)
