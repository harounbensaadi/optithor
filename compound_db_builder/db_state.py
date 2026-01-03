# compound_db_builder/db_state.py

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd


def _norm(s: object) -> str:
    return str(s).strip().lower()


def load_parquet_known(
    parquet_path: Path,
) -> tuple[set[str], set[str]]:
    """
    Return (known_names_lower, known_cids_str).

    - known_names_lower from "PubChem Name"
    - known_cids_str from "PubChem CID" (normalized string, no trailing .0)
    """
    if not parquet_path.is_file():
        return set(), set()

    df = pd.read_parquet(parquet_path)
    known_names: set[str] = set()
    known_cids: set[str] = set()

    if "PubChem Name" in df.columns:
        known_names = {
            _norm(x) for x in df["PubChem Name"].dropna().astype(str).tolist() if _norm(x)
        }

    if "PubChem CID" in df.columns:
        cids = (
            df["PubChem CID"]
            .dropna()
            .astype(str)
            .str.strip()
            .str.replace(r"\.0$", "", regex=True)
            .tolist()
        )
        known_cids = {c for c in cids if c and c.lower() != "none"}

    return known_names, known_cids


def filter_names_to_fetch(
    names: Iterable[str],
    *,
    known_names_lower: set[str],
    known_cids_str: set[str],
    attempted_queries_lower: set[str],
) -> list[str]:
    """
    Keep only names that:
      - are not empty
      - are not already attempted (cache)
      - are not already present in parquet by name
      - if name looks like a CID, also skip if CID already present in parquet
    """
    out: list[str] = []
    seen: set[str] = set()

    for n in names:
        s = str(n).strip()
        if not s:
            continue

        key = s.lower()
        if key in seen:
            continue
        seen.add(key)

        # skip anything already attempted (success OR fail)
        if key in attempted_queries_lower:
            continue

        # if it's a numeric CID query, skip if parquet already has it
        if s.isdigit() and s in known_cids_str:
            continue

        # skip if name is already present in parquet
        if key in known_names_lower:
            continue

        out.append(s)

    return out
