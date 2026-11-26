"""Lectura y validación de inventario.csv, recetas.csv y demanda.csv."""

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from menucero.modelos import Ingrediente, Receta

DECIMAL = re.compile(r"-?\d+(\.\d+)?")
ENTERO = re.compile(r"-?\d+")
FECHA = re.compile(r"\d{4}-\d{2}-\d{2}")
IDENT = re.compile(r"[A-Za-z0-9_-]+")

COLS_INVENTARIO = ["ingrediente_id", "nombre", "cantidad_kg", "fecha_caducidad", "costo_kg"]
COLS_RECETAS = ["receta_id", "platillo", "tipo", "ingrediente_id", "kg_por_porcion"]
COLS_DEMANDA = ["receta_id", "demanda_fija", "demanda_menu_dia"]


@dataclass(frozen=True, slots=True)
class Mensaje:
    archivo: str
    fila: int | None
    columna: str | None
    texto: str
    valor: str | None = None

    def __str__(self) -> str:
        partes = [self.archivo]
        if self.fila is not None:
            partes.append(f"fila {self.fila}")
        if self.columna is not None:
            partes.append(f"columna {self.columna}")
        lugar = ", ".join(partes)
        extra = f" («{self.valor}»)" if self.valor is not None else ""
        return f"{lugar}: {self.texto}{extra}"


@dataclass
class ResultadoCarga:
    ingredientes: list[Ingrediente] = field(default_factory=list)
    recetas: list[Receta] = field(default_factory=list)
    errores: list[Mensaje] = field(default_factory=list)
    advertencias: list[Mensaje] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errores


def _leer_df(fuente: Any, archivo: str, errores: list[Mensaje]) -> pd.DataFrame | None:
    if hasattr(fuente, "seek"):
        fuente.seek(0)
    try:
        df = pd.read_csv(
            fuente,
            dtype=str,
            keep_default_na=False,
            encoding="utf-8-sig",
            skip_blank_lines=False,
        )
    except pd.errors.EmptyDataError:
        errores.append(Mensaje(archivo, None, None, "el archivo está vacío"))
        return None
    except Exception as exc:
        errores.append(Mensaje(archivo, None, None, f"no se pudo leer el CSV: {exc}"))
        return None

    df.columns = [str(c).strip().lower() for c in df.columns]
    return df.apply(lambda col: col.str.strip())


def _validar_columnas(
    df: pd.DataFrame | None,
    obligatorias: list[str],
    archivo: str,
    errores: list[Mensaje],
    advertencias: list[Mensaje],
) -> bool:
    if df is None:
        return False
    presentes = set(df.columns)
    faltantes = [c for c in obligatorias if c not in presentes]
    for col in faltantes:
        errores.append(Mensaje(archivo, 1, col, "falta columna obligatoria"))
    for col in df.columns:
        if col not in obligatorias:
            advertencias.append(Mensaje(archivo, 1, col, "columna desconocida", col))
    return len(faltantes) == 0


def _parse_decimal(
    fila: dict[str, str],
    col: str,
    archivo: str,
    fila_n: int,
    errores: list[Mensaje],
) -> float | None:
    val = fila[col]
    if val == "":
        errores.append(Mensaje(archivo, fila_n, col, "celda obligatoria vacía"))
        return None
    if not DECIMAL.fullmatch(val):
        errores.append(
            Mensaje(archivo, fila_n, col, "no es un número válido (usa punto decimal)", val)
        )
        return None
    return float(val)


def _parse_entero(
    fila: dict[str, str],
    col: str,
    archivo: str,
    fila_n: int,
    errores: list[Mensaje],
) -> int | None:
    val = fila[col]
    if val == "":
        errores.append(Mensaje(archivo, fila_n, col, "celda obligatoria vacía"))
        return None
    if not ENTERO.fullmatch(val):
        errores.append(Mensaje(archivo, fila_n, col, "no es un entero válido", val))
        return None
    return int(val)


def _parse_fecha(
    fila: dict[str, str],
    col: str,
    archivo: str,
    fila_n: int,
    errores: list[Mensaje],
) -> date | None:
    val = fila[col]
    if val == "":
        errores.append(Mensaje(archivo, fila_n, col, "celda obligatoria vacía"))
        return None
    if not FECHA.fullmatch(val):
        errores.append(Mensaje(archivo, fila_n, col, "no es una fecha AAAA-MM-DD", val))
        return None
    try:
        return date.fromisoformat(val)
    except ValueError:
        errores.append(Mensaje(archivo, fila_n, col, "fecha inválida", val))
        return None


def _parse_ident(
    fila: dict[str, str],
    col: str,
    archivo: str,
    fila_n: int,
    errores: list[Mensaje],
) -> str | None:
    val = fila[col]
    if val == "":
        errores.append(Mensaje(archivo, fila_n, col, "celda obligatoria vacía"))
        return None
    if not IDENT.fullmatch(val):
        errores.append(Mensaje(archivo, fila_n, col, "identificador inválido", val))
        return None
    return val


def cargar_datos(
    inventario: str | Path | Any,
    recetas: str | Path | Any,
    demanda: str | Path | Any,
    hoy: date | None = None,
) -> ResultadoCarga:
    """Lee y valida los tres CSV y devuelve ResultadoCarga con dataclasses."""
    errores: list[Mensaje] = []
    advertencias: list[Mensaje] = []

    df_inv = _leer_df(inventario, "inventario.csv", errores)
    df_rec = _leer_df(recetas, "recetas.csv", errores)
    df_dem = _leer_df(demanda, "demanda.csv", errores)

    inv_ok = _validar_columnas(df_inv, COLS_INVENTARIO, "inventario.csv", errores, advertencias)
    rec_ok = _validar_columnas(df_rec, COLS_RECETAS, "recetas.csv", errores, advertencias)
    dem_ok = _validar_columnas(df_dem, COLS_DEMANDA, "demanda.csv", errores, advertencias)

    ingredientes_raw: list[tuple[int, Ingrediente]] = []
    ids_inv: set[str] = set()

    if inv_ok and df_inv is not None:
        for fila_n, fila in enumerate(df_inv.to_dict("records"), start=2):
            if all(v == "" for v in fila.values()):
                continue
            ing_id = _parse_ident(fila, "ingrediente_id", "inventario.csv", fila_n, errores)
            nombre = fila["nombre"]
            if nombre == "":
                errores.append(
                    Mensaje("inventario.csv", fila_n, "nombre", "celda obligatoria vacía")
                )
            cant = _parse_decimal(fila, "cantidad_kg", "inventario.csv", fila_n, errores)
            cad = _parse_fecha(fila, "fecha_caducidad", "inventario.csv", fila_n, errores)
            costo = _parse_decimal(fila, "costo_kg", "inventario.csv", fila_n, errores)

            if ing_id is not None:
                if ing_id in ids_inv:
                    errores.append(
                        Mensaje("inventario.csv", fila_n, "ingrediente_id", "id repetido", ing_id)
                    )
                else:
                    ids_inv.add(ing_id)

            if cant is not None:
                if cant < 0:
                    errores.append(
                        Mensaje(
                            "inventario.csv",
                            fila_n,
                            "cantidad_kg",
                            "no puede ser negativa",
                            str(cant),
                        )
                    )
                elif cant == 0:
                    advertencias.append(
                        Mensaje("inventario.csv", fila_n, "cantidad_kg", "cantidad en 0", str(cant))
                    )

            if costo is not None:
                if costo < 0:
                    errores.append(
                        Mensaje(
                            "inventario.csv",
                            fila_n,
                            "costo_kg",
                            "no puede ser negativo",
                            str(costo),
                        )
                    )
                elif costo == 0:
                    advertencias.append(
                        Mensaje("inventario.csv", fila_n, "costo_kg", "costo en 0", str(costo))
                    )

            if cad is not None and hoy is not None and (cad - hoy).days < 0:
                advertencias.append(
                    Mensaje(
                        "inventario.csv",
                        fila_n,
                        "fecha_caducidad",
                        "ingrediente caducado",
                        cad.isoformat(),
                    )
                )

            if (
                ing_id
                and nombre
                and cant is not None
                and cant >= 0
                and cad is not None
                and costo is not None
                and costo >= 0
            ):
                ingredientes_raw.append((fila_n, Ingrediente(ing_id, nombre, cant, cad, costo)))

    recetas_meta: dict[str, tuple[str, str, int]] = {}
    recetas_ings: dict[str, dict[str, float]] = {}
    pares_vistos: set[tuple[str, str]] = set()

    if rec_ok and df_rec is not None:
        for fila_n, fila in enumerate(df_rec.to_dict("records"), start=2):
            if all(v == "" for v in fila.values()):
                continue
            rec_id = _parse_ident(fila, "receta_id", "recetas.csv", fila_n, errores)
            platillo = fila["platillo"]
            if platillo == "":
                errores.append(
                    Mensaje("recetas.csv", fila_n, "platillo", "celda obligatoria vacía")
                )
            tipo = fila["tipo"]
            if tipo == "":
                errores.append(Mensaje("recetas.csv", fila_n, "tipo", "celda obligatoria vacía"))
            elif tipo not in ("fijo", "secundaria"):
                errores.append(Mensaje("recetas.csv", fila_n, "tipo", "tipo inválido", tipo))

            ing_id = _parse_ident(fila, "ingrediente_id", "recetas.csv", fila_n, errores)
            kg_por = _parse_decimal(fila, "kg_por_porcion", "recetas.csv", fila_n, errores)

            if rec_id and ing_id:
                par = (rec_id, ing_id)
                if par in pares_vistos:
                    errores.append(
                        Mensaje(
                            "recetas.csv",
                            fila_n,
                            "ingrediente_id",
                            "par receta-ingrediente repetido",
                            ing_id,
                        )
                    )
                else:
                    pares_vistos.add(par)

            if rec_id and platillo and tipo in ("fijo", "secundaria"):
                if rec_id in recetas_meta:
                    prev_platillo, prev_tipo, prev_fila = recetas_meta[rec_id]
                    if (platillo, tipo) != (prev_platillo, prev_tipo):
                        errores.append(
                            Mensaje(
                                "recetas.csv",
                                fila_n,
                                "platillo",
                                f"platillo o tipo distinto al de la fila {prev_fila} para {rec_id}",
                                platillo,
                            )
                        )
                else:
                    recetas_meta[rec_id] = (platillo, tipo, fila_n)
                    recetas_ings[rec_id] = {}

            if ing_id and ing_id not in ids_inv:
                advertencias.append(
                    Mensaje(
                        "recetas.csv",
                        fila_n,
                        "ingrediente_id",
                        "ingrediente no está en el inventario (se toma cantidad 0)",
                        ing_id,
                    )
                )

            if kg_por is not None:
                if kg_por <= 0:
                    errores.append(
                        Mensaje(
                            "recetas.csv",
                            fila_n,
                            "kg_por_porcion",
                            "debe ser mayor que 0",
                            str(kg_por),
                        )
                    )
                else:
                    if kg_por > 1:
                        advertencias.append(
                            Mensaje(
                                "recetas.csv",
                                fila_n,
                                "kg_por_porcion",
                                "valor mayor a 1 kg por porción (revisar unidad)",
                                str(kg_por),
                            )
                        )
                    if rec_id and ing_id and rec_id in recetas_ings:
                        recetas_ings[rec_id][ing_id] = kg_por

    demandas_map: dict[str, tuple[int, int]] = {}
    if dem_ok and df_dem is not None:
        for fila_n, fila in enumerate(df_dem.to_dict("records"), start=2):
            if all(v == "" for v in fila.values()):
                continue
            rec_id = _parse_ident(fila, "receta_id", "demanda.csv", fila_n, errores)
            dem_fija = _parse_entero(fila, "demanda_fija", "demanda.csv", fila_n, errores)
            dem_menu = _parse_entero(fila, "demanda_menu_dia", "demanda.csv", fila_n, errores)

            if rec_id:
                if rec_id in demandas_map:
                    errores.append(
                        Mensaje("demanda.csv", fila_n, "receta_id", "receta_id repetido", rec_id)
                    )
                if rec_id not in recetas_meta:
                    advertencias.append(
                        Mensaje(
                            "demanda.csv",
                            fila_n,
                            "receta_id",
                            "fila de una receta que no existe (se ignora)",
                            rec_id,
                        )
                    )

            if dem_fija is not None and dem_fija < 0:
                errores.append(
                    Mensaje(
                        "demanda.csv",
                        fila_n,
                        "demanda_fija",
                        "no puede ser negativa",
                        str(dem_fija),
                    )
                )
            if dem_menu is not None and dem_menu < 0:
                errores.append(
                    Mensaje(
                        "demanda.csv",
                        fila_n,
                        "demanda_menu_dia",
                        "no puede ser negativa",
                        str(dem_menu),
                    )
                )

            if rec_id and rec_id in recetas_meta and dem_fija is not None and dem_menu is not None:
                _, tipo_rec, _ = recetas_meta[rec_id]
                fija_final = dem_fija
                if tipo_rec == "secundaria" and dem_fija > 0:
                    advertencias.append(
                        Mensaje(
                            "demanda.csv",
                            fila_n,
                            "demanda_fija",
                            "receta secundaria no lleva demanda_fija (se toma 0)",
                            str(dem_fija),
                        )
                    )
                    fija_final = 0
                if fija_final == 0 and dem_menu == 0:
                    advertencias.append(
                        Mensaje(
                            "demanda.csv", fila_n, "demanda_fija", "ambas demandas están en 0", "0"
                        )
                    )
                if rec_id not in demandas_map:
                    demandas_map[rec_id] = (fija_final, dem_menu)

    for rec_id in recetas_meta:
        if rec_id not in demandas_map:
            advertencias.append(
                Mensaje(
                    "demanda.csv",
                    None,
                    "receta_id",
                    f"receta sin fila de demanda (se toma 0): {rec_id}",
                )
            )

    if errores:
        return ResultadoCarga(errores=errores, advertencias=advertencias)

    ingredientes_finales = [ing for _, ing in ingredientes_raw]
    recetas_finales: list[Receta] = []
    for rec_id, (platillo, tipo, _) in recetas_meta.items():
        d_fija, d_menu = demandas_map.get(rec_id, (0, 0))
        ings_validos = {k: v for k, v in recetas_ings.get(rec_id, {}).items() if v > 0}
        recetas_finales.append(
            Receta(
                id=rec_id,
                platillo=platillo,
                tipo=tipo,
                ingredientes=ings_validos,
                demanda_fija=max(0, d_fija),
                demanda_menu_dia=max(0, d_menu),
            )
        )

    return ResultadoCarga(
        ingredientes=ingredientes_finales,
        recetas=recetas_finales,
        errores=[],
        advertencias=advertencias,
    )
