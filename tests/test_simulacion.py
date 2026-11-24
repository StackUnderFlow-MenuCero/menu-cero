"""Pruebas del simulador de los escenarios A y B (#25)."""

import csv
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import pytest

from menucero.simulacion import simular

EJEMPLO = Path(__file__).resolve().parents[1] / "data" / "ejemplo"
HOY = date(2026, 11, 17)


# Mismos campos que modelos.py en el contrato (#11). Cuando #11 esté en main,
# estas clases se reemplazan por las de menucero.modelos.
@dataclass(frozen=True)
class Ingrediente:
    id: str
    nombre: str
    cantidad_kg: float
    fecha_caducidad: date
    costo_kg: float


@dataclass
class Receta:
    id: str
    platillo: str
    tipo: str
    ingredientes: dict[str, float] = field(default_factory=dict)
    demanda_fija: int = 0
    demanda_menu_dia: int = 0


def leer_ejemplo() -> tuple[list[Ingrediente], list[Receta]]:
    """Lee data/ejemplo sin validar (la carga con validación es #13)."""
    with open(EJEMPLO / "inventario.csv", encoding="utf-8") as f:
        ingredientes = [
            Ingrediente(
                r["ingrediente_id"],
                r["nombre"],
                float(r["cantidad_kg"]),
                date.fromisoformat(r["fecha_caducidad"]),
                float(r["costo_kg"]),
            )
            for r in csv.DictReader(f)
        ]
    recetas: dict[str, Receta] = {}
    with open(EJEMPLO / "recetas.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            receta = recetas.setdefault(
                r["receta_id"], Receta(r["receta_id"], r["platillo"], r["tipo"])
            )
            receta.ingredientes[r["ingrediente_id"]] = float(r["kg_por_porcion"])
    with open(EJEMPLO / "demanda.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            recetas[r["receta_id"]].demanda_fija = int(r["demanda_fija"])
            recetas[r["receta_id"]].demanda_menu_dia = int(r["demanda_menu_dia"])
    return ingredientes, list(recetas.values())


def dia(n: int) -> date:
    return HOY + timedelta(days=n)


def pedidas(resultado) -> list[dict[str, int]]:
    """Porciones fijas que pidieron los clientes cada día (servidas + no atendidas)."""
    return [
        {j: x + r["no_atendidas"].get(j, 0) for j, x in r["porciones_fijas"].items()}
        for r in resultado.consumo_diario
    ]


def test_menu_fijo_calculado_a_mano():
    # 2 kg que se usan hasta mañana; el menú fijo gasta 0.5 kg por día.
    ingredientes = [Ingrediente("I1", "Crema", 2.0, dia(1), 10.0)]
    recetas = [Receta("R1", "Enchiladas", "fijo", {"I1": 0.1}, demanda_fija=5)]

    res = simular(ingredientes, recetas, HOY, dias=3)

    assert [r["consumo_kg"] for r in res.consumo_diario] == [
        {"I1": pytest.approx(0.5)},
        {"I1": pytest.approx(0.5)},
        {},
    ]
    assert res.consumo_diario[1]["merma_kg"] == {"I1": pytest.approx(1.0)}
    assert res.merma_kg == {"I1": pytest.approx(1.0)}
    assert res.merma_costo == pytest.approx(10.0)
    assert res.porciones_no_atendidas == 5  # el día 3 ya no hay crema
    assert res.menus == []


def test_sin_ingredientes_en_riesgo_a_y_b_tienen_la_misma_merma():
    ingredientes = [
        Ingrediente("I1", "Crema", 1.0, dia(1), 70.0),  # el menú fijo la acaba justo
        Ingrediente("I2", "Papa", 4.0, dia(20), 35.0),
        Ingrediente("I3", "Lechuga", 0.3, dia(-1), 20.0),  # ya caducada al empezar
    ]
    recetas = [
        Receta("R1", "Enchiladas", "fijo", {"I1": 0.1}, demanda_fija=5),
        Receta("R2", "Papas", "fijo", {"I2": 0.2}, demanda_fija=2),
        Receta("R3", "Crema de papa", "secundaria", {"I1": 0.1, "I2": 0.1}, demanda_menu_dia=10),
    ]

    a = simular(ingredientes, recetas, HOY, escenario="A")
    b = simular(ingredientes, recetas, HOY, escenario="B")

    assert a.merma_kg == b.merma_kg == {"I1": 0.0, "I2": 0.0, "I3": pytest.approx(0.3)}
    assert a.merma_costo == b.merma_costo == pytest.approx(6.0)
    assert all(not m for m in b.menus)


def test_el_menu_fijo_va_antes_que_el_menu_del_dia():
    ingredientes = [Ingrediente("I1", "Pollo", 3.0, dia(0), 120.0)]
    recetas = [
        Receta("R1", "Pollo asado", "fijo", {"I1": 0.2}, demanda_fija=10),
        Receta("R2", "Tinga", "secundaria", {"I1": 0.1}, demanda_menu_dia=50),
    ]

    def voraz_gloton(ingredientes, recetas, hoy):
        return {"R2": 50}  # pide mucho más de lo que hay

    b = simular(ingredientes, recetas, HOY, dias=1, escenario="B", generador=voraz_gloton)

    registro = b.consumo_diario[0]
    assert registro["porciones_fijas"] == {"R1": 10}
    assert registro["porciones_menu_dia"] == {"R2": 10}  # solo lo que quedó: 1 kg
    assert b.porciones_no_atendidas == 0
    assert b.merma_kg == {"I1": 0.0}


def test_el_voraz_recibe_el_inventario_de_cada_dia():
    ingredientes = [Ingrediente("I1", "Pollo", 3.0, dia(5), 120.0)]
    recetas = [Receta("R1", "Pollo asado", "fijo", {"I1": 0.5}, demanda_fija=2)]
    vistos = []

    def espia(ingredientes, recetas, hoy):
        vistos.append((hoy, ingredientes[0].cantidad_kg))
        return {}

    simular(ingredientes, recetas, HOY, dias=3, escenario="B", generador=espia)
    assert vistos == [(dia(0), 3.0), (dia(1), 2.0), (dia(2), 1.0)]


def test_acepta_un_menu_generado_con_porciones():
    @dataclass
    class MenuGenerado:
        variante: str
        porciones: dict[str, int]

    ingredientes = [Ingrediente("I1", "Pollo", 3.0, dia(0), 120.0)]
    recetas = [Receta("R2", "Tinga", "secundaria", {"I1": 0.1}, demanda_menu_dia=50)]
    b = simular(
        ingredientes,
        recetas,
        HOY,
        dias=1,
        escenario="B",
        generador=lambda *_: MenuGenerado("base", {"R2": 30}),
    )
    assert b.menus == [{"R2": 30}]
    assert b.merma_kg == {"I1": 0.0}


def test_con_el_ejemplo_b_reduce_la_merma_de_a():
    ingredientes, recetas = leer_ejemplo()
    a = simular(ingredientes, recetas, HOY, escenario="A")
    b = simular(ingredientes, recetas, HOY, escenario="B")

    assert a.merma_total_kg == pytest.approx(21.79, abs=0.005)
    assert b.merma_total_kg < a.merma_total_kg
    assert b.merma_costo < a.merma_costo
    assert len(b.menus) == 7
    assert b.menus[0]  # el primer día hay ingredientes en riesgo


@pytest.mark.parametrize("escenario", ["A", "B"])
def test_sin_reposicion_lo_inicial_es_consumo_mas_merma_mas_lo_que_queda(escenario):
    ingredientes, recetas = leer_ejemplo()
    res = simular(ingredientes, recetas, HOY, escenario=escenario, semilla=3, ruido=True)
    for ing in ingredientes:
        consumo = sum(r["consumo_kg"].get(ing.id, 0.0) for r in res.consumo_diario)
        final = res.inventario_final[ing.id]
        assert consumo + res.merma_kg[ing.id] + final == pytest.approx(ing.cantidad_kg)
        assert final >= 0


def test_el_ruido_se_repite_con_la_misma_semilla():
    ingredientes, recetas = leer_ejemplo()
    uno = simular(ingredientes, recetas, HOY, escenario="B", semilla=7, ruido=True)
    otro = simular(ingredientes, recetas, HOY, escenario="B", semilla=7, ruido=True)
    distinto = simular(ingredientes, recetas, HOY, escenario="B", semilla=8, ruido=True)

    assert uno == otro
    assert pedidas(uno) != pedidas(distinto)


def test_a_y_b_ven_los_mismos_clientes_con_la_misma_semilla():
    ingredientes, recetas = leer_ejemplo()
    a = simular(ingredientes, recetas, HOY, escenario="A", semilla=11, ruido=True)
    b = simular(ingredientes, recetas, HOY, escenario="B", semilla=11, ruido=True)
    assert pedidas(a) == pedidas(b)
    assert pedidas(a) != pedidas(simular(ingredientes, recetas, HOY, escenario="A"))


@pytest.mark.parametrize(
    ("kwargs", "mensaje"), [({"escenario": "C"}, "escenario"), ({"dias": 0}, "dias")]
)
def test_rechaza_parametros_invalidos(kwargs, mensaje):
    ingredientes, recetas = leer_ejemplo()
    with pytest.raises(ValueError, match=mensaje):
        simular(ingredientes, recetas, HOY, **kwargs)
