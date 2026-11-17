# Cómo trabajamos en Menú Cero

## Flujo de un issue

1. Toma un issue asignado a ti y muévelo a **In Progress** en el [tablero](https://github.com/orgs/StackUnderFlow-MenuCero/projects/1).
2. Crea una rama desde `main` con el nombre `tipo/descripcion-corta`, por ejemplo `feat/carga-csv`, `docs/formato-csv` o `test/voraz-invariantes`.
3. Haz commits pequeños con el formato `tipo: Descripción en español`, por ejemplo `feat: Validar fechas del inventario`.
4. Abre un PR hacia `main` y escribe `Closes #N` en la descripción. GitHub solo reconoce las palabras en inglés (`Closes`, `Fixes`, `Resolves`); con ellas, el issue se cierra solo al unir el PR.
5. Mueve el issue a **In Review** y pide revisión a otra persona del equipo.
6. Se une a `main` cuando el CI está en verde y hay al menos una aprobación.

Tipos de rama y commit: `feat`, `fix`, `docs`, `test`, `refactor` y `chore` (configuración, dependencias, CI).

## Antes de abrir un PR

```bash
uv run ruff format         # da formato al código
uv run ruff check --fix    # lint
uv run pytest              # pruebas
```

El CI corre lo mismo en cada PR: `uv sync --locked`, `ruff check`, `ruff format --check` y `pytest`.

## Dependencias

- Agregar una biblioteca: `uv add nombre` (o `uv add --dev nombre` si solo se usa para desarrollo).
- Sube siempre `pyproject.toml` y `uv.lock` en el mismo commit.
- No se edita `uv.lock` a mano.

## Reglas del código

- Pandas solo se usa en `carga.py`. El algoritmo trabaja con las dataclasses de `modelos.py`, para que la complejidad que se analiza sea la del código que se mide.
- Nada usa la fecha del sistema por dentro: la fecha de referencia («hoy») siempre llega como parámetro.
- Toda función nueva lleva al menos una prueba en `tests/`.
