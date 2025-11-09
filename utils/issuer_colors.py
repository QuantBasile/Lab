import json
from pathlib import Path
from functools import lru_cache

# El JSON está en el mismo directorio que este archivo
_COLORS_FILE = Path(__file__).with_name("issuer_colors.json")


@lru_cache(maxsize=1)
def _load_colors() -> dict:
    """
    Carga el JSON una sola vez en memoria.
    Devuelve un dict {issuer: color_hex}.
    """
    try:
        with open(_COLORS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Normalizamos a str por si acaso
        return {str(k): str(v) for k, v in data.items()}
    except Exception:
        return {}


def get_issuer_color(issuer: str, fallback=None):
    """
    Devuelve el color para un emisor.
    Si no existe en el JSON, devuelve `fallback`.
    """
    colors = _load_colors()
    return colors.get(issuer, fallback)


def get_all_issuer_colors() -> dict:
    """
    Devuelve una copia del diccionario completo de colores.
    Útil si en alguna sheet quieres mostrar una leyenda global.
    """
    return _load_colors().copy()
