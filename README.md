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

<table width="100%" style="table-layout: fixed; border-collapse: collapse;">
  <thead style="background-color: rgba(0, 0, 0, 0.05);">
    <tr>
      <th align="right">PubChem CID</th>
      <th align="left">PubChem Name</th>
      <th align="left">Formula</th>
      <th align="right">MW</th>
    </tr>
  </thead>
  <tbody>
    <tr><td align="right">57429219</td><td>Ammonium chloride monohydrate</td><td>ClH6NO</td><td align="right">71.51</td></tr>
    <tr><td align="right">5284359</td><td>Calcium chloride</td><td>CaCl2</td><td align="right">110.98</td></tr>
    <tr><td align="right">24643</td><td>Cobaltous chloride hexahydrate</td><td>Cl2CoH12O6</td><td align="right">237.93</td></tr>
    <tr><td align="right">61482</td><td>Cupric chloride dihydrate</td><td>Cl2CuH4O2</td><td align="right">170.48</td></tr>
    <tr><td align="right">91618179</td><td>Ferric chloride dihydrate</td><td>Cl3FeH4O2</td><td align="right">198.23</td></tr>
    <tr><td align="right">5793</td><td>D-Glucose</td><td>C6H12O6</td><td align="right">180.16</td></tr>
    <tr><td align="right">5360315</td><td>Magnesium chloride</td><td>Cl2Mg</td><td align="right">95.21</td></tr>
    <tr><td align="right">24480</td><td>Manganese (II) chloride</td><td>Cl2Mn</td><td align="right">125.84</td></tr>
    <tr><td align="right">23672064</td><td>Monosodium phosphate</td><td>H2NaO4P</td><td align="right">119.98</td></tr>
    <tr><td align="right">4873</td><td>Potassium chloride</td><td>ClK</td><td align="right">74.55</td></tr>
    <tr><td align="right">23673662</td><td>Sodium bisulfate monohydrate</td><td>H3NaO5S</td><td align="right">138.08</td></tr>
    <tr><td align="right">62640</td><td>Zinc sulfate heptahydrate</td><td>H14O11SZn</td><td align="right">287.60</td></tr>
  </tbody>
</table>


If any CIDs are missing, they are reported explicitly and the optimization
should not be run until resolved.

---

### (2) Compound results (optimized medium)

This table represents the **final optimized medium recipe**.

Key columns:
- **Obtained Concentration** - optimal amount per compound
- **Unit** - automatically scaled (g/L, mg/L, µg/L)
- Values satisfy all elemental constraints while minimizing total compound mass

<table width="100%" style="table-layout: fixed; border-collapse: collapse;">
  <thead style="background-color: rgba(0, 0, 0, 0.05);">
    <tr>
      <th align="right">PubChem CID</th>
      <th align="left">Compound</th>
      <th align="right">MW (g/mol)</th>
      <th align="right">Obtained Concentration</th>
      <th align="left">Unit</th>
    </tr>
  </thead>
  <tbody>
    <tr><td align="right">5360315</td><td>Magnesium chloride</td><td align="right">95.21</td><td align="right">979.33</td><td>mg/L</td></tr>
    <tr><td align="right">4873</td><td>Potassium chloride</td><td align="right">74.55</td><td align="right">953.37</td><td>mg/L</td></tr>
    <tr><td align="right">62640</td><td>Zinc sulfate heptahydrate</td><td align="right">287.60</td><td align="right">87.98</td><td>mg/L</td></tr>
    <tr><td align="right">24480</td><td>Manganese (II) chloride</td><td align="right">125.84</td><td align="right">45.81</td><td>mg/L</td></tr>
    <tr><td align="right">5793</td><td>D-Glucose</td><td align="right">180.16</td><td align="right">25.00</td><td>g/L</td></tr>
    <tr><td align="right">57429219</td><td>Ammonium chloride monohydrate</td><td align="right">71.51</td><td align="right">19.14</td><td>g/L</td></tr>
    <tr><td align="right">24643</td><td>Cobaltous chloride hexahydrate</td><td align="right">237.93</td><td align="right">8.07</td><td>mg/L</td></tr>
    <tr><td align="right">23672064</td><td>Monosodium phosphate</td><td align="right">119.98</td><td align="right">5.87</td><td>g/L</td></tr>
    <tr><td align="right">61482</td><td>Cupric chloride dihydrate</td><td align="right">170.48</td><td align="right">5.37</td><td>mg/L</td></tr>
    <tr><td align="right">5284359</td><td>Calcium chloride</td><td align="right">110.98</td><td align="right">2.77</td><td>g/L</td></tr>
    <tr><td align="right">23673662</td><td>Sodium bisulfate monohydrate</td><td align="right">138.08</td><td align="right">2.11</td><td>g/L</td></tr>
    <tr><td align="right">91618179</td><td>Ferric chloride dihydrate</td><td align="right">198.23</td><td align="right">1.77</td><td>g/L</td></tr>
  </tbody>
</table>


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

<table width="100%" style="table-layout: fixed; border-collapse: collapse;">
  <thead style="background-color: rgba(0, 0, 0, 0.05);">
    <tr>
      <th align="center">Element</th>
      <th align="right">Reference Yield (gCDW/g)</th>
      <th align="right">Excess Factor</th>
      <th align="right">Required Mass</th>
      <th align="right">Obtained Mass</th>
      <th align="left">Unit</th>
      <th align="right">Match (%)</th>
    </tr>
  </thead>
  <tbody>
    <tr><td align="center">C</td><td align="right">1</td><td align="right">1</td><td align="right">10.00</td><td align="right">10.00</td><td>g/L</td><td align="right">100.0</td></tr>
    <tr><td align="center">N</td><td align="right">8</td><td align="right">3</td><td align="right">3.75</td><td align="right">3.75</td><td>g/L</td><td align="right">100.0</td></tr>
    <tr><td align="center">P</td><td align="right">33</td><td align="right">5</td><td align="right">1515.15</td><td align="right">1515.15</td><td>mg/L</td><td align="right">100.0</td></tr>
    <tr><td align="center">Ca</td><td align="right">100</td><td align="right">10</td><td align="right">1000.00</td><td align="right">1000.00</td><td>mg/L</td><td align="right">100.0</td></tr>
    <tr><td align="center">S</td><td align="right">100</td><td align="right">5</td><td align="right">500.00</td><td align="right">500.00</td><td>mg/L</td><td align="right">100.0</td></tr>
    <tr><td align="center">K</td><td align="right">100</td><td align="right">5</td><td align="right">500.00</td><td align="right">500.00</td><td>mg/L</td><td align="right">100.0</td></tr>
    <tr><td align="center">Fe</td><td align="right">200</td><td align="right">10</td><td align="right">500.00</td><td align="right">500.00</td><td>mg/L</td><td align="right">100.0</td></tr>
    <tr><td align="center">Mg</td><td align="right">200</td><td align="right">5</td><td align="right">250.00</td><td align="right">250.00</td><td>mg/L</td><td align="right">100.0</td></tr>
    <tr><td align="center">Mn</td><td align="right">10000</td><td align="right">20</td><td align="right">20.00</td><td align="right">20.00</td><td>mg/L</td><td align="right">100.0</td></tr>
    <tr><td align="center">Zn</td><td align="right">10000</td><td align="right">20</td><td align="right">20.00</td><td align="right">20.00</td><td>mg/L</td><td align="right">100.0</td></tr>
    <tr><td align="center">Cu</td><td align="right">100000</td><td align="right">20</td><td align="right">2000.00</td><td align="right">2000.00</td><td>µg/L</td><td align="right">100.0</td></tr>
    <tr><td align="center">Co</td><td align="right">100000</td><td align="right">20</td><td align="right">2000.00</td><td align="right">2000.00</td><td>µg/L</td><td align="right">100.0</td></tr>
  </tbody>
</table>


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