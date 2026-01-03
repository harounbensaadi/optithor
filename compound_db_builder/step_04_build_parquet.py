# compound_db_builder/step_04_build_parquet.py

from __future__ import annotations

from pathlib import Path
import re

import pandas as pd


def molar_mass_h2o() -> float:
    return 18.01528


def split_hydrate_formula(formula: str) -> tuple[str, int]:
    """
    'CaCl2 • 2 H2O' -> ('CaCl2', 2)
    'Na2HPO4 • H2O' -> ('Na2HPO4', 1)
    'C6H12O6'       -> ('C6H12O6', 0)
    """
    if not formula or not isinstance(formula, str):
        return "", 0

    s = formula.replace("·", "•")
    if "•" not in s:
        return s.strip(), 0

    left, right = [p.strip() for p in s.split("•", 1)]
    m = re.search(r"^\s*(\d+)\s*H2O\s*$", right, flags=re.IGNORECASE)
    if m:
        return left, int(m.group(1))
    if re.fullmatch(r"H2O", right, flags=re.IGNORECASE):
        return left, 1
    return left, 0


def _score_best_per_cid_row(row: pd.Series) -> int:
    """
    Pick the best row per CID.
    Prefer:
      - Status ok
      - having PubChem Name, Formula, MW, SMILES
    """
    score = 0

    if str(row.get("Status", "")).strip().lower() == "ok":
        score += 10_000

    name = row.get("PubChem Name")
    if pd.notna(name) and str(name).strip():
        score += 500

    formula = row.get("Molecular Formula") if "Molecular Formula" in row else row.get("Formula")
    if pd.notna(formula) and str(formula).strip():
        score += 500

    mw = row.get("Molecular Weight") if "Molecular Weight" in row else row.get("MW")
    if pd.notna(mw):
        score += 500

    smiles = row.get("SMILES")
    if pd.notna(smiles) and str(smiles).strip():
        score += 100

    return score


def build_compound_db(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Final DB schema:
      - PubChem CID
      - PubChem Name
      - Formula
      - Formula (-H2O)
      - MW
      - MW (-H2O)
    """
    cols = ["PubChem CID", "PubChem Name", "Formula", "Formula (-H2O)", "MW", "MW (-H2O)"]
    if df_raw is None or df_raw.empty:
        return pd.DataFrame(columns=cols)

    df = df_raw.copy()

    # If Status exists, only build parquet from successful entries.
    # (Failures remain cached in JSON, but do NOT enter the DB.)
    if "Status" in df.columns:
        df = df[df["Status"].astype(str).str.strip().str.lower().eq("ok")].copy()

    # Must have CID
    if "PubChem CID" not in df.columns:
        return pd.DataFrame(columns=cols)

    df = df[df["PubChem CID"].notna()].copy()

    # Normalize CID to clean string (no trailing .0)
    df["PubChem CID"] = (
        df["PubChem CID"]
        .astype(str)
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
    )

    df = df[df["PubChem CID"].str.lower().ne("none") & (df["PubChem CID"] != "")].copy()

    # Pick the best row per CID (most complete)
    df["_score"] = df.apply(_score_best_per_cid_row, axis=1)
    df["_idx"] = range(len(df))
    df = df.sort_values(by=["PubChem CID", "_score", "_idx"], ascending=[True, False, False])
    df = df.drop_duplicates(subset="PubChem CID", keep="first").drop(columns=["_score", "_idx"]).reset_index(drop=True)

    # Build Formula/MW from raw fields
    if "Formula" not in df.columns:
        df["Formula"] = df.get("Molecular Formula")

    df["MW"] = pd.to_numeric(df.get("Molecular Weight"), errors="coerce")

    h2o = molar_mass_h2o()

    def compute_minus_h2o(row):
        formula = row.get("Formula")
        mw = row.get("MW")
        if not isinstance(formula, str) or not formula.strip():
            return None, None
        base, n = split_hydrate_formula(formula)
        if mw is None or (isinstance(mw, float) and pd.isna(mw)):
            return base, None
        return base, float(mw) - float(n) * float(h2o)

    out = df.copy()
    computed = out.apply(compute_minus_h2o, axis=1, result_type="expand")
    out["Formula (-H2O)"] = computed[0]
    out["MW (-H2O)"] = pd.to_numeric(computed[1], errors="coerce")

    final = out[cols].copy()
    return final


def save_parquet(df: pd.DataFrame, out_path: str | Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        df.to_parquet(out_path, index=False, engine="pyarrow")
    except Exception as e_pyarrow:
        try:
            df.to_parquet(out_path, index=False, engine="fastparquet")
        except Exception as e_fastparquet:
            raise RuntimeError(
                "Failed to write parquet. Install/upgrade a parquet engine:\n"
                "  pip install -U 'pyarrow>=16'\n"
                "or\n"
                "  pip install -U fastparquet\n"
                f"\npyarrow error: {e_pyarrow}\nfastparquet error: {e_fastparquet}"
            ) from e_fastparquet

    print(f"saved parquet: {out_path}  rows={len(df)}")
    return out_path


def build_and_save_parquet(df_raw: pd.DataFrame, out_parquet: str | Path) -> Path:
    df_db = build_compound_db(df_raw)
    return save_parquet(df_db, out_parquet)
