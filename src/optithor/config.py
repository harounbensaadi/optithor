# src/optithor/config.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True, slots=True)
class SolverConfig:
    # -----------------------------
    # Linear solver configuration
    # -----------------------------
    default_cost: float = 1.0
    lower_bound: float = 0.0
    upper_bound: float = 1000.0
    method: str = "highs"

    # -----------------------------
    # Chemistry / elements
    # -----------------------------
    elements: List[str] = field(
        default_factory=lambda: [
            "C", "H", "O", "N", "S", "P",
            "Cl", "Na", "K", "Mg", "Ca",
            "Fe", "Mn", "Zn", "Cu", "Co",
            "Mo", "Ni", "Br",
        ]
    )

    # -----------------------------
    # Biological reference values
    # g CDW / g Element
    # -----------------------------
    reference_values: Dict[str, float] = field(
        default_factory=lambda: {
            "C": 1,
            "N": 8,
            "S": 100,
            "P": 33,
            "K": 100,
            "Mg": 200,
            "Ca": 100,
            "Fe": 200,
            "Mn": 1e4,
            "Zn": 1e4,
            "Cu": 1e5,
            "Co": 1e5,
            "Cl": 0,
            "Na": 0,
            "Mo": 0,
            "Ni": 0,
            "Br": 0,
        }
    )

    # -----------------------------
    # Excess allowance factors
    # -----------------------------
    excess_factors: Dict[str, float] = field(
        default_factory=lambda: {
            "C": 1,
            "N": 3,
            "S": 5,
            "P": 5,
            "K": 5,
            "Mg": 5,
            "Ca": 10,
            "Fe": 10,
            "Mn": 20,
            "Zn": 20,
            "Cu": 20,
            "Co": 20,
            "Cl": 0,
            "Na": 0,
            "Mo": 0,
            "Ni": 0,
            "Br": 0,
        }
    )

    # -----------------------------
    # Biomass constraint
    # -----------------------------
    max_produced_dry_biomass: float = 10.0  # g CDW / L
