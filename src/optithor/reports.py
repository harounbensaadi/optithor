# src/optithor/reports.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np
import pandas as pd

from optithor.types import MediumOptimizationInput, MediumOptimizationResult


def format_mass_and_unit(value_g_per_l: float, *, decimals: int = 2) -> tuple[float, str]:
    """
    Convert g/L -> (value, unit) with human-readable scaling.
    """
    if value_g_per_l is None or not np.isfinite(value_g_per_l):
        return float("nan"), ""

    v = float(value_g_per_l)
    if v >= 1:
        return round(v, decimals), "g/L"
    if v >= 1e-3:
        return round(v * 1e3, decimals), "mg/L"
    if v >= 1e-6:
        return round(v * 1e6, decimals), "µg/L"
    return round(v * 1e9, decimals), "ng/L"


def _scale_to_unit(value_g_per_l: float, unit: str, *, decimals: int = 2) -> float:
    """
    Scale value in g/L to a chosen unit.
    """
    if value_g_per_l is None or not np.isfinite(value_g_per_l):
        return float("nan")

    v = float(value_g_per_l)
    if unit == "g/L":
        return round(v, decimals)
    if unit == "mg/L":
        return round(v * 1e3, decimals)
    if unit == "µg/L":
        return round(v * 1e6, decimals)
    if unit == "ng/L":
        return round(v * 1e9, decimals)
    return round(v, decimals)


def _choose_unit_from_min_mass(values_g_per_l: Iterable[float]) -> str:
    """
    Pick a unit based on the minimum non-zero mass in the set.
    """
    vals = [float(v) for v in values_g_per_l if v is not None and np.isfinite(v) and float(v) > 0]
    if not vals:
        return "g/L"
    min_v = min(vals)
    _, unit = format_mass_and_unit(min_v)
    return unit


def _ensure_repo_df_schema(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure expected DB columns exist and are typed.

    Expected DB schema (optithor):
      - PubChem CID
      - PubChem Name
      - Formula
      - Formula (-H2O)
      - MW
      - MW (-H2O)

    Also tolerates older DBs using "Molecular Weight".
    """
    out = df.copy()

    if "PubChem CID" in out.columns:
        out["PubChem CID"] = (
            out["PubChem CID"]
            .astype(str)
            .str.strip()
            .str.replace(r"\.0$", "", regex=True)
        )

    if "MW" not in out.columns and "Molecular Weight" in out.columns:
        out["MW"] = out["Molecular Weight"]

    if "MW" in out.columns:
        out["MW"] = pd.to_numeric(out["MW"], errors="coerce")
    if "MW (-H2O)" in out.columns:
        out["MW (-H2O)"] = pd.to_numeric(out["MW (-H2O)"], errors="coerce")

    return out


def build_selected_cids_table(
    compound_repository: Any,
    compound_cids: Iterable[str | int],
    *,
    force_reload: bool = False,
) -> pd.DataFrame:
    """
    Table of what the user selected vs what exists in the DB.

    Returns columns (if available):
      - PubChem CID
      - PubChem Name
      - Formula
      - MW

    Row order follows the input CID order.
    """
    wanted = [
        str(c).strip().removesuffix(".0")
        for c in compound_cids
        if str(c).strip()
    ]
    if not wanted:
        return pd.DataFrame(columns=["PubChem CID", "PubChem Name", "Formula", "MW"])

    df = compound_repository.get_compounds_by_cids(wanted, force_reload=force_reload)
    if df is None or df.empty:
        return pd.DataFrame({"PubChem CID": wanted})

    df = _ensure_repo_df_schema(df)

    cols = [c for c in ["PubChem CID", "PubChem Name", "Formula", "MW"] if c in df.columns]
    df = df[cols].copy()

    wanted_index = {cid: i for i, cid in enumerate(wanted)}
    df["_order"] = df["PubChem CID"].astype(str).map(lambda x: wanted_index.get(x, 10**9))
    df = df.sort_values("_order", kind="mergesort").drop(columns=["_order"])

    return df.reset_index(drop=True)


def build_compounds_results_table(
    result: MediumOptimizationResult,
    compound_repository: Any,
    *,
    decimals: int = 2,
    include_anhydrous_mass: bool = False,
) -> pd.DataFrame:
    base_cols = [
        "PubChem CID",
        "PubChem Name",
        "Formula",
        "MW [g/mol]",
        "Obtained Compound Concentration",
        "Unit",
    ]

    if not result.success or not getattr(result, "compound_doses", None):
        return pd.DataFrame(columns=base_cols)

    doses_df = pd.DataFrame(
        [
            {
                "PubChem CID": str(d.cid).strip(),
                "Obtained Compound Quantity [mol/L]": float(d.mol_per_l),
                "Obtained Compound Mass [g/L]": float(d.mass_g_per_l),
            }
            for d in result.compound_doses
        ]
    )

    cids = doses_df["PubChem CID"].astype(str).tolist()
    meta_df = compound_repository.get_compounds_by_cids(cids)
    meta_df = _ensure_repo_df_schema(meta_df)

    keep_cols = [c for c in ["PubChem CID", "PubChem Name", "Formula", "MW", "MW (-H2O)"] if c in meta_df.columns]
    meta_df = meta_df[keep_cols].copy()

    merged = pd.merge(doses_df, meta_df, on="PubChem CID", how="left")

    formatted = merged["Obtained Compound Mass [g/L]"].apply(
        lambda x: pd.Series(format_mass_and_unit(x, decimals=decimals))
    )
    merged["Obtained Compound Concentration"] = formatted[0]
    merged["Unit"] = formatted[1]

    if include_anhydrous_mass and "MW (-H2O)" in merged.columns:
        merged["Obtained Compound Mass (-H2O) [g/L]"] = (
            merged["Obtained Compound Quantity [mol/L]"] * pd.to_numeric(merged["MW (-H2O)"], errors="coerce")
        )

        formatted2 = merged["Obtained Compound Mass (-H2O) [g/L]"].apply(
            lambda x: pd.Series(format_mass_and_unit(x, decimals=decimals))
        )
        merged["Obtained Compound Concentration (-H2O)"] = formatted2[0]
        merged["Unit (-H2O)"] = formatted2[1]

    if "MW" in merged.columns:
        merged["MW [g/mol]"] = pd.to_numeric(merged["MW"], errors="coerce").round(3)
    else:
        merged["MW [g/mol]"] = np.nan

    out_cols = base_cols.copy()
    if include_anhydrous_mass and "Obtained Compound Concentration (-H2O)" in merged.columns:
        out_cols += ["Obtained Compound Concentration (-H2O)", "Unit (-H2O)"]

    out = merged[out_cols].copy()
    out = out.sort_values(by="Obtained Compound Concentration", ascending=False, kind="mergesort").reset_index(drop=True)
    return out


def build_element_validation_table(
    medium_input: MediumOptimizationInput,
    result: MediumOptimizationResult,
    *,
    decimals_mass: int = 2,
    decimals_percent: int = 2,
) -> pd.DataFrame:
    cols = [
        "Element",
        "Reference Elemental Growth Yield [gCDW/g]",
        "Excess Factor",
        "Reference Element Mass",
        "Required Element Mass",
        "Obtained Element Mass",
        "Unit",
        "Match (%)",
    ]

    if not result.success or not getattr(result, "element_matches", None):
        return pd.DataFrame(columns=cols)

    obtained_map = {m.element: float(m.obtained_mass_g_per_l) for m in result.element_matches}
    required_map = {m.element: float(m.required_mass_g_per_l) for m in result.element_matches}
    match_map = {m.element: float(m.match_percent) for m in result.element_matches}

    rows: list[dict[str, Any]] = []

    for element, req in medium_input.required_elements.items():
        y = float(req.reference_yield_g_cdw_per_g)
        ex = float(req.excess_factor)
        if y <= 0 or ex <= 0:
            continue

        reference_mass = float(medium_input.max_dry_biomass_g_per_l) / y
        required_mass = float(required_map.get(element, reference_mass * ex))
        obtained_mass = float(obtained_map.get(element, np.nan))
        match_percent = float(match_map.get(element, 0.0))

        unit = _choose_unit_from_min_mass([reference_mass, required_mass, obtained_mass])
        ref_scaled = _scale_to_unit(reference_mass, unit, decimals=decimals_mass)
        req_scaled = _scale_to_unit(required_mass, unit, decimals=decimals_mass)
        obt_scaled = _scale_to_unit(obtained_mass, unit, decimals=decimals_mass)

        rows.append(
            {
                "Element": str(element),
                "Reference Elemental Growth Yield [gCDW/g]": round(y, decimals_mass),
                "Excess Factor": round(ex, decimals_mass),
                "Reference Element Mass": ref_scaled,
                "Required Element Mass": req_scaled,
                "Obtained Element Mass": obt_scaled,
                "Unit": unit,
                "Match (%)": round(match_percent, decimals_percent),
            }
        )

    df = pd.DataFrame(rows, columns=cols)

    def _back_to_g_per_l(value: float, unit: str) -> float:
        if value is None or not np.isfinite(value):
            return float("nan")
        if unit == "g/L":
            return float(value)
        if unit == "mg/L":
            return float(value) / 1e3
        if unit == "µg/L":
            return float(value) / 1e6
        if unit == "ng/L":
            return float(value) / 1e9
        return float(value)

    if not df.empty:
        df["_required_g_per_l"] = [_back_to_g_per_l(v, u) for v, u in zip(df["Required Element Mass"], df["Unit"])]
        df = (
            df.sort_values(by="_required_g_per_l", ascending=False, kind="mergesort")
            .drop(columns=["_required_g_per_l"])
            .reset_index(drop=True)
        )

    return df


@dataclass(frozen=True, slots=True)
class OptimizationTables:
    compounds: pd.DataFrame
    elements: pd.DataFrame


def build_optimization_tables(
    medium_input: MediumOptimizationInput,
    result: MediumOptimizationResult,
    compound_repository: Any,
    *,
    decimals: int = 2,
    include_anhydrous_mass: bool = False,
) -> OptimizationTables:
    compounds_df = build_compounds_results_table(
        result,
        compound_repository,
        decimals=decimals,
        include_anhydrous_mass=include_anhydrous_mass,
    )
    elements_df = build_element_validation_table(
        medium_input,
        result,
        decimals_mass=decimals,
        decimals_percent=decimals,
    )
    return OptimizationTables(compounds=compounds_df, elements=elements_df)
