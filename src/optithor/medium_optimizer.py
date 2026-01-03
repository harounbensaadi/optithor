# src/optithor/medium_optimizer.py

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import SolverConfig
from .lp_solver import solve_linear_program
from .paths import ensure_db_schema
from .types import CompoundDose, ElementMatch, MediumOptimizationInput, MediumOptimizationResult
from .utils import elemental_counts, molar_mass


def optimize_medium(
    medium_input: MediumOptimizationInput,
    compound_repository,
    solver_config: SolverConfig | None = None,
) -> MediumOptimizationResult:
    solver_config = solver_config or SolverConfig()

    compounds_df = compound_repository.get_compounds_by_cids(medium_input.compound_cids)
    if compounds_df.empty:
        return MediumOptimizationResult(
            success=False,
            message="no compounds found for provided cids",
            compound_doses=[],
            element_matches=[],
            diagnostics="repository returned an empty dataframe",
        )

    compounds_df = ensure_db_schema(compounds_df)

    # --- build requirements
    requirement_rows = []
    for element, req in medium_input.required_elements.items():
        if req.reference_yield_g_cdw_per_g <= 0 or req.excess_factor <= 0:
            continue

        ref_mass = medium_input.max_dry_biomass_g_per_l / req.reference_yield_g_cdw_per_g
        required_mass = ref_mass * req.excess_factor
        required_mol = required_mass / molar_mass(element)

        requirement_rows.append((element, required_mass, required_mol))

    if not requirement_rows:
        return MediumOptimizationResult(
            success=False,
            message="no valid element requirements provided",
            compound_doses=[],
            element_matches=[],
            diagnostics="all elements had non-positive yield or excess factor",
        )

    requirements_df = pd.DataFrame(
        requirement_rows,
        columns=[
            "Element",
            "Required Element Mass [g/L]",
            "Required Element Quantity [mol/L]",
        ],
    )

    selected_elements = requirements_df["Element"].tolist()

    # --- elemental counts (from anhydrous formula)
    for element in selected_elements:
        compounds_df[element] = 0

    for idx, row in compounds_df.iterrows():
        counts = elemental_counts(str(row["Formula (-H2O)"]), selected_elements)
        for element in selected_elements:
            compounds_df.at[idx, element] = counts[element]

    selected_compounds_df = compounds_df[["PubChem CID"] + selected_elements]

    a_eq = selected_compounds_df[selected_elements].to_numpy(dtype=float).T
    b_eq = requirements_df["Required Element Quantity [mol/L]"].to_numpy(dtype=float)

    solution = solve_linear_program(
        a_eq=a_eq,
        b_eq=b_eq,
        num_variables=a_eq.shape[1],
        solver_config=solver_config,
    )

    if not solution.success or solution.x is None:
        diagnostics = analyze_unsolvable_system(
            b_eq=b_eq,
            selected_compounds_df=selected_compounds_df,
            selected_elements=selected_elements,
        )
        return MediumOptimizationResult(
            success=False,
            message=f"optimization could not be solved: {solution.message}",
            compound_doses=[],
            element_matches=[],
            diagnostics=diagnostics,
        )

    # --- doses
    mol_per_l = solution.x
    mw_hydrated = compounds_df["MW"].to_numpy(dtype=float)
    mass_g_per_l = mol_per_l * mw_hydrated

    compound_doses = [
        CompoundDose(cid=str(cid), mass_g_per_l=float(m), mol_per_l=float(n))
        for cid, m, n in zip(
            compounds_df["PubChem CID"].astype(str),
            mass_g_per_l,
            mol_per_l,
        )
        if np.isfinite(m) and m > 0
    ]
    compound_doses.sort(key=lambda d: d.mass_g_per_l, reverse=True)

    # --- element matches
    element_matches = []
    for _, row in requirements_df.iterrows():
        element = row["Element"]
        required_mass = float(row["Required Element Mass [g/L]"])

        obtained_mol = float((compounds_df[element].to_numpy(dtype=float) * mol_per_l).sum())
        obtained_mass = obtained_mol * molar_mass(element)

        match_percent = (obtained_mass / required_mass) * 100 if required_mass > 0 else 0.0

        element_matches.append(
            ElementMatch(
                element=str(element),
                required_mass_g_per_l=required_mass,
                obtained_mass_g_per_l=float(obtained_mass),
                match_percent=float(match_percent),
            )
        )

    return MediumOptimizationResult(
        success=True,
        message=solution.message,
        compound_doses=compound_doses,
        element_matches=element_matches,
        diagnostics=None,
    )


def analyze_unsolvable_system(
    b_eq: np.ndarray,
    selected_compounds_df: pd.DataFrame,
    selected_elements: list[str],
) -> str:
    num_constraints = len(b_eq)

    missing_elements = [
        element
        for element in selected_elements
        if element not in selected_compounds_df.columns
        or selected_compounds_df[element].sum() == 0
    ]

    message_parts = [
        f"A total of {num_constraints} constraints were applied to match required elements with available compounds."
    ]

    if missing_elements:
        if len(missing_elements) == 1:
            message_parts.append(
                f"However, the required element '{missing_elements[0]}' is missing or not present in the provided compounds."
            )
        else:
            message_parts.append(
                f"However, the following {len(missing_elements)} elements are missing or not present in the provided compounds: "
                f"{', '.join(missing_elements)}."
            )
        message_parts.append(
            "Please ensure that the input compounds contain these missing elements or review the required constraints."
        )
    else:
        message_parts.append(
            "All required elements were found in the provided compounds, but the constraints could not be satisfied. "
            "This may be due to insufficient compound availability or conflicting constraints."
        )

    return " ".join(message_parts)
