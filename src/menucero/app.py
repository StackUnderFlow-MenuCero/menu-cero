"""Interfaz de Menú Cero en Streamlit.

Por ahora es una pantalla de bienvenida. La carga de los CSV y el inventario
ordenado por prioridad se agregan en #14; las propuestas de menú, en #26.
"""

import streamlit as st

from menucero import __version__

st.set_page_config(page_title="Menú Cero", layout="wide")
st.title("Menú Cero")
st.write("Menú del día que prioriza los ingredientes próximos a caducar.")
st.info(
    "Prototipo en construcción: la carga de los CSV y el inventario ordenado por "
    "prioridad llegan con el avance del miércoles 18 (#14)."
)
st.caption(f"Versión {__version__}")
