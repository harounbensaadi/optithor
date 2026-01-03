[![PyPI version](https://img.shields.io/pypi/v/optithor.svg)](https://pypi.org/project/optithor/)
[![Python versions](https://img.shields.io/pypi/pyversions/optithor.svg)](https://pypi.org/project/optithor/)
[![License](https://img.shields.io/pypi/l/optithor.svg)](https://pypi.org/project/optithor/)
[![CI](https://github.com/harounbensaadi/optithor/actions/workflows/ci.yml/badge.svg)](https://github.com/harounbensaadi/optithor/actions/workflows/ci.yml)

# OptiThor

**OptiThor** is a Python package for **linear-programming–based optimization of microbial growth media** under elemental stoichiometric constraints.

Given:
- a set of candidate compounds (identified by PubChem CIDs),
- elemental growth requirements (e.g. C, N, P, S),
- and a target biomass yield,

OptiThor computes the **optimal compound concentrations** that satisfy elemental requirements while minimizing total compound mass.

The package ships with a **pre-built compound database** derived from PubChem, so no external data preparation is required for most use cases.

---

## Installation

```bash
pip install optithor

```

**Python requirement:** ≥ 3.10

---
## Quick example

```python
from optithor import CompoundDb

db = CompoundDb().load()
print(db.head())

```
---

## Quick start (minimal example)

```python
from optithor import CompoundDb, optimize_medium
from optithor.types import ElementRequirement, MediumOptimizationInput

repo = CompoundDb()

compound_cids = [
    "57429219",
    "5284359",
    "24643",
    "61482",
]

required_elements = {
    "C": ElementRequirement(reference_yield_g_cdw_per_g=1.0, excess_factor=1.0),
    "N": ElementRequirement(reference_yield_g_cdw_per_g=8.0, excess_factor=3.0),
    "P": ElementRequirement(reference_yield_g_cdw_per_g=33.0, excess_factor=5.0),
}

medium_input = MediumOptimizationInput(
    compound_cids=compound_cids,
    required_elements=required_elements,
    max_dry_biomass_g_per_l=10.0,
)

result = optimize_medium(
    medium_input=medium_input,
    compound_repository=repo,
)

if not result.success:
    raise RuntimeError(result.message)

print(result.solution)

```
---

## Understanding the results

Running the basic example produces three main outputs:  
(1) selected compounds, (2) optimized compound concentrations, and (3) elemental validation.

---

### Selected compounds

The first table lists the compounds found in the local database:

- Confirms that all requested PubChem CIDs exist in the database
- Shows the molecular formula and molar mass used internally
- If a CID is missing, it is reported explicitly

---

### Compounds results table

The **compounds results table** shows the optimized medium composition.

Key columns:
- **Obtained Compound Concentration**: the optimal amount of each compound
- **Unit**: concentrations are automatically reported in sensible units (g/L, mg/L, µg/L)
- Values satisfy all elemental constraints while minimizing total compound mass

Important notes:
- Some compounds appear at very low concentrations because they supply trace elements
- Major nutrients (e.g. carbon or nitrogen sources) appear at higher concentrations
- The solution is a **mathematical optimum**, not a validated experimental recipe

---

### Element validation table

The **element validation table** verifies that elemental requirements are met.

Key columns:
- **Reference Elemental Growth Yield**: biological assumption (g CDW per g element)
- **Excess Factor**: safety margin applied to the requirement
- **Required Element Mass**: target elemental amount after applying excess
- **Obtained Element Mass**: elemental mass supplied by the optimized medium
- **Match (%)**: agreement between required and obtained values

A match of **100%** indicates that the solver satisfied the constraint exactly (within numerical tolerance).

---

## Core concepts

### Compound database

OptiThor ships with a **pre-generated compound database** containing molecular formulas, molar masses, elemental composition, and hydrate handling.

The database is accessed via:

```python
from optithor import CompoundDb
repo = CompoundDb()
```

**Cache behavior**

- On first use, the packaged database (shipped in the wheel) is copied into a **user-writable local cache**
- Subsequent runs read from this local cache
- No network access occurs by default

If needed, the local cache can be **reset to the packaged database**:

```python
repo.load(force_reload=True)
```

This overwrites the local cache using the database shipped in the installed wheel.

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
    reference_yield_g_cdw_per_g=...,  # grams CDW per gram of element
    excess_factor=...,                # oversupply safety factor
)
```

These parameters are **biological assumptions** and must be adapted to the organism and growth model.

---

### Optimization model

The optimization problem is solved using linear programming and aims to:
- satisfy elemental requirements,
- respect compound availability,
- minimize total compound mass.

Solver behavior can be customized, but default settings are suitable for most use cases.

---

## Inspecting compound availability

To see which requested compounds exist in the local database:

```python
from optithor.reports import build_selected_cids_table

df = build_selected_cids_table(
    compound_repository=repo,
    compound_cids=compound_cids,
    force_reload=False,
)

print(df)
```

This operation is **offline** and uses the local cache.

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

Fetched compounds are optionally written back into the local cache.

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

## Assumptions and limitations

- Elemental formulas are parsed using simplified chemical rules
- Hydrates are handled via an anhydrous-equivalent representation
- Optimization assumes linear, additive stoichiometry
- Biological yield parameters must be provided by the user

OptiThor is intended as a **design and exploration tool**, not a substitute for experimental validation.

---

## Project structure

```text
    src/optithor/            # Core OptiThor package (runtime code)
        resources/           # Packaged compound database (Parquet)
    examples/                # Usage examples (basic + advanced)
    tests/                   # Test suite (pytest)
    compound_db_builder/     # Database construction pipeline (for transparency)
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

If you would like to:
- report a bug,
- suggest an improvement,
- add new features,
- improve documentation or examples,

please open an issue or a pull request on GitHub.

Before contributing code, please read the contribution guidelines:
https://github.com/harounbensaadi/optithor/blob/main/CONTRIBUTING.md

---

## Citation

If you use OptiThor in **academic work**, please cite or reference this repository.

---

## License

MIT License
