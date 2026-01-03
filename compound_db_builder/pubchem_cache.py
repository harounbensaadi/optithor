# compound_db_builder/pubchem_cache.py

from __future__ import annotations

from pathlib import Path

import pandas as pd

from io_json import write_json


def _norm_cid(v: object) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    s = s.replace(".0", "") if s.endswith(".0") else s
    if s.lower() == "none":
        return None
    return s


def _not_empty(v: object) -> bool:
    if v is None:
        return False
    s = str(v).strip()
    return bool(s) and s.lower() != "nan"


def _score_row(row: pd.Series) -> int:
    """
    Higher score = better.
    We prefer:
      - Status ok
      - has CID
      - has Name / Formula / MW / SMILES
    """
    score = 0
    if str(row.get("Status", "")).strip().lower() == "ok":
        score += 10_000

    if _norm_cid(row.get("PubChem CID")):
        score += 2_000

    if _not_empty(row.get("PubChem Name")):
        score += 400
    if _not_empty(row.get("Molecular Formula")):
        score += 400
    if _not_empty(row.get("Molecular Weight")):
        score += 400
    if _not_empty(row.get("SMILES")):
        score += 50

    return score


def load_cache(cache_path: Path) -> tuple[pd.DataFrame, set[str]]:
    """
    Load ALL call outcomes (success + failure).
    Returns (df_cache, attempted_query_lower_set).
    """
    if not cache_path.is_file():
        return pd.DataFrame(), set()

    df = pd.read_json(cache_path)
    if df.empty or "Query Name" not in df.columns:
        return df, set()

    attempted = set(
        df["Query Name"].dropna().astype(str).str.strip().str.lower().tolist()
    )
    return df, attempted


def save_cache(cache_path: Path, df: pd.DataFrame) -> Path:
    """
    Persist cache as JSON with NaN -> None (so JSON uses null).
    """
    records = df.where(pd.notna(df), None).to_dict(orient="records")
    return write_json(cache_path, records)


def merge_cache(df_cached: pd.DataFrame, df_new: pd.DataFrame, cache_path: Path) -> pd.DataFrame:
    """
    Merge cached + new call records, keep BEST record per Query Name.
    """
    if df_cached is None or df_cached.empty:
        df_all = df_new.copy() if df_new is not None else pd.DataFrame()
    elif df_new is None or df_new.empty:
        df_all = df_cached.copy()
    else:
        df_all = pd.concat([df_cached, df_new], ignore_index=True)

    if df_all.empty or "Query Name" not in df_all.columns:
        save_cache(cache_path, df_all if df_all is not None else pd.DataFrame())
        return df_all

    df_all = df_all.copy()
    df_all["Query Name"] = df_all["Query Name"].astype(str).str.strip()
    df_all["_qkey"] = df_all["Query Name"].str.lower()
    df_all["_score"] = df_all.apply(_score_row, axis=1)
    df_all["_idx"] = range(len(df_all))  # stable tie-break

    df_all = df_all.sort_values(by=["_qkey", "_score", "_idx"], ascending=[True, False, False])
    df_all = df_all.drop_duplicates(subset=["_qkey"], keep="first")
    df_all = df_all.drop(columns=["_qkey", "_score", "_idx"]).reset_index(drop=True)

    save_cache(cache_path, df_all)
    return df_all


def successful_only(df_calls: pd.DataFrame) -> pd.DataFrame:
    """
    Filter cache to only successful (Status == ok) rows with a CID.
    Normalize CID to a clean string.
    """
    if df_calls is None or df_calls.empty:
        return pd.DataFrame()

    df = df_calls.copy()

    if "Status" in df.columns:
        df = df[df["Status"].astype(str).str.strip().str.lower().eq("ok")].copy()

    if "PubChem CID" not in df.columns:
        return pd.DataFrame()

    df["PubChem CID"] = df["PubChem CID"].apply(_norm_cid)
    df = df[df["PubChem CID"].notna()].copy()

    return df.reset_index(drop=True)


def best_per_cid(df_ok: pd.DataFrame) -> pd.DataFrame:
    """
    If multiple successful rows share the same CID, keep the most complete one.
    """
    if df_ok is None or df_ok.empty:
        return pd.DataFrame()

    df = df_ok.copy()
    df["_score"] = df.apply(_score_row, axis=1)
    df["_idx"] = range(len(df))

    df = df.sort_values(by=["PubChem CID", "_score", "_idx"], ascending=[True, False, False])
    df = df.drop_duplicates(subset=["PubChem CID"], keep="first")
    df = df.drop(columns=["_score", "_idx"]).reset_index(drop=True)

    return df
