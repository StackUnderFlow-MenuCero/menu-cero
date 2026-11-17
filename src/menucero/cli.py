"""Comandos de Menú Cero.

``uv run menucero`` abre la app de Streamlit. Los argumentos extra se pasan a
``streamlit run`` (por ejemplo, ``uv run menucero --server.port 8502``).
"""

import sys
from pathlib import Path

APP = Path(__file__).with_name("app.py")


def main() -> None:
    """Abre la interfaz de Menú Cero en el navegador."""
    from streamlit.web import cli as stcli

    sys.argv = ["streamlit", "run", str(APP), *sys.argv[1:]]
    sys.exit(stcli.main())
