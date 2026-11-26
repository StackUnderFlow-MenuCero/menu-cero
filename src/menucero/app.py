"""Interfaz de Menú Cero en Streamlit."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from menucero import __version__
from menucero.carga import cargar_datos
from menucero.metricas import metricas_propuesta, orden_de_uso
from menucero.modelos import Ingrediente, MenuGenerado, Receta
from menucero.prioridad import dias_para_caducar, kg_en_riesgo, ordenar_por_prioridad, prioridad

EJEMPLO = Path(__file__).resolve().parents[2] / "data" / "ejemplo"
NOMBRES = ("inventario", "recetas", "demanda")

st.set_page_config(page_title="Menú Cero", layout="wide")
st.title("Menú Cero")
st.caption(f"Versión {__version__}")


def _firma_fuentes(fuentes: list[Any], hoy: date) -> tuple[Any, ...]:
    identificadores: list[Any] = []
    for f in fuentes:
        if isinstance(f, Path):
            identificadores.append(str(f.resolve()))
        elif hasattr(f, "name"):
            identificadores.append((getattr(f, "name", ""), getattr(f, "size", None)))
        else:
            identificadores.append(str(f))
    return (hoy.isoformat(), tuple(identificadores))


def _enriquecer_propuestas(
    propuestas: list[MenuGenerado],
    ingredientes: list[Ingrediente],
    recetas: list[Receta],
    hoy: date,
) -> list[MenuGenerado]:
    for prop in propuestas:
        if not prop.metricas:
            prop.metricas = metricas_propuesta(prop, ingredientes, recetas, hoy)
        if not prop.orden_uso:
            prop.orden_uso = orden_de_uso(prop, ingredientes, recetas, hoy)
    return propuestas


def _respaldo_propuestas(
    ingredientes: list[Ingrediente],
    recetas: list[Receta],
    hoy: date,
) -> list[MenuGenerado]:
    """Generador provisional hasta que el módulo voraz esté disponible en la rama."""
    riesgo = kg_en_riesgo(ingredientes, recetas, hoy)
    vigentes, _ = (
        [i for i in ingredientes if dias_para_caducar(i, hoy) >= 0],
        [i for i in ingredientes if dias_para_caducar(i, hoy) < 0],
    )
    prio_map = {i.id: prioridad(dias_para_caducar(i, hoy)) for i in vigentes}

    candidatas: list[tuple[float, Receta, int]] = []
    for rec in recetas:
        max_porciones = max(0, int(rec.demanda_menu_dia))
        if max_porciones <= 0 or not rec.ingredientes:
            continue
        puntaje = sum(
            prio_map.get(ing_id, 0.0) * kg_por
            for ing_id, kg_por in rec.ingredientes.items()
            if riesgo.get(ing_id, 0.0) > 1e-9
        )
        candidatas.append((puntaje, rec, max_porciones))

    candidatas.sort(key=lambda item: (-item[0], item[1].id))
    if not candidatas:
        return []

    porciones_base = {rec.id: min(max_p, 5) for _, rec, max_p in candidatas[:3]}
    propuestas: list[MenuGenerado] = [
        MenuGenerado(variante="base", porciones=porciones_base, valor=0.0)
    ]

    if len(candidatas) > 1:
        sin_top = {rec.id: min(max_p, 5) for _, rec, max_p in candidatas[1:4]}
        if sin_top and sin_top != porciones_base:
            propuestas.append(MenuGenerado(variante="sin_principal", porciones=sin_top, valor=0.0))

    sec_candidatas = [(p, r, m) for p, r, m in candidatas if r.tipo == "secundaria"]
    if sec_candidatas:
        porc_sec = {rec.id: min(max_p, 5) for _, rec, max_p in sec_candidatas[:2]}
        if porc_sec and all(p != porc_sec for p in (m.porciones for m in propuestas)):
            propuestas.append(MenuGenerado(variante="secundarias", porciones=porc_sec, valor=0.0))

    return _enriquecer_propuestas(propuestas, ingredientes, recetas, hoy)


def _obtener_propuestas(
    ingredientes: list[Ingrediente],
    recetas: list[Receta],
    hoy: date,
) -> list[MenuGenerado]:
    try:
        from menucero.voraz import generar_propuestas  # type: ignore[import-not-found]

        crudas = generar_propuestas(ingredientes, recetas, hoy)
        return _enriquecer_propuestas(list(crudas), ingredientes, recetas, hoy)
    except ImportError:
        return _respaldo_propuestas(ingredientes, recetas, hoy)


with st.sidebar:
    hoy = st.date_input("Fecha de referencia", value=date(2026, 11, 17), format="YYYY-MM-DD")
    archivos = [st.file_uploader(f"{nombre}.csv", type="csv") for nombre in NOMBRES]
    if st.button("Usar datos de ejemplo", use_container_width=True):
        st.session_state.fuentes = [EJEMPLO / f"{nombre}.csv" for nombre in NOMBRES]

if all(archivos):
    st.session_state.fuentes = archivos

if "fuentes" not in st.session_state:
    st.info("Sube los tres CSV o usa los datos de ejemplo.")
    st.stop()

firma_actual = _firma_fuentes(st.session_state.fuentes, hoy)
if st.session_state.get("propuestas_firma") != firma_actual:
    st.session_state.pop("propuestas", None)
    st.session_state["propuestas_firma"] = firma_actual

res = cargar_datos(*st.session_state.fuentes, hoy=hoy)

for msg in res.errores:
    st.error(str(msg))

if not res.ok:
    st.stop()

if res.advertencias:
    with st.expander(f"{len(res.advertencias)} advertencias"):
        for msg in res.advertencias:
            st.warning(str(msg))

ordenados = ordenar_por_prioridad(res.ingredientes, hoy)
filas = []
for ing in ordenados:
    d = dias_para_caducar(ing, hoy)
    filas.append(
        {
            "Ingrediente": ing.nombre,
            "Vence": ing.fecha_caducidad,
            "Días": d,
            "Prioridad": prioridad(d),
            "kg": ing.cantidad_kg,
            "Costo/kg": ing.costo_kg,
            "Valor ($)": ing.cantidad_kg * ing.costo_kg,
        }
    )

tabla = pd.DataFrame(filas)


def _resaltar(fila: pd.Series) -> list[str]:
    if fila["Días"] < 0:
        estilo = "background-color: #5c1a1a; color: #ffd6d6; font-weight: 600"
    elif fila["Días"] <= 1:
        estilo = "background-color: #4a231d; color: #ffece8"
    else:
        estilo = ""
    return [estilo] * len(fila)


urgentes = int((tabla["Días"] <= 1).sum()) if not tabla.empty else 0
st.caption(f"{len(tabla)} ingredientes · {urgentes} vencen en menos de 48 h")

formato = {
    "Prioridad": "{:.3f}",
    "kg": "{:.2f}",
    "Costo/kg": "${:,.2f}",
    "Valor ($)": "${:,.2f}",
}

st.dataframe(
    tabla.style.apply(_resaltar, axis=1).format(formato),
    hide_index=True,
    use_container_width=True,
)

st.divider()
st.subheader("Propuestas de menú del día")

if st.button("Generar menú del día", type="primary"):
    st.session_state.propuestas = _obtener_propuestas(res.ingredientes, res.recetas, hoy)

propuestas: list[MenuGenerado] | None = st.session_state.get("propuestas")
if propuestas is not None:
    if not propuestas:
        st.info("No se encontraron propuestas aplicables con los datos y fecha actuales.")
    else:
        if len(propuestas) < 3:
            st.info(
                f"Solo se generaron {len(propuestas)} propuesta(s) distinta(s) para este escenario."
            )

        resumen_filas = []
        for prop in propuestas:
            m = prop.metricas or metricas_propuesta(prop, res.ingredientes, res.recetas, hoy)
            resumen_filas.append(
                {
                    "Variante": prop.variante,
                    "Valor (V)": prop.valor,
                    "Porciones": int(m.get("porciones", prop.total_porciones)),
                    "Platillos": int(
                        m.get("platillos", sum(1 for p in prop.porciones.values() if p > 0))
                    ),
                    "kg rescatados": m.get("kg_rescatados", 0.0),
                    "% aprovechamiento": m.get("pct_aprovechamiento", 0.0),
                    "Costo recuperado ($)": m.get("costo_recuperado", 0.0),
                }
            )

        st.dataframe(
            pd.DataFrame(resumen_filas).style.format(
                {
                    "Valor (V)": "{:.4f}",
                    "kg rescatados": "{:.2f}",
                    "% aprovechamiento": "{:.1f}%",
                    "Costo recuperado ($)": "${:,.2f}",
                }
            ),
            hide_index=True,
            use_container_width=True,
        )

        recetas_map = {r.id: r for r in res.recetas}
        pestanas = st.tabs([f"Propuesta: {p.variante}" for p in propuestas])

        for tab, prop in zip(pestanas, propuestas, strict=False):
            with tab:
                m = prop.metricas or metricas_propuesta(prop, res.ingredientes, res.recetas, hoy)
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Porciones totales", int(m.get("porciones", prop.total_porciones)))
                c2.metric("kg rescatados", f"{m.get('kg_rescatados', 0.0):.2f} kg")
                c3.metric("% aprovechamiento", f"{m.get('pct_aprovechamiento', 0.0):.1f}%")
                c4.metric("Costo recuperado", f"${m.get('costo_recuperado', 0.0):,.2f}")

                platillos_filas = [
                    {
                        "Receta ID": rec_id,
                        "Platillo": recetas_map[rec_id].platillo
                        if rec_id in recetas_map
                        else rec_id,
                        "Tipo": recetas_map[rec_id].tipo if rec_id in recetas_map else "-",
                        "Porciones": cant,
                    }
                    for rec_id, cant in prop.porciones.items()
                    if cant > 0
                ]
                st.markdown("**Platillos propuestos**")
                if platillos_filas:
                    st.dataframe(
                        pd.DataFrame(platillos_filas), hide_index=True, use_container_width=True
                    )
                else:
                    st.caption("Sin porciones asignadas en esta variante.")

                uso_items = prop.orden_uso or orden_de_uso(prop, res.ingredientes, res.recetas, hoy)
                uso_filas = [
                    {
                        "Ingrediente": item.nombre,
                        "ID": item.ingrediente_id,
                        "Días": item.dias,
                        "kg a usar": item.kg_a_usar,
                        "Platillos": ", ".join(item.platillos),
                    }
                    for item in uso_items
                ]
                st.markdown("**Orden de uso de ingredientes**")
                if uso_filas:
                    df_uso = pd.DataFrame(uso_filas)
                    st.dataframe(
                        df_uso.style.format({"kg a usar": "{:.2f}"}),
                        hide_index=True,
                        use_container_width=True,
                    )
                    st.download_button(
                        label=f"Descargar orden de uso ({prop.variante}.csv)",
                        data=df_uso.to_csv(index=False).encode("utf-8-sig"),
                        file_name=f"propuesta_{prop.variante}_orden_uso.csv",
                        mime="text/csv",
                        key=f"descarga_{prop.variante}",
                    )
                else:
                    st.caption("No hay ingredientes asignados para esta propuesta.")
