from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ElementRequirement:
    """
    reference_yield_g_cdw_per_g:
        Reference elemental growth yield (gCDW / gElement).
    excess_factor:
        Multiply the reference requirement by this factor.
    """
    reference_yield_g_cdw_per_g: float
    excess_factor: float


@dataclass(frozen=True)
class MediumOptimizationInput:
    compound_cids: List[str]
    max_dry_biomass_g_per_l: float
    required_elements: Dict[str, ElementRequirement]


@dataclass(frozen=True)
class CompoundDose:
    cid: str
    mass_g_per_l: float
    mol_per_l: float


@dataclass(frozen=True)
class ElementMatch:
    element: str
    required_mass_g_per_l: float
    obtained_mass_g_per_l: float
    match_percent: float


@dataclass(frozen=True)
class MediumOptimizationResult:
    success: bool
    message: str
    compound_doses: List[CompoundDose]
    element_matches: List[ElementMatch]
    diagnostics: Optional[str] = None
