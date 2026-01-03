[![PyPI version](https://img.shields.io/pypi/v/optithor.svg)](https://pypi.org/project/optithor/)
[![Python versions](https://img.shields.io/pypi/pyversions/optithor.svg)](https://pypi.org/project/optithor/)
[![License](https://img.shields.io/pypi/l/optithor.svg)](https://pypi.org/project/optithor/)
[![CI](https://github.com/harounbensaadi/optithor/actions/workflows/ci.yml/badge.svg)](https://github.com/harounbensaadi/optithor/actions/workflows/ci.yml)

# OptiThor

**OptiThor** is a Python package for **linear-programming-based optimization of microbial growth media** under elemental stoichiometric constraints.

Given:
- a set of candidate compounds (identified by PubChem CIDs),
- elemental growth requirements (e.g. C, N, P, S, other trace metals),
- and a target biomass yield,

OptiThor computes the **optimal compound concentrations** that satisfy all elemental requirements while **minimizing total compound mass**.

The package ships with a **pre-built compound database** derived from PubChem, so no external data preparation is required for most use cases.

---

## Installation

```bash
pip install optithor

```

**Python requirement:** ≥ 3.10

---

## Quick check (successful installation)

```python
from optithor import CompoundDb

db = CompoundDb().load()
print(db.head())
```

This confirms that the packaged compound database is available and readable.

---

## Real example: optimizing a defined medium

This is a real, end-to-end example using actual PubChem CIDs and real elemental requirements, identical in logic to **examples/basic_usage.py**.

```python
from optithor import CompoundDb, optimize_medium
from optithor.config import SolverConfig
from optithor.types import ElementRequirement, MediumOptimizationInput
from optithor.reports import (
    build_selected_cids_table,
    build_optimization_tables,
)

repo = CompoundDb()

compound_cids = [
    "57429219", "5284359", "24643", "61482", "91618179",
    "5793", "5360315", "24480", "23672064", "4873",
    "23673662", "62640",
]

selected_df = build_selected_cids_table(
    compound_repository=repo,
    compound_cids=compound_cids,
    force_reload=False,
)

print("\n=== Selected compounds (from DB) ===")
print(selected_df.to_string(index=False))

reference_yields = {
    "C": 1, "N": 8, "S": 100, "P": 33, "K": 100,
    "Mg": 200, "Ca": 100, "Fe": 200,
    "Mn": 1e4, "Zn": 1e4, "Cu": 1e5, "Co": 1e5,
}

excess_factors = {
    "C": 1, "N": 3, "S": 5, "P": 5, "K": 5,
    "Mg": 5, "Ca": 10, "Fe": 10,
    "Mn": 20, "Zn": 20, "Cu": 20, "Co": 20,
}

required_elements = {
    e: ElementRequirement(
        reference_yield_g_cdw_per_g=reference_yields[e],
        excess_factor=excess_factors[e],
    )
    for e in reference_yields
}

medium_input = MediumOptimizationInput(
    compound_cids=compound_cids,
    required_elements=required_elements,
    max_dry_biomass_g_per_l=10.0,
)

result = optimize_medium(
    medium_input=medium_input,
    compound_repository=repo,
    solver_config=SolverConfig(),
)

print("\nSuccess:", result.success)
print("Message:", result.message)

tables = build_optimization_tables(
    medium_input=medium_input,
    result=result,
    compound_repository=repo,
    decimals=2,
    include_anhydrous_mass=False,
)

print("\n=== Compounds results table ===")
print(tables.compounds.to_string(index=False))

print("\n=== Element validation table ===")
print(tables.elements.to_string(index=False))
```

---
Running the example produces three tables.

### (1) Selected compounds

This table lists the compounds found in the local database **before optimization**.

Purpose:
- Confirms that all requested PubChem CIDs exist in the database
- Shows the molecular formula and molar mass used internally
- Detects missing compounds early (before solving)

| PubChem CID | PubChem Name                   | Formula        | MW    |
|------------:|--------------------------------|----------------|-------|
| 57429219    | Ammonium chloride monohydrate  | ClH6NO         | 71.51 |
| 5284359     | Calcium chloride               | CaCl2          | 110.98 |
| 24643       | Cobaltous chloride hexahydrate | Cl2CoH12O6     | 237.93 |
| 61482       | Cupric chloride dihydrate      | Cl2CuH4O2      | 170.48 |
| 91618179    | Ferric chloride dihydrate      | Cl3FeH4O2      | 198.23 |
| 5793        | D-Glucose                      | C6H12O6        | 180.16 |
| 5360315     | Magnesium chloride             | Cl2Mg          | 95.21 |
| 24480       | Manganese (II) chloride        | Cl2Mn          | 125.84 |
| 23672064    | Monosodium phosphate           | H2NaO4P        | 119.98 |
| 4873        | Potassium chloride             | ClK            | 74.55 |
| 23673662    | Sodium bisulfate monohydrate   | H3NaO5S        | 138.08 |
| 62640       | Zinc sulfate heptahydrate      | H14O11SZn      | 287.60 |

If any CIDs are missing, they are reported explicitly and the optimization
should not be run until resolved.

---

### (2) Compound results (optimized medium)

This table represents the **final optimized medium recipe**.

Key columns:
- **Obtained Concentration** - optimal amount per compound
- **Unit** - automatically scaled (g/L, mg/L, µg/L)
- Values satisfy all elemental constraints while minimizing total compound mass

| PubChem CID | Compound                       | MW (g/mol) | Obtained Concentration | Unit |
|------------:|--------------------------------|-----------:|------------------------:|:-----|
| 5360315     | Magnesium chloride             | 95.21      | 979.33                  | mg/L |
| 4873        | Potassium chloride             | 74.55      | 953.37                  | mg/L |
| 62640       | Zinc sulfate heptahydrate      | 287.60     | 87.98                   | mg/L |
| 24480       | Manganese (II) chloride        | 125.84     | 45.81                   | mg/L |
| 5793        | D-Glucose                      | 180.16     | 25.00                   | g/L |
| 57429219    | Ammonium chloride monohydrate  | 71.51      | 19.14                   | g/L |
| 24643       | Cobaltous chloride hexahydrate | 237.93     | 8.07                    | mg/L |
| 23672064    | Monosodium phosphate           | 119.98     | 5.87                    | g/L |
| 61482       | Cupric chloride dihydrate      | 170.48     | 5.37                    | mg/L |
| 5284359     | Calcium chloride               | 110.98     | 2.77                    | g/L |
| 23673662    | Sodium bisulfate monohydrate   | 138.08     | 2.11                    | g/L |
| 91618179    | Ferric chloride dihydrate      | 198.23     | 1.77                    | g/L |

Interpretation:
- High concentrations correspond to **bulk nutrients** (C, N, major salts)
- Low concentrations typically supply **trace elements**
- This is a **mathematical optimum**, not an experimentally validated recipe

---

### (3) Element validation table

This table verifies that all elemental constraints are satisfied.

Key columns:
- **Reference Yield** - biological assumption (g CDW per g element)
- **Excess Factor** - safety margin applied
- **Required Mass** - target elemental mass after excess
- **Obtained Mass** - mass supplied by the optimized medium
- **Match (%)** - agreement between required and obtained values

| Element | Reference Yield (gCDW/g) | Excess Factor | Required Mass | Obtained Mass | Unit | Match (%) |
|:------:|------------------------:|--------------:|--------------:|--------------:|:-----:|----------:|
| C  | 1      | 1  | 10.00  | 10.00  | g/L  | 100.0 |
| N  | 8      | 3  | 3.75   | 3.75   | g/L  | 100.0 |
| P  | 33     | 5  | 1515.15 | 1515.15 | mg/L | 100.0 |
| Ca | 100    | 10 | 1000.00 | 1000.00 | mg/L | 100.0 |
| S  | 100    | 5  | 500.00 | 500.00 | mg/L | 100.0 |
| K  | 100    | 5  | 500.00 | 500.00 | mg/L | 100.0 |
| Fe | 200    | 10 | 500.00 | 500.00 | mg/L | 100.0 |
| Mg | 200    | 5  | 250.00 | 250.00 | mg/L | 100.0 |
| Mn | 10000  | 20 | 20.00  | 20.00  | mg/L | 100.0 |
| Zn | 10000  | 20 | 20.00  | 20.00  | mg/L | 100.0 |
| Cu | 100000 | 20 | 2000.00 | 2000.00 | µg/L | 100.0 |
| Co | 100000 | 20 | 2000.00 | 2000.00 | µg/L | 100.0 |

A **100% match** indicates that the solver satisfied the constraint
within numerical tolerance.


## Core concepts

### Compound database

OptiThor ships with a **pre-generated, offline compound database** containing
molecular formulas, molar masses, elemental composition, and hydrate handling.

```python
from optithor import CompoundDb
repo = CompoundDb()
```

On first use, the packaged database (shipped in the wheel) is copied into a
**user-writable local cache**. Subsequent runs use this cache and **no network
access occurs by default**.

To reset the local cache to the packaged database:

```python
repo.load(force_reload=True)
```

---

### PubChem CIDs

Compounds are referenced using **PubChem Compound IDs (CIDs)** provided as strings:

```python
compound_cids = ["5793", "4873", "62640"]
```

---

### Elemental requirements

Elemental constraints are defined using `ElementRequirement`:

```python
ElementRequirement(
    reference_yield_g_cdw_per_g=...,  # g CDW per g element
    excess_factor=...,                # safety margin
)
```

These parameters encode **biological assumptions** and must be adapted to the
organism and growth model.

---

### Optimization model

OptiThor formulates a **linear programming problem** that:
- satisfies elemental requirements,
- respects compound availability,
- minimizes total compound mass.

Default solver settings are suitable for most use cases.

---

## Advanced usage

### Fetching missing compounds from PubChem

To explicitly allow network access and fetch missing compounds from PubChem:

```python
df = repo.get_compounds_by_cids(
    compound_cids,
    fetch_missing=True,
    update_cache=True,
)
```

⚠️ PubChem is **never accessed unless explicitly requested**.

---

### Diagnostics and reporting tables

```python
from optithor.reports import build_optimization_tables

tables = build_optimization_tables(
    medium_input=medium_input,
    result=result,
    compound_repository=repo,
    decimals=2,
)

tables.compounds
tables.elements
```

Returned objects are Pandas DataFrames and can be exported or plotted.

---

## Project structure

```text
src/optithor/
    resources/           # Packaged compound database
examples/                # Usage examples
tests/                   # Test suite
compound_db_builder/     # Database construction pipeline
pyproject.toml
README.md
CONTRIBUTING.md
LICENSE
```

The `compound_db_builder/` directory documents how the packaged compound
database was generated and curated. It is **not required for normal usage**
of OptiThor and is **not used at runtime**, but is included for transparency
and reproducibility.

---

## Contributing

Contributions are welcome.

Please open an issue or pull request on GitHub.

Contribution guidelines:
https://github.com/harounbensaadi/optithor/blob/main/CONTRIBUTING.md

---

## Citation

If you use OptiThor in **academic work**, please cite or reference this repository.

---

## License

MIT License