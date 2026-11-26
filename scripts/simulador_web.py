"""Puente entre el simulador de la página (#51) y ``menucero.simulacion``.

La vista ``simulador.html`` corre este módulo en el navegador con Pyodide, junto
con el paquete ``menucero`` y el prototipo v0, tal como están en el repositorio.
Por eso solo usa la biblioteca estándar y ``menucero``.

Un restaurante llega del navegador como un diccionario::

    {
        "nombre": "Trattoria",
        "cocina": "italiana",
        "platillos": {"IT01": {"tipo": "fijo", "demanda_fija": 25, "demanda_menu_dia": 4}},
        "inventario": [{"ingrediente": "jitomate", "cantidad_kg": 4.5, "vence_en": 2}],
        "dias": 7,
        "semilla": 1,
        "ruido": true,
    }

``vence_en`` cuenta días desde la fecha de la simulación: 0 = vence ese día (todavía
se usa), igual que ``fecha_caducidad`` en ``docs/datos.md``. Los costos, nombres y
recetas salen del catálogo (``data/catalogo.json``).

El voraz es el de ``voraz_por_omision()``: el prototipo v0 hasta que
``menucero.voraz.generar_menu`` (#20) exista; desde ese momento, el definitivo,
sin cambiar nada aquí.
"""

from __future__ import annotations

import base64
import csv
import io
import json
import random
import zipfile
from collections import defaultdict
from collections.abc import Callable, Mapping
from datetime import date, timedelta
from typing import Any

from menucero.modelos import Ingrediente, Receta
from menucero.simulacion import ResultadoSimulacion, simular, voraz_por_omision

DIAS_SEMANA = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")
MESES = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
DIAS_MAXIMOS = 14

Catalogo = Mapping[str, Any]


# --- catálogo -------------------------------------------------------------------


def recetas_del_catalogo(catalogo: Catalogo) -> dict[str, dict]:
    """Todas las recetas del catálogo por id, con su cocina."""
    recetas = {}
    for cocina, datos in catalogo["cocinas"].items():
        for r in datos["recetas"]:
            recetas[r["id"]] = {**r, "cocina": cocina}
    return recetas


def errores_del_catalogo(catalogo: Catalogo) -> list[str]:
    """Lo que está mal en el catálogo; vacío si se puede usar."""
    errores = []
    ingredientes = catalogo["ingredientes"]
    for i, ing in ingredientes.items():
        vmin, vmax = ing["vida_dias"]
        if not 0 <= vmin <= vmax:
            errores.append(f"{i}: vida_dias debe ir de menor a mayor y no ser negativa")
        if ing["costo_kg"] < 0 or ing["compra_kg"] <= 0:
            errores.append(f"{i}: costo_kg ≥ 0 y compra_kg > 0")
    vistos: set[str] = set()
    for cocina, datos in catalogo["cocinas"].items():
        for r in datos["recetas"]:
            if r["id"] in vistos:
                errores.append(f"{r['id']}: id repetido")
            vistos.add(r["id"])
            for i in r["ingredientes"]:
                if i not in ingredientes:
                    errores.append(f"{r['id']} ({cocina}): {i} no está en los ingredientes")
            try:
                _receta(r, r)
            except ValueError as e:
                errores.append(str(e))
    for ejemplo in catalogo.get("restaurantes_ejemplo", []):
        cocina = catalogo["cocinas"].get(ejemplo["cocina"])
        ids = {r["id"] for r in cocina["recetas"]} if cocina else set()
        for rid in ejemplo["recetas"]:
            if rid not in ids:
                errores.append(f"{ejemplo['nombre']}: {rid} no es de la cocina {ejemplo['cocina']}")
    return errores


def platillos_por_omision(catalogo: Catalogo, ids: list[str]) -> dict[str, dict]:
    """Tipo y demanda de cada platillo tal como vienen en el catálogo."""
    recetas = recetas_del_catalogo(catalogo)
    return {
        rid: {
            "tipo": recetas[rid]["tipo"],
            "demanda_fija": recetas[rid]["demanda_fija"],
            "demanda_menu_dia": recetas[rid]["demanda_menu_dia"],
        }
        for rid in ids
    }


def aleatorizar(catalogo: Catalogo, platillos: Mapping[str, Mapping], semilla: int) -> list[dict]:
    """Un inventario coherente con los platillos elegidos, reproducible con ``semilla``.

    Trae cada ingrediente que usan los platillos. Supone que el negocio compró para
    cubrir lo que le queda de vida útil con la demanda del menú fijo, o al menos un
    resto de la compra mínima: así lo de los platillos poco pedidos sobra, como en
    el negocio tipo de ``docs/datos.md``.
    """
    recetas = recetas_del_catalogo(catalogo)
    uso: dict[str, float] = defaultdict(float)  # kg al día con el menú fijo
    for rid, cfg in platillos.items():
        porciones = cfg["demanda_fija"] if cfg["tipo"] == "fijo" else 0
        for i, q in recetas[rid]["ingredientes"].items():
            uso[i] += porciones * q

    rng = random.Random(f"inventario-{semilla}")
    inventario = []
    for i in sorted(uso):
        ing = catalogo["ingredientes"][i]
        vmin, vmax = ing["vida_dias"]
        # Uno de cada cuatro está por vencer: así siempre hay algo que aprovechar.
        vence_en = rng.randint(0, 1) if rng.random() < 0.25 else rng.randint(0, vmax)
        cubrir = uso[i] * (vence_en + 1) * rng.uniform(1.05, 1.5)
        resto = ing["compra_kg"] * rng.uniform(0.4, 1.0)
        kg = max(round(max(cubrir, resto) / 0.05) * 0.05, 0.05)
        inventario.append({"ingrediente": i, "cantidad_kg": round(kg, 2), "vence_en": vence_en})
    return inventario


def restaurantes_ejemplo(catalogo: Catalogo) -> list[dict]:
    """Los restaurantes con los que abre la vista, con su inventario aleatorio."""
    ejemplos = []
    for ejemplo in catalogo["restaurantes_ejemplo"]:
        platillos = platillos_por_omision(catalogo, ejemplo["recetas"])
        ejemplos.append(
            {
                "nombre": ejemplo["nombre"],
                "cocina": ejemplo["cocina"],
                "platillos": platillos,
                "inventario": aleatorizar(catalogo, platillos, ejemplo["semilla"]),
                "dias": 7,
                "semilla": ejemplo["semilla"],
                "ruido": True,
            }
        )
    return ejemplos


# --- del restaurante a los modelos -------------------------------------------------


def _receta(base: Mapping, cfg: Mapping) -> Receta:
    tipo = cfg.get("tipo", base["tipo"])
    return Receta(
        id=base["id"],
        platillo=base["platillo"],
        tipo=tipo,
        ingredientes=dict(base["ingredientes"]),
        demanda_fija=int(cfg.get("demanda_fija", 0)) if tipo == "fijo" else 0,
        demanda_menu_dia=int(cfg.get("demanda_menu_dia", 0)),
    )


def modelos(
    catalogo: Catalogo, restaurante: Mapping, hoy: date
) -> tuple[list[Ingrediente], list[Receta]]:
    """Los ``Ingrediente`` y ``Receta`` de ``modelos.py`` del restaurante.

    Lanza ``ValueError`` con un mensaje para el usuario si algo no se puede simular.
    """
    catalogo_ing = catalogo["ingredientes"]
    recetas_cat = recetas_del_catalogo(catalogo)

    ingredientes = []
    vistos = set()
    for fila in restaurante["inventario"]:
        i = fila["ingrediente"]
        if i not in catalogo_ing:
            raise ValueError(f"«{i}» no está en el catálogo de ingredientes.")
        if i in vistos:
            raise ValueError(f"{catalogo_ing[i]['nombre']} está dos veces en el inventario.")
        vistos.add(i)
        ingredientes.append(
            Ingrediente(
                id=i,
                nombre=catalogo_ing[i]["nombre"],
                cantidad_kg=float(fila["cantidad_kg"]),
                fecha_caducidad=hoy + timedelta(days=int(fila["vence_en"])),
                costo_kg=float(catalogo_ing[i]["costo_kg"]),
            )
        )

    recetas = []
    for rid, cfg in sorted(restaurante["platillos"].items()):
        if rid not in recetas_cat:
            raise ValueError(f"El platillo {rid} no está en el catálogo.")
        recetas.append(_receta(recetas_cat[rid], cfg))

    if not recetas:
        raise ValueError("Elige al menos un platillo.")
    if not ingredientes:
        raise ValueError("El inventario está vacío: agrega ingredientes o usa «Aleatorizar».")
    return ingredientes, recetas


# --- simulación día por día ----------------------------------------------------------


def fecha_corta(d: date) -> str:
    return f"{DIAS_SEMANA[d.weekday()]} {d.day} {MESES[d.month - 1]}"


def nombre_voraz(generador: Callable) -> str:
    """Qué voraz usa la simulación: el definitivo (#20) o el prototipo v0."""
    definitivo = getattr(generador, "__module__", "") == "menucero.voraz"
    return "voraz (#20)" if definitivo else "v0 (prototipo)"


def dias_visor(resultado: ResultadoSimulacion, ids: list[str], inicial: list[float]) -> list[dict]:
    """Cada día de una corrida con arreglos alineados a ``ids``, como los lee ``visor.js``."""
    stock = list(inicial)
    dias = []
    for r in resultado.consumo_diario:
        consumo = [r["consumo_kg"].get(i, 0.0) for i in ids]
        merma = [r["merma_kg"].get(i, 0.0) for i in ids]
        dias.append(
            {
                "stock": [round(kg, 3) for kg in stock],
                "consumo": [round(kg, 3) for kg in consumo],
                "merma": [round(kg, 3) for kg in merma],
                "menu": resultado.menus[r["dia"] - 1] if resultado.menus else {},
                "vendidas": r["porciones_menu_dia"],
                "fijas": sum(r["porciones_fijas"].values()),
                "no_atendidas": sum(r["no_atendidas"].values()),
            }
        )
        stock = [max(0.0, s - c - m) for s, c, m in zip(stock, consumo, merma, strict=True)]
    return dias


def escenario_visor(
    ingredientes: list[Ingrediente],
    recetas: list[Receta],
    hoy: date,
    dias: int,
    semilla: int,
    ruido: bool,
    generador: Callable,
) -> dict:
    """Corre A y B con los mismos clientes y los deja listos para ``visor.js``."""
    ids = [ing.id for ing in ingredientes]
    inicial = [ing.cantidad_kg for ing in ingredientes]
    comun = {"dias": dias, "semilla": semilla, "ruido": ruido}
    a = simular(ingredientes, recetas, hoy, escenario="A", **comun)
    b = simular(ingredientes, recetas, hoy, escenario="B", generador=generador, **comun)
    return {
        "ingredientes": [
            {
                "nombre": ing.nombre,
                "costo": ing.costo_kg,
                # Día de la corrida (1 = el primero) en que caduca; ≤ 0 si ya caducó.
                "vence": (ing.fecha_caducidad - hoy).days + 1,
            }
            for ing in ingredientes
        ],
        "recetas": {r.id: r.platillo for r in recetas},
        "A": dias_visor(a, ids, inicial),
        "B": dias_visor(b, ids, inicial),
    }


def simular_restaurante(
    catalogo: Catalogo, restaurante: Mapping, hoy: date, generador: Callable | None = None
) -> dict:
    """La simulación de un restaurante en el formato de ``visor.js``."""
    dias = int(restaurante.get("dias", 7))
    if not 1 <= dias <= DIAS_MAXIMOS:
        raise ValueError(f"Los días deben ir de 1 a {DIAS_MAXIMOS}.")
    semilla = int(restaurante.get("semilla", 1))
    ruido = bool(restaurante.get("ruido", True))
    ingredientes, recetas = modelos(catalogo, restaurante, hoy)
    generador = generador or voraz_por_omision()

    escenario = escenario_visor(ingredientes, recetas, hoy, dias, semilla, ruido, generador)
    cocina = catalogo["cocinas"][restaurante["cocina"]]["nombre"].lower()
    fijos = sum(r.tipo == "fijo" for r in recetas)
    demanda = "demanda con variación aleatoria" if ruido else "demanda exacta"
    escenario.update(
        {
            "id": "restaurante",
            "nombre": restaurante["nombre"],
            "descripcion": (
                f"Cocina {cocina}: {fijos} platillos en la carta fija, "
                f"{len(recetas) - fijos} solo como menú del día y {len(ingredientes)} "
                f"ingredientes. {dias} días sin reposición, {demanda} (semilla {semilla})."
            ),
        }
    )
    return {
        "semilla": semilla,
        "voraz": nombre_voraz(generador),
        "fechas": [fecha_corta(hoy + timedelta(days=t)) for t in range(dias)],
        "escenarios": [escenario],
    }


# --- descarga en los CSV oficiales -------------------------------------------------------


def a_csv(catalogo: Catalogo, restaurante: Mapping, hoy: date) -> dict[str, str]:
    """El restaurante en los 3 CSV de ``docs/datos.md``, para abrirlo en la app (#14).

    Un ingrediente que usa algún platillo pero no está en el inventario va con 0 kg,
    para que cada ``ingrediente_id`` de ``recetas.csv`` exista en ``inventario.csv``.
    """
    ingredientes, recetas = modelos(catalogo, restaurante, hoy)
    presentes = {ing.id for ing in ingredientes}
    for r in recetas:
        for i in r.ingredientes:
            if i not in presentes:
                presentes.add(i)
                ing = catalogo["ingredientes"][i]
                ingredientes.append(Ingrediente(i, ing["nombre"], 0.0, hoy, ing["costo_kg"]))
    id_ing = {ing.id: f"ING{k:02d}" for k, ing in enumerate(ingredientes, 1)}
    id_rec = {r.id: f"REC{k:02d}" for k, r in enumerate(recetas, 1)}

    def texto(columnas: list[str], filas: list[list]) -> str:
        salida = io.StringIO()
        escritor = csv.writer(salida, lineterminator="\n")
        escritor.writerow(columnas)
        escritor.writerows(filas)
        return salida.getvalue()

    return {
        "inventario.csv": texto(
            ["ingrediente_id", "nombre", "cantidad_kg", "fecha_caducidad", "costo_kg"],
            [
                [
                    id_ing[ing.id],
                    ing.nombre,
                    f"{ing.cantidad_kg:.2f}",
                    ing.fecha_caducidad.isoformat(),
                    f"{ing.costo_kg:.2f}",
                ]
                for ing in ingredientes
            ],
        ),
        "recetas.csv": texto(
            ["receta_id", "platillo", "tipo", "ingrediente_id", "kg_por_porcion"],
            [
                [id_rec[r.id], r.platillo, r.tipo, id_ing[i], f"{q:.3f}"]
                for r in recetas
                for i, q in r.ingredientes.items()
            ],
        ),
        "demanda.csv": texto(
            ["receta_id", "demanda_fija", "demanda_menu_dia"],
            [[id_rec[r.id], r.demanda_fija, r.demanda_menu_dia] for r in recetas],
        ),
    }


def zip_csv(catalogo: Catalogo, restaurante: Mapping, hoy: date) -> bytes:
    archivos = a_csv(catalogo, restaurante, hoy)
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as z:
        for nombre, contenido in archivos.items():
            z.writestr(nombre, contenido)
    return salida.getvalue()


# --- entrada desde el navegador -------------------------------------------------------------

_catalogo: dict | None = None


def iniciar(texto_catalogo: str) -> str:
    """Guarda el catálogo y dice qué voraz se va a usar."""
    global _catalogo
    _catalogo = json.loads(texto_catalogo)
    return nombre_voraz(voraz_por_omision())


def ejecutar(peticion: str) -> str:
    """Atiende una petición JSON de ``simulador.js`` y responde en JSON.

    ``accion`` es ``"simular"``, ``"aleatorizar"`` o ``"csv"``. Si los datos no se
    pueden usar, responde ``{"ok": false, "error": "..."}`` en vez de fallar.
    """
    if _catalogo is None:
        raise RuntimeError("Falta llamar a iniciar() con el catálogo")
    p = json.loads(peticion)
    try:
        if p["accion"] == "simular":
            hoy = date.fromisoformat(p["hoy"])
            respuesta = simular_restaurante(_catalogo, p["restaurante"], hoy)
        elif p["accion"] == "aleatorizar":
            r = p["restaurante"]
            respuesta = {"inventario": aleatorizar(_catalogo, r["platillos"], int(p["semilla"]))}
        elif p["accion"] == "csv":
            datos = zip_csv(_catalogo, p["restaurante"], date.fromisoformat(p["hoy"]))
            respuesta = {"zip": base64.b64encode(datos).decode("ascii")}
        else:
            raise ValueError(f"Acción desconocida: {p['accion']!r}")
    except KeyError as e:
        return json.dumps({"ok": False, "error": f"Falta el dato {e.args[0]!r}."})
    except (ValueError, TypeError) as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)
    return json.dumps({"ok": True, **respuesta}, ensure_ascii=False)
