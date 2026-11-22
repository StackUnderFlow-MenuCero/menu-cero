"""Interfaz de Menú Cero en Streamlit."""

from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from menucero import __version__
from menucero.carga import cargar_datos
from menucero.prioridad import dias_para_caducar, ordenar_por_prioridad, prioridad

EJEMPLO = Path(__file__).resolve().parents[2] / "data" / "ejemplo"
NOMBRES = ("inventario", "recetas", "demanda")

st.set_page_config(page_title="Menú Cero", layout="wide")
st.title("Menú Cero")
st.caption(f"Versión {__version__}")

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
    estilo = "background-color: #ffe3dc" if fila["Días"] <= 1 else ""
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
