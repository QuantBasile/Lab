# utils/issuer_colors.py
import json
import re
from pathlib import Path
from functools import lru_cache

_COLORS_FILE = Path(__file__).with_name("issuer_colors.json")

# Paleta fallback (coherente y legible)
_FALLBACK_PALETTE = [
    "#1f77b4","#ff7f0e","#2ca02c","#d62728","#9467bd",
    "#8c564b","#e377c2","#7f7f7f","#bcbd22","#17becf",
]

# Alias conocidos (extiéndelo con tus emisores reales)
_ALIAS = {
    "DEUTSCHE BANK": "DB",
    "DEUTSCHE BANK AG": "DB",
    "DEUTSCHE BANK AG & CO": "DB",
    "HSBC BANK": "HSBC",
    "HSBC BANK PLC": "HSBC",
    "HSBC TRINKAUS": "HSBC",
    "J.P. MORGAN": "JPM",
    "JP MORGAN": "JPM",
    "JPMORGAN": "JPM",
    "BNP PARIBAS": "BNPP",
    "BNP PARIBAS ARBITRAGE": "BNPP",
    "MORGAN STANLEY": "MS",
    "GOLDMAN SACHS": "GS",
    "CITIGROUP": "CITI",
    "CITIBANK": "CITI",
    # añade más variantes reales aquí...
}

# Cache runtime para emisores no presentes en JSON (consistencia sesión)
_runtime_unknown_map = {}
_runtime_palette_idx = 0

def _normalize_issuer(s: str) -> str:
    if s is None:
        return ""
    t = str(s).upper().strip()
    # Quitar puntuación leve y múltiples espacios
    t = re.sub(r"[.,;:()&']", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    # Quitar sufijos corporativos comunes
    t = re.sub(r"\b(BANK|AG|PLC|S\.?A\.?|SA|N\.?V\.?|NV|GROUP|& CO|LTD|LIMITED)\b", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

@lru_cache(maxsize=1)
def _load_colors() -> dict:
    try:
        with open(_COLORS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # normaliza claves del JSON también (por si acaso)
        return { _normalize_issuer(k): str(v) for k, v in data.items() }
    except Exception:
        return {}

def _resolve_alias(norm_issuer: str) -> str:
    # intenta alias exacto
    if norm_issuer in _ALIAS:
        return _ALIAS[norm_issuer]
    # heurística startswith (p.ej. "DEUTSCHE BANK X" → "DEUTSCHE BANK")
    for k, v in _ALIAS.items():
        if norm_issuer.startswith(k):
            return v
    return norm_issuer  # si no hay alias, queda como está

def get_issuer_color(issuer: str, fallback=None):
    """
    Devuelve color:
      1) match directo en JSON tras normalización
      2) alias → match JSON
      3) runtime palette (cacheada) si no hay match
      4) por último, fallback
    """
    global _runtime_palette_idx

    colors = _load_colors()
    norm = _normalize_issuer(issuer)
    # 1) directo
    if norm in colors:
        return colors[norm]

    # 2) alias
    aliased = _resolve_alias(norm)
    alias_norm = _normalize_issuer(aliased)
    if alias_norm in colors:
        return colors[alias_norm]

    # 3) runtime fallback consistente
    if norm in _runtime_unknown_map:
        return _runtime_unknown_map[norm]
    # asigna un color de la paleta (cíclica)
    color = _FALLBACK_PALETTE[_runtime_palette_idx % len(_FALLBACK_PALETTE)]
    _runtime_palette_idx += 1
    _runtime_unknown_map[norm] = color
    return color if color is not None else fallback

def get_all_issuer_colors() -> dict:
    # Devuelve todos (JSON + runtime asignados)
    base = _load_colors().copy()
    base.update(_runtime_unknown_map)
    return base
