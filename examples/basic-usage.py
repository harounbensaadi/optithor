# examples/basic_usage.py

# ---------------------------------------------------------------------
# What this example demonstrates
#
# This is a BASIC, end-to-end OptiThor example.
#
# It shows:
# 1) How to select a known-good set of compounds (PubChem CIDs)
# 2) How to verify their availability in the local compound DB (offline)
# 3) How to define elemental requirements
# 4) How to run a feasible medium optimization
# 5) How to inspect results via built-in reporting tables
#
# NOTES:
# - The current compound CIDs and element parameters are chosen to ensure 
#   a FEASIBLE optimization problem.
# - Changing compounds or constraints may lead to infeasible solutions.
# ---------------------------------------------------------------------

from optithor import CompoundDb, optimize_medium
from optithor.config import SolverConfig
from optithor.reports import build_optimization_tables, build_selected_cids_table
from optithor.types import ElementRequirement, MediumOptimizationInput

def main() -> None:
    # Load compound database (packaged DB via local cache)
    repo = CompoundDb()

    # -----------------------------------------------------------------
    # Candidate compounds
    #
    # These CIDs are known to be present in the shipped database and to
    # form a FEASIBLE optimization problem with the parameters below.
    # -----------------------------------------------------------------
    compound_cids = [
        "57429219",  # Ammonium chloride monohydrate — ClH6NO
        "5284359",   # Calcium chloride — CaCl2
        "24643",     # Cobaltous chloride hexahydrate — Cl2CoH12O6
        "61482",     # Cupric chloride dihydrate — Cl2CuH4O2
        "91618179",  # Ferric chloride dihydrate — Cl3FeH4O2
        "5793",      # D-Glucose — C6H12O6
        "5360315",   # Magnesium chloride — Cl2Mg
        "24480",     # Manganese(II) chloride — Cl2Mn
        "23672064",  # Monosodium phosphate — H2NaO4P
        "4873",      # Potassium chloride — ClK
        "23673662",  # Sodium bisulfate monohydrate — H3NaO5S
        "62640",     # Zinc sulfate heptahydrate — H14O11SZn
    ]

    # -----------------------------------------------------------------
    # Inspect which compounds are available locally (offline)
    # -----------------------------------------------------------------
    selected_df = build_selected_cids_table(
        compound_repository=repo,
        compound_cids=compound_cids,
        force_reload=False,
    )

    print("\n=== Selected compounds (from DB) ===")
    if selected_df.empty:
        print("(empty)")
    else:
        print(selected_df.to_string(index=False))

    found_cids = set(selected_df["PubChem CID"].astype(str))
    missing = [c for c in compound_cids if c not in found_cids]

    print(f"\nRequested: {len(compound_cids)}")
    print(f"Found:     {len(found_cids)}")
    print("Missing CIDs:", missing if missing else "(none)")

    # -----------------------------------------------------------------
    # Elemental requirements
    #
    # These values are deliberately chosen to:
    #   - be biologically reasonable
    #   - avoid infeasible LP solutions
    #
    # Users should adapt these values for their organism.
    # -----------------------------------------------------------------
    reference_values_default = {
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
    }

    excess_factors_default = {
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
    }

    required_elements = {
        element: ElementRequirement(
            reference_yield_g_cdw_per_g=reference_values_default[element],
            excess_factor=excess_factors_default[element],
        )
        for element in reference_values_default
    }

    medium_input = MediumOptimizationInput(
        compound_cids=compound_cids,
        required_elements=required_elements,
        max_dry_biomass_g_per_l=10.0,
    )

    # -----------------------------------------------------------------
    # Run optimization
    # -----------------------------------------------------------------
    result = optimize_medium(
        medium_input=medium_input,
        compound_repository=repo,
        solver_config=SolverConfig(),
    )

    print("\nSuccess:", result.success)
    print("Message:", result.message)

    if result.diagnostics:
        print("\nDiagnostics:\n", result.diagnostics)

    # -----------------------------------------------------------------
    # Build reporting tables
    # -----------------------------------------------------------------
    tables = build_optimization_tables(
        medium_input=medium_input,
        result=result,
        compound_repository=repo,
        decimals=2,
        include_anhydrous_mass=False,
    )

    print("\n=== Compounds results table ===")
    if tables.compounds.empty:
        print("(empty)")
    else:
        print(tables.compounds.to_string(index=False))

    print("\n=== Element validation table ===")
    if tables.elements.empty:
        print("(empty)")
    else:
        print(tables.elements.to_string(index=False))


if __name__ == "__main__":
    main()