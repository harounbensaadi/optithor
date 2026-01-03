# src/optithor/__init__.py

"""optithor - Linear-programming based medium optimization toolkit."""

from .__about__ import __version__
from .compound_db import CompoundDb
from .medium_optimizer import optimize_medium
from .utils import (
    elemental_counts,
    format_mass_with_unit,
    mass_to_g_per_l,
    molar_mass,
    molar_mass_h2o,
    split_hydrate_formula,
)

__all__ = [
    "__version__",
    "CompoundDb",
    "optimize_medium",
    "molar_mass",
    "molar_mass_h2o",
    "split_hydrate_formula",
    "elemental_counts",
    "format_mass_with_unit",
    "mass_to_g_per_l",
]
