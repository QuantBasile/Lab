"""
issuer_colors.py
-----------------

Utility functions for assigning consistent colors to issuers.

Color priority:
    1. Direct match from the embedded ISSUER_COLORS_RAW dict (after normalization)
    2. Alias resolution (e.g. "JP MORGAN", "JPMORGAN" → "JPM")
    3. Runtime fallback palette (stable within the current Python process)
    4. User-provided fallback color

Public API:
    get_issuer_color(issuer, fallback=None)
    get_all_issuer_colors()
"""

from __future__ import annotations

import re
from functools import lru_cache

# -------------------------------------------------------------------------
# 1. Base embedded color mapping
#    - You can freely extend/tune this dictionary.
#    - Keys are "canonical" issuer names; they will be normalized internally.
# -------------------------------------------------------------------------
ISSUER_COLORS_RAW: dict[str, str] = {
    # Core issuers (tune these to your taste)
    "HSBC": "#d62728",           # red
    "DB": "#1f77b4",             # blue (Deutsche Bank)
    "BNPP": "#2ca02c",           # green (BNP Paribas)
    "JPM": "#9467bd",            # purple (J.P. Morgan)
    "GS": "#ff7f0e",             # orange (Goldman Sachs)
    "MS": "#8c564b",             # brown (Morgan Stanley)
    "CITI": "#17becf",           # teal (Citigroup)
    "UBS": "#e377c2",            # pink
    "SOCIETE GENERALE": "#bcbd22",
    "BARCLAYS": "#7f7f7f",
    "UNICREDIT": "#98df8a",
    "COMMERZBANK": "#ff9896",
    "VONTOBEL": "#c5b0d5",
    "RBC": "#aec7e8",
    "CREDIT SUISSE": "#ffbb78",
    "ING": "#98df8a",
    "RAIFFEISEN": "#ff9896",
    # Add more specific mappings as you wish...
}

# -------------------------------------------------------------------------
# 2. Fallback palette for unknown issuers
# -------------------------------------------------------------------------
_FALLBACK_PALETTE = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
]

# -------------------------------------------------------------------------
# 3. Known alias patterns (extend with your real issuers)
# -------------------------------------------------------------------------
_ALIAS = {
    "DEUTSCHE BANK": "DB",
    "DEUTSCHE BANK AG": "DB",
    "DEUTSCHE BANK AG & CO": "DB",

    "HSBC BANK": "HSBC",
    "HSBC BANK PLC": "HSBC",
    "HSBC TRINKAUS": "HSBC",

    "J.P. MORGAN": "JPM",
    "JP MORGAN": "JPM",
    "JP MORGAN CHASE": "JPM",
    "JPMORGAN": "JPM",

    "BNP PARIBAS": "BNPP",
    "BNP PARIBAS ARBITRAGE": "BNPP",

    "MORGAN STANLEY": "MS",

    "GOLDMAN SACHS": "GS",
    "GOLDMAN SACHS INTERNATIONAL": "GS",

    "CITIGROUP": "CITI",
    "CITIBANK": "CITI",
    "CITIBANK N.A.": "CITI",

    "SOCIETE GENERALE": "SOCIETE GENERALE",
    "SOCIÉTÉ GÉNÉRALE": "SOCIETE GENERALE",

    "CREDIT SUISSE": "CREDIT SUISSE",
    "CREDIT SUISSE INTERNATIONAL": "CREDIT SUISSE",

    "VONTOBEL": "VONTOBEL",
    "VONCERT": "VONTOBEL",

    "UNICREDIT": "UNICREDIT",
    "UNICREDIT BANK": "UNICREDIT",

    "COMMERZBANK": "COMMERZBANK",
    "COMMERZBANK AG": "COMMERZBANK",

    "BARCLAYS": "BARCLAYS",
    "BARCLAYS BANK": "BARCLAYS",

    "RBC": "RBC",
    "ROYAL BANK OF CANADA": "RBC",

    "ING": "ING",
    "ING BANK": "ING",
}

# Runtime mapping for unknown issuers (stable per process)
_runtime_unknown_map: dict[str, str] = {}
_runtime_palette_idx: int = 0


# -------------------------------------------------------------------------
# Normalization
# -------------------------------------------------------------------------
def _normalize_issuer(s: str) -> str:
    """
    Normalize issuer names for consistent comparison.

    Steps:
        - Uppercase
        - Remove punctuation
        - Collapse multiple spaces
        - Remove common corporate suffixes (AG, PLC, NV, SA, GROUP, LTD...)
    """
    if s is None:
        return ""

    t = str(s).upper().strip()

    # Remove punctuation
    t = re.sub(r"[.,;:()&']", " ", t)
    t = re.sub(r"\s+", " ", t).strip()

    # Remove corporate suffixes
    t = re.sub(
        r"\b(BANK|AG|PLC|S\.?A\.?|SA|N\.?V\.?|NV|GROUP|& CO|LTD|LIMITED)\b",
        "",
        t,
    )
    t = re.sub(r"\s+", " ", t).strip()

    return t


# -------------------------------------------------------------------------
# Load embedded colors (normalized)
# -------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _load_colors() -> dict[str, str]:
    """
    Build a normalized issuer → color mapping from ISSUER_COLORS_RAW.

    Cached via lru_cache so normalization is done only once.
    """
    return {_normalize_issuer(k): str(v) for k, v in ISSUER_COLORS_RAW.items()}


# -------------------------------------------------------------------------
# Alias resolution
# -------------------------------------------------------------------------
def _resolve_alias(norm_issuer: str) -> str:
    """
    Resolve alias mappings.

    1) Try exact alias match
    2) Try prefix alias match
    """
    if norm_issuer in _ALIAS:
        return _ALIAS[norm_issuer]

    for key, alias in _ALIAS.items():
        if norm_issuer.startswith(key):
            return alias

    return norm_issuer


# -------------------------------------------------------------------------
# Public API
# -------------------------------------------------------------------------
def get_issuer_color(issuer: str, fallback: str | None = None) -> str | None:
    """
    Return a color for the given issuer with the following priority:

      1. Direct match in embedded ISSUER_COLORS_RAW (after normalization)
      2. Alias-based match in embedded ISSUER_COLORS_RAW
      3. Runtime fallback palette (assigned once per normalized issuer)
      4. The provided `fallback` color

    Parameters
    ----------
    issuer : str
        Issuer name as present in your data.

    fallback : str | None
        Optional fallback color if all other methods fail.

    Returns
    -------
    str | None
        A hex color string.
    """
    global _runtime_palette_idx

    colors = _load_colors()
    norm = _normalize_issuer(issuer)

    # 1) Direct match
    if norm in colors:
        return colors[norm]

    # 2) Alias match
    aliased = _resolve_alias(norm)
    alias_norm = _normalize_issuer(aliased)
    if alias_norm in colors:
        return colors[alias_norm]

    # 3) Runtime palette (session-stable)
    if norm in _runtime_unknown_map:
        return _runtime_unknown_map[norm]

    color = _FALLBACK_PALETTE[_runtime_palette_idx % len(_FALLBACK_PALETTE)]
    _runtime_palette_idx += 1
    _runtime_unknown_map[norm] = color

    return color if color is not None else fallback


def get_all_issuer_colors() -> dict[str, str]:
    """
    Return a dictionary containing:

        - All embedded colors (normalized)
        - All runtime-assigned fallback colors (for unknown issuers
          seen so far in this Python process)
    """
    base = _load_colors().copy()
    base.update(_runtime_unknown_map)
    return base
