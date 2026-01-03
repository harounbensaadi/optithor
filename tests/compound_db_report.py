# tests/compound_db_report.py
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import math
from dataclasses import dataclass
from typing import Any

import pandas as pd
import pytest

from optithor.compound_db import CompoundDb
from optithor.utils import molar_mass_h2o, split_hydrate_formula


pytestmark = pytest.mark.dbcheck

EXPECTED_COLUMNS = [
    "PubChem CID",
    "PubChem Name",
    "Formula",
    "Formula (-H2O)",
    "MW",
    "MW (-H2O)",
]

# Hydrate marker used in the DB ("base • n H2O")
# Be tolerant to both bullet variants: • and ·
HYDRATE_REGEX = r"[•·]\s*(\d+\s*)?H2O\b"

@dataclass
class CheckResult:
    name: str
    ok: bool
    details: str = ""
    extras: dict[str, Any] | None = None


def _fmt_bool(x: bool) -> str:
    return "PASS" if x else "FAIL"


def _safe_str(x: Any) -> str:
    try:
        return str(x)
    except Exception:
        return repr(x)


def _coerce_numeric(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    # These should exist in the DB schema; convert defensively
    if "PubChem CID" in out.columns:
        out["PubChem CID"] = (
            out["PubChem CID"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
        )

    for col in ("MW", "MW (-H2O)"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    for col in ("Formula", "Formula (-H2O)"):
        if col in out.columns:
            out[col] = out[col].astype(str)

    return out


def _load_db(*, force_reload: bool = False) -> pd.DataFrame:
    repo = CompoundDb()
    return repo.load(force_reload=force_reload)


def validate_compound_db(df: pd.DataFrame) -> tuple[list[CheckResult], dict[str, Any]]:
    df = _coerce_numeric(df)
    results: list[CheckResult] = []
    summary: dict[str, Any] = {}

    # --- Schema
    cols = list(df.columns)
    missing = [c for c in EXPECTED_COLUMNS if c not in cols]
    extra = [c for c in cols if c not in EXPECTED_COLUMNS]
    results.append(
        CheckResult(
            "Schema: required columns present",
            ok=(len(missing) == 0),
            details=(
                ("Missing columns: %s. " % missing if missing else "")
                + ("Extra columns: %s." % extra if extra else "")
            ),
        )
    )
    summary["columns"] = cols
    summary["rows_total"] = int(len(df))

    if missing:
        return results, summary

    # --- Non-empty
    results.append(CheckResult("Rows: non-empty", ok=len(df) > 0, details=f"rows={len(df)}"))

    # --- CID uniqueness
    n_unique = df["PubChem CID"].nunique(dropna=False)
    ok_unique = (n_unique == len(df))
    dupes = df.loc[df["PubChem CID"].duplicated(keep=False), "PubChem CID"].unique().tolist()
    results.append(
        CheckResult(
            "CIDs: unique per row",
            ok=ok_unique,
            details=f"unique={n_unique} rows={len(df)}" + (f" duplicated={dupes[:10]}..." if dupes else ""),
        )
    )
    summary["cids_unique"] = int(n_unique)
    summary["cids_duplicated_count"] = int(len(dupes))

    # --- NaNs in critical columns
    critical = ["Formula", "MW", "Formula (-H2O)", "MW (-H2O)"]
    nan_counts = {c: int(df[c].isna().sum()) for c in critical}
    summary["nan_counts"] = nan_counts

    results.append(CheckResult("NaNs: Formula has no missing values", ok=(nan_counts["Formula"] == 0), details=f"NaNs={nan_counts['Formula']}"))
    results.append(CheckResult("NaNs: MW has no missing values", ok=(nan_counts["MW"] == 0), details=f"NaNs={nan_counts['MW']}"))
    results.append(CheckResult("NaNs: Formula (-H2O) has no missing values", ok=(nan_counts["Formula (-H2O)"] == 0), details=f"NaNs={nan_counts['Formula (-H2O)']}"))
    results.append(CheckResult("NaNs: MW (-H2O) has no missing values", ok=(nan_counts["MW (-H2O)"] == 0), details=f"NaNs={nan_counts['MW (-H2O)']}"))

    # --- Hydrate/anhydrous split
    is_hydrate = df["Formula"].astype(str).str.contains(HYDRATE_REGEX, regex=True, na=False)
    df_h = df[is_hydrate].copy()
    df_a = df[~is_hydrate].copy()

    summary["rows_hydrate"] = int(len(df_h))
    summary["rows_anhydrous"] = int(len(df_a))
    results.append(CheckResult("Hydrates: count detected", ok=True, details=f"hydrate_rows={len(df_h)} anhydrous_rows={len(df_a)}"))

    # --- Anhydrous: MW == MW(-H2O)
    tol = 1e-6
    if len(df_a) > 0:
        delta_a = (df_a["MW"] - df_a["MW (-H2O)"]).abs()
        max_delta_a = float(delta_a.max())
        ok_a = bool(max_delta_a <= tol or math.isclose(max_delta_a, 0.0, abs_tol=tol))
        results.append(CheckResult("Anhydrous: MW equals MW(-H2O)", ok=ok_a, details=f"max_abs_delta={max_delta_a}"))
        summary["anhydrous_max_abs_delta_mw"] = max_delta_a
    else:
        results.append(CheckResult("Anhydrous: MW equals MW(-H2O)", ok=True, details="no anhydrous rows"))

    # --- Hydrates: Formula(-H2O) matches parsed base + MW >= MW(-H2O)
    if len(df_h) > 0:
        bad_formula: list[dict[str, Any]] = []
        bad_mw: list[dict[str, Any]] = []

        for _, r in df_h.iterrows():
            f = _safe_str(r["Formula"])
            f_minus = _safe_str(r["Formula (-H2O)"])
            base, water_count = split_hydrate_formula(f)

            mw = r["MW"]
            mw_minus = r["MW (-H2O)"]

            if water_count <= 0:
                bad_formula.append(
                    {
                        "CID": r["PubChem CID"],
                        "Name": r.get("PubChem Name"),
                        "Formula": f,
                        "issue": "hydrate marker detected but water_count parsed as 0",
                    }
                )
                continue

            if f_minus.strip() != base.strip():
                bad_formula.append(
                    {
                        "CID": r["PubChem CID"],
                        "Name": r.get("PubChem Name"),
                        "Formula": f,
                        "Formula(-H2O)": f_minus,
                        "expected_base": base,
                        "water_count": water_count,
                    }
                )

            if pd.notna(mw) and pd.notna(mw_minus) and float(mw) + tol < float(mw_minus):
                bad_mw.append(
                    {
                        "CID": r["PubChem CID"],
                        "Name": r.get("PubChem Name"),
                        "Formula": f,
                        "MW": float(mw),
                        "MW(-H2O)": float(mw_minus),
                    }
                )

        results.append(
            CheckResult(
                "Hydrates: Formula(-H2O) matches base formula",
                ok=(len(bad_formula) == 0),
                details=f"bad_rows={len(bad_formula)}",
                extras={"examples": bad_formula[:5]} if bad_formula else None,
            )
        )
        results.append(
            CheckResult(
                "Hydrates: MW >= MW(-H2O)",
                ok=(len(bad_mw) == 0),
                details=f"bad_rows={len(bad_mw)}",
                extras={"examples": bad_mw[:5]} if bad_mw else None,
            )
        )

        summary["hydrate_bad_formula_count"] = int(len(bad_formula))
        summary["hydrate_bad_mw_count"] = int(len(bad_mw))
    else:
        results.append(CheckResult("Hydrates: Formula(-H2O) matches base formula", ok=True, details="no hydrate rows"))
        results.append(CheckResult("Hydrates: MW >= MW(-H2O)", ok=True, details="no hydrate rows"))

    # --- Hydrates: delta ~= n*MW(H2O)
    h2o = float(molar_mass_h2o())
    if len(df_h) > 0:
        bad_delta: list[dict[str, Any]] = []
        for _, r in df_h.iterrows():
            f = _safe_str(r["Formula"])
            _, water_count = split_hydrate_formula(f)
            mw = r["MW"]
            mw_minus = r["MW (-H2O)"]

            if water_count <= 0 or pd.isna(mw) or pd.isna(mw_minus):
                continue

            expected = water_count * h2o
            observed = float(mw) - float(mw_minus)

            if not math.isclose(observed, expected, rel_tol=5e-3, abs_tol=0.05):
                bad_delta.append(
                    {
                        "CID": r["PubChem CID"],
                        "Name": r.get("PubChem Name"),
                        "Formula": f,
                        "water_count": water_count,
                        "observed_delta": observed,
                        "expected_delta": expected,
                    }
                )

        results.append(
            CheckResult(
                "Hydrates: MW - MW(-H2O) ~= n*MW(H2O)",
                ok=(len(bad_delta) == 0),
                details=f"bad_rows={len(bad_delta)}",
                extras={"examples": bad_delta[:5]} if bad_delta else None,
            )
        )
        summary["hydrate_bad_delta_count"] = int(len(bad_delta))
    else:
        results.append(CheckResult("Hydrates: MW - MW(-H2O) ~= n*MW(H2O)", ok=True, details="no hydrate rows"))

    return results, summary


def print_db_report(results: list[CheckResult], summary: dict[str, Any]) -> None:
    print("\n" + "=" * 72)
    print("OptiThor compound_db validation report")
    print("=" * 72)
    print(f"Total rows: {summary.get('rows_total')}")
    print(f"Hydrate rows: {summary.get('rows_hydrate')} | Anhydrous rows: {summary.get('rows_anhydrous')}")
    print(f"Unique CIDs: {summary.get('cids_unique')} | Duplicated CIDs: {summary.get('cids_duplicated_count')}")
    print(f"NaNs: {summary.get('nan_counts')}")
    if "anhydrous_max_abs_delta_mw" in summary:
        print(f"Anhydrous max |MW - MW(-H2O)|: {summary.get('anhydrous_max_abs_delta_mw')}")

    print("\nChecks:")
    for r in results:
        line = f"  [{_fmt_bool(r.ok)}] {r.name}"
        if r.details:
            line += f" - {r.details}"
        print(line)
        if (not r.ok) and r.extras and r.extras.get("examples"):
            print("        examples:")
            for item in r.extras["examples"]:
                print(f"          - {item}")

    ok_all = all(r.ok for r in results)
    print("\nOverall:", "PASS" if ok_all else "FAIL")
    print("=" * 72 + "\n")


def test_compound_db_report() -> None:
    """
    This is a DB integrity check (not a unit test).
    Run explicitly:
      pytest -q -s -m dbcheck
    """
    df = _load_db(force_reload=False)
    results, summary = validate_compound_db(df)
    print_db_report(results, summary)

    failed = [r for r in results if not r.ok]
    assert not failed, "Compound DB validation failed. See printed report above."


if __name__ == "__main__":
    test_compound_db_report()
