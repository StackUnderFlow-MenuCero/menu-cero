"""Pruebas del algoritmo voraz principal (issue #20)."""

import ast
import csv
import random
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import pytest

from menucero.modelos import Ingrediente, Receta
from menucero.voraz import VARIANTES, generar_menu, llenar, preparar, valor_objetivo

EJEMPLO = Path(__file__).resolve().parents[1] / "data" / "ejemplo"


def _cargar_carpeta(carpeta: Path) -> tuple[list[Ingrediente], list[Receta]]:
    with open(carpeta / "inventario.csv", encoding="utf-8-sig", newline="") as f:
        ingredientes = [
            Ingrediente(
                id=row["ingrediente_id"],
                nombre=row["nombre"],
                cantidad_kg=float(row["cantidad_kg"]),
                fecha_caducidad=date.fromisoformat(row["fecha_caducidad"]),
                costo_kg=float(row["costo_kg"]),
            )
            for row in csv.DictReader(f)
        ]

    agrupadas: dict[str, dict[str, object]] = {}
    with open(carpeta / "recetas.csv", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            info = agrupadas.setdefault(
                row["receta_id"],
                {"platillo": row["platillo"], "tipo": row["tipo"], "q": {}},
            )
            info["q"][row["ingrediente_id"]] = float(row["kg_por_porcion"])  # type: ignore[index]

    with open(carpeta / "demanda.csv", encoding="utf-8-sig", newline="") as f:
        demanda = {
            row["receta_id"]: (int(row["demanda_fija"]), int(row["demanda_menu_dia"]))
            for row in csv.DictReader(f)
        }

    recetas = [
        Receta(
            id=rec_id,
            platillo=str(info["platillo"]),
            tipo=str(info["tipo"]),
            ingredientes=info["q"],  # type: ignore[arg-type]
            demanda_fija=demanda[rec_id][0],
            demanda_menu_dia=demanda[rec_id][1],
        )
        for rec_id, info in agrupadas.items()
    ]
    return ingredientes, recetas


def _instancia_aleatoria(rng: random.Random, hoy: date) -> tuple[list[Ingrediente], list[Receta]]:
    n_ing = rng.randint(5, 16)
    m_rec = rng.randint(3, 9)
    ids_ing = [f"ING{k + 1:02d}" for k in range(n_ing)]

    ingredientes = [
        Ingrediente(
            id=ing_id,
            nombre=f"Ingrediente {ing_id}",
            cantidad_kg=round(rng.uniform(0.0, 12.0), 2),
            fecha_caducidad=hoy + timedelta(days=rng.randint(-2, 10)),
            costo_kg=round(rng.uniform(20.0, 200.0), 2),
        )
        for ing_id in ids_ing
    ]

    recetas: list[Receta] = []
    for j in range(m_rec):
        tipo = "fijo" if rng.random() < 0.7 else "secundaria"
        k_ing = rng.randint(1, min(5, n_ing))
        elegidos = rng.sample(ids_ing, k_ing)
        q = {ing_id: round(rng.uniform(0.02, 0.25), 3) for ing_id in elegidos}
        fija = rng.randint(0, 15) if tipo == "fijo" else 0
        menu_dia = rng.randint(0, 15)
        recetas.append(
            Receta(
                id=f"REC{j + 1:02d}",
                platillo=f"Platillo {j + 1}",
                tipo=tipo,
                ingredientes=q,
                demanda_fija=fija,
                demanda_menu_dia=menu_dia,
            )
        )
    return ingredientes, recetas


def test_constante_variantes():
    assert VARIANTES == ("base", "sin_principal", "economica", "eficiencia", "secundarias")


def test_preparar_ejemplo_de_referencia(ingredientes, recetas, hoy):
    estado = preparar(ingredientes, recetas, hoy)

    assert set(estado.ingredientes) == {"ING01", "ING02", "ING03", "ING04", "ING05"}
    assert set(estado.recetas) == {"REC01", "REC02", "REC03", "REC07"}
    assert estado.p == pytest.approx(
        {
            "ING01": 0.5,
            "ING02": 1 / 3,
            "ING03": 0.2,
            "ING04": 0.25,
            "ING05": 1 / 3,
        }
    )
    assert estado.disponible == pytest.approx(
        {
            "ING01": 1.58,
            "ING02": 1.41,
            "ING03": 6.95,
            "ING04": 3.27,
            "ING05": 2.00,
        }
    )
    assert estado.riesgo == pytest.approx(
        {
            "ING01": 1.16,
            "ING02": 1.23,
            "ING03": 2.75,
            "ING04": 0.0,
            "ING05": 0.0,
        }
    )
    assert estado.orden == ["ING01", "ING02", "ING03"]
    assert set(estado.usa["ING01"]) == {"REC01", "REC03", "REC07"}
    assert set(estado.usa["ING05"]) == {"REC02"}


def test_preparar_excluye_caducados_y_acepta_diccionarios(ingredientes, recetas):
    hoy_18 = date(2026, 11, 18)
    ing_dict = {i.id: i for i in ingredientes}
    rec_dict = {r.id: r for r in recetas}

    estado = preparar(ing_dict, rec_dict, hoy_18)

    assert "ING01" not in estado.ingredientes
    assert "ING01" not in estado.disponible
    assert "ING01" not in estado.riesgo
    assert "ING01" not in estado.orden


def test_preparar_recorta_disponible_a_cero_si_reserva_supera_stock():
    hoy = date(2026, 11, 16)
    ing = [Ingrediente("ING01", "Crema", 0.20, date(2026, 11, 17), 70.0)]
    rec = [Receta("REC01", "Pollo", "fijo", {"ING01": 0.10}, demanda_fija=5, demanda_menu_dia=5)]

    estado = preparar(ing, rec, hoy)
    assert estado.disponible["ING01"] == 0.0
    assert estado.riesgo["ING01"] == 0.0
    assert estado.orden == []


def test_valor_objetivo_vacio_y_ejemplo_base(ingredientes, recetas, hoy):
    estado = preparar(ingredientes, recetas, hoy)

    assert valor_objetivo({}, estado) == 0.0
    assert valor_objetivo({"REC01": 0}, estado) == 0.0

    v = valor_objetivo({"REC01": 12, "REC03": 10, "REC07": 10}, estado)
    assert v == pytest.approx(1.51667, abs=1e-5)


def test_llenar_traza_ejemplo_de_referencia(ingredientes, recetas, hoy):
    estado = preparar(ingredientes, recetas, hoy)
    porciones = llenar(estado, variante="base")

    assert porciones == {"REC01": 12, "REC03": 10, "REC07": 10}
    assert valor_objetivo(porciones, estado) == pytest.approx(1.51667, abs=1e-5)


def test_llenar_respeta_permitidas_y_excluidas(ingredientes, recetas, hoy):
    estado = preparar(ingredientes, recetas, hoy)

    assert llenar(estado, permitidas={"REC03"}) == {"REC03": 10}
    assert llenar(estado, permitidas=set()) == {}
    assert llenar(estado, excluidas={"REC01"}) == {"REC03": 10, "REC07": 10}


def test_llenar_ignora_demanda_cero_e_ingredientes_faltantes_o_caducados(hoy):
    ingredientes = [
        Ingrediente("ING01", "Crema", 2.0, date(2026, 11, 17), 70.0),
        Ingrediente("ING_CAD", "Leche", 1.0, date(2026, 11, 15), 30.0),
    ]
    recetas = [
        Receta("REC_CERO", "Salsa", "fijo", {"ING01": 0.10}, demanda_fija=0, demanda_menu_dia=0),
        Receta(
            "REC_FALTA",
            "Pasta",
            "fijo",
            {"ING01": 0.10, "ING_NO_EXISTE": 0.20},
            demanda_fija=0,
            demanda_menu_dia=10,
        ),
        Receta(
            "REC_CAD",
            "Licuado",
            "secundaria",
            {"ING01": 0.10, "ING_CAD": 0.20},
            demanda_fija=0,
            demanda_menu_dia=10,
        ),
        Receta(
            "REC_OK",
            "Crema pura",
            "secundaria",
            {"ING01": 0.20},
            demanda_fija=0,
            demanda_menu_dia=5,
        ),
    ]

    estado = preparar(ingredientes, recetas, hoy)
    assert llenar(estado) == {"REC_OK": 5}


def test_llenar_sin_ingredientes_en_riesgo_devuelve_vacio(hoy):
    ingredientes = [Ingrediente("ING01", "Bistec", 3.0, date(2026, 11, 18), 180.0)]
    recetas = [
        Receta("REC01", "Tacos", "fijo", {"ING01": 0.12}, demanda_fija=25, demanda_menu_dia=10)
    ]

    estado = preparar(ingredientes, recetas, hoy)
    assert estado.orden == []
    assert llenar(estado) == {}


def test_llenar_acota_porciones_a_las_necesarias_con_tolerancia_eps(hoy):
    ingredientes = [Ingrediente("ING01", "Crema", 2.0, date(2026, 11, 17), 70.0)]
    recetas = [
        Receta(
            "REC_FIJA", "Base carta", "fijo", {"ING01": 0.14}, demanda_fija=3, demanda_menu_dia=0
        ),
        Receta(
            "REC_DIA",
            "Especial",
            "secundaria",
            {"ING01": 0.04},
            demanda_fija=0,
            demanda_menu_dia=50,
        ),
    ]

    estado = preparar(ingredientes, recetas, hoy)
    assert llenar(estado) == {"REC_DIA": 29}


def test_llenar_rechaza_variante_desconocida(ingredientes, recetas, hoy):
    estado = preparar(ingredientes, recetas, hoy)
    with pytest.raises(ValueError, match="variante desconocida"):
        llenar(estado, variante="inexistente")


def test_generar_menu_ejemplo_de_referencia(ingredientes, recetas, hoy):
    menu = generar_menu(ingredientes, recetas, hoy)

    assert menu.variante == "base"
    assert menu.porciones == {"REC01": 12, "REC03": 10, "REC07": 10}
    assert menu.total_porciones == 32
    assert menu.valor == pytest.approx(1.51667, abs=1e-5)
    assert menu.tiempo_ms >= 0.0


def test_generar_menu_con_datos_ejemplo():
    ingredientes, recetas = _cargar_carpeta(EJEMPLO)
    menu = generar_menu(ingredientes, recetas, date(2026, 11, 17))

    assert menu.porciones == {
        "REC01": 12,
        "REC03": 10,
        "REC04": 8,
        "REC05": 4,
        "REC06": 8,
        "REC07": 10,
    }
    assert menu.valor == pytest.approx(4.25455, abs=1e-5)


@pytest.mark.parametrize("semilla", range(50))
def test_invariantes_50_instancias_aleatorias(semilla: int, hoy: date):
    ingredientes, recetas = _instancia_aleatoria(random.Random(semilla), hoy)
    menu = generar_menu(ingredientes, recetas, hoy)
    estado = preparar(ingredientes, recetas, hoy)

    recetas_por_id = {r.id: r for r in recetas}
    ing_por_id = {i.id: i for i in ingredientes}
    usado: defaultdict[str, float] = defaultdict(float)

    for rec_id, porciones in menu.porciones.items():
        # Solo recetas existentes y dentro de su demanda del menú del día
        assert rec_id in recetas_por_id
        assert 1 <= porciones <= recetas_por_id[rec_id].demanda_menu_dia
        for ing_id, kg in recetas_por_id[rec_id].ingredientes.items():
            # Ningún ingrediente caducado puede ser consumido
            assert ing_por_id[ing_id].fecha_caducidad >= hoy
            usado[ing_id] += porciones * kg

    # Nunca excede el inventario disponible tras reservar el menú fijo de hoy
    for ing_id, kg_usado in usado.items():
        assert kg_usado <= estado.disponible.get(ing_id, 0.0) + 1e-9

    # Determinismo: incluso invirtiendo el orden de entrada produce el mismo menú
    repetido = generar_menu(list(reversed(ingredientes)), list(reversed(recetas)), hoy)
    assert repetido.porciones == menu.porciones
    assert repetido.valor == pytest.approx(menu.valor)


def test_voraz_no_usa_pandas_streamlit_ni_fecha_del_sistema():
    ruta = Path(__file__).resolve().parents[1] / "src" / "menucero" / "voraz.py"
    codigo = ruta.read_text(encoding="utf-8")
    arbol = ast.parse(codigo)
    importados: set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            importados.update(alias.name.split(".")[0] for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            importados.add(nodo.module.split(".")[0])
    assert "pandas" not in importados
    assert "streamlit" not in importados
    assert "today(" not in codigo
    assert "now(" not in codigo


def test_variantes_secundarias_y_sin_principal_ejemplo_referencia(ingredientes, recetas, hoy):
    menu_sec = generar_menu(ingredientes, recetas, hoy, variante="secundarias")
    assert menu_sec.porciones == {"REC07": 10}
    assert menu_sec.valor == pytest.approx(0.51667, abs=1e-5)

    menu_sin = generar_menu(ingredientes, recetas, hoy, variante="sin_principal")
    assert menu_sin.porciones == {"REC03": 10, "REC07": 10}
    assert menu_sin.valor == pytest.approx(0.96667, abs=1e-5)


def test_variante_economica_prioriza_rescate_de_mayor_costo(hoy):
    # ING_BARATO vence hoy (p = 1.0, $20/kg) y va primero en estado.orden.
    # ING_CARO vence mañana (p = 0.5, $200/kg). ING_LIM deja 0.9 kg disponibles (10 porciones).
    # - REC_A: 0.12 kg de ING_BARATO -> base = 0.12, economica = 2.4
    # - REC_B: 0.04 kg de ING_BARATO + 0.06 kg de ING_CARO -> base = 0.07, economica = 6.8
    ingredientes = [
        Ingrediente("ING_BARATO", "Verdura", 1.2, hoy, 20.0),
        Ingrediente("ING_CARO", "Queso fino", 0.6, hoy + timedelta(days=1), 200.0),
        Ingrediente("ING_LIM", "Tortilla", 1.0, hoy + timedelta(days=9), 25.0),
    ]
    recetas = [
        Receta(
            "REC_CARTA", "Taco fijo", "fijo", {"ING_LIM": 0.10}, demanda_fija=1, demanda_menu_dia=0
        ),
        Receta(
            "REC_A",
            "Guiso verdura",
            "secundaria",
            {"ING_BARATO": 0.12, "ING_LIM": 0.09},
            demanda_fija=0,
            demanda_menu_dia=10,
        ),
        Receta(
            "REC_B",
            "Quesadilla especial",
            "secundaria",
            {"ING_BARATO": 0.04, "ING_CARO": 0.06, "ING_LIM": 0.09},
            demanda_fija=0,
            demanda_menu_dia=10,
        ),
    ]

    estado = preparar(ingredientes, recetas, hoy)
    assert estado.orden[0] == "ING_BARATO"
    assert llenar(estado, variante="base") == {"REC_A": 10}
    assert llenar(estado, variante="economica") == {"REC_B": 10}


def test_variante_eficiencia_cuida_inventario_sano(hoy):
    # ING_RIESGO tiene 1.0 kg en riesgo (p = 1.0) e ING_SANO tiene 5.0 kg sin riesgo.
    # - REC_PESADA: 0.12 kg en riesgo + 0.50 kg sanos (base = 0.12, eficiencia = 0.12 / 0.62)
    # - REC_LIGERA: 0.10 kg en riesgo + 0.02 kg sanos (base = 0.10, eficiencia = 0.10 / 0.12)
    ingredientes = [
        Ingrediente("ING_RIESGO", "Crema", 1.0, hoy, 70.0),
        Ingrediente("ING_SANO", "Pechuga", 5.0, hoy + timedelta(days=3), 120.0),
    ]
    recetas = [
        Receta(
            "REC_FIJA",
            "Pollo carta",
            "fijo",
            {"ING_SANO": 1.25},
            demanda_fija=1,
            demanda_menu_dia=0,
        ),
        Receta(
            "REC_PESADA",
            "Plato abundante",
            "secundaria",
            {"ING_RIESGO": 0.12, "ING_SANO": 0.50},
            demanda_fija=0,
            demanda_menu_dia=10,
        ),
        Receta(
            "REC_LIGERA",
            "Salsa ligera",
            "secundaria",
            {"ING_RIESGO": 0.10, "ING_SANO": 0.02},
            demanda_fija=0,
            demanda_menu_dia=10,
        ),
    ]

    estado = preparar(ingredientes, recetas, hoy)
    assert llenar(estado, variante="base") == {"REC_PESADA": 7, "REC_LIGERA": 1}
    assert llenar(estado, variante="eficiencia") == {"REC_LIGERA": 10}
