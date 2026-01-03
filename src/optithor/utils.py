# src/optithor/utils.py

from __future__ import annotations

import re
from typing import Iterable

from chempy import Substance

from .config import SolverConfig

__all__ = [
    "molar_mass",
    "molar_mass_h2o",
    "split_hydrate_formula",
    "elemental_counts",
    "format_mass_with_unit",
    "mass_to_g_per_l",
]

_H2O_MOLAR_MASS_FALLBACK = 18.01528


def molar_mass(formula: str) -> float:
    """Return molar mass in g/mol. Returns 0.0 if parsing fails."""
    try:
        return float(Substance.from_formula(str(formula)).mass)
    except Exception:
        return 0.0


def molar_mass_h2o() -> float:
    """Molar mass of water (g/mol) with safe fallback."""
    mm = molar_mass("H2O")
    return mm if mm > 0 else _H2O_MOLAR_MASS_FALLBACK


def split_hydrate_formula(formula: str) -> tuple[str, int]:
    """
    Parse hydrate notations:
      - 'CoCl2 • 6 H2O'
      - 'CoCl2·6H2O'
      - 'CoCl2 . 6 H2O'
      - 'CoCl2 • H2O'

    Returns: (base_formula, water_count)
    """
    if not formula:
        return "", 0

    s = str(formula).strip()
    s = s.replace("·", "•").replace(".", "•")

    if "•" not in s:
        return s, 0

    parts = [p.strip() for p in s.split("•") if p.strip()]
    if not parts:
        return s, 0

    base_formula = parts[0]

    water_count = 0
    for part in parts[1:]:
        compact = part.replace(" ", "")
        match = re.search(r"(?:(\d+))?H2O\b", compact)
        if match:
            water_count = int(match.group(1)) if match.group(1) else 1
            break

    return base_formula, water_count


def elemental_counts(
    molecular_formula: str,
    elements: Iterable[str] | None = None,
) -> dict[str, int]:
    """
    Count elements in a molecular formula.

    If elements is None, defaults are taken from SolverConfig.
    """
    if elements is None:
        elements = SolverConfig().elements

    counts = {element: 0 for element in elements}
    matches = re.findall(r"([A-Z][a-z]?)(\d*)", str(molecular_formula))

    for element, count_str in matches:
        if element in counts:
            counts[element] = int(count_str) if count_str else 1

    return counts


def format_mass_with_unit(value_g_per_l: float, decimals: int = 2) -> tuple[float, str]:
    """Format g/L into a readable unit for display."""
    v = float(value_g_per_l)
    if v >= 1:
        return round(v, decimals), "g/L"
    if v >= 1e-3:
        return round(v * 1e3, decimals), "mg/L"
    if v >= 1e-6:
        return round(v * 1e6, decimals), "µg/L"
    return round(v * 1e9, decimals), "ng/L"


def mass_to_g_per_l(value: float, unit: str) -> float:
    """Convert a mass concentration in {g/L, mg/L, µg/L, ng/L} into g/L."""
    u = unit.strip()
    if u == "g/L":
        return float(value)
    if u == "mg/L":
        return float(value) / 1e3
    if u == "µg/L":
        return float(value) / 1e6
    if u == "ng/L":
        return float(value) / 1e9
    raise ValueError(f"unsupported unit: {unit!r}")
