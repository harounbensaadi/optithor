# src/optithor/compound_db.py

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd
import asyncio

from .errors import DataError
from .paths import default_db_path, empty_db_df, ensure_db_in_cache, ensure_db_schema
from .pubchem_client import PubChemClient

REQUIRED_COLUMNS = {
    "PubChem CID",
    "PubChem Name",
    "Formula",
    "Formula (-H2O)",
    "MW",
    "MW (-H2O)",
}


def _normalize_cid(value: object) -> str:
    """
    Normalize any CID-like value to a canonical string form.

    Examples:
      61482        -> "61482"
      61482.0      -> "61482"
      " 61482.0 "  -> "61482"
      "" / None    -> ""
    """
    s = str(value).strip()
    if not s or s.lower() in {"none", "nan"}:
        return ""
    return s.removesuffix(".0")


def _completeness_score(row: pd.Series) -> int:
    """
    Higher score = more complete record.
    """
    fields = ["PubChem Name", "Formula", "Formula (-H2O)", "MW", "MW (-H2O)"]
    score = 0
    for f in fields:
        v = row.get(f, None)
        if v is None:
            continue
        if isinstance(v, float) and pd.isna(v):
            continue
        if isinstance(v, str) and not v.strip():
            continue
        score += 1
    return score


def _dedupe_keep_most_complete(df: pd.DataFrame) -> pd.DataFrame:
    """
    For duplicated PubChem CID, keep the most complete row.
    """
    if df.empty:
        return df

    df = df.copy()
    df["_score"] = df.apply(_completeness_score, axis=1)

    # Keep highest score per CID; stable for ties
    df = (
        df.sort_values(["PubChem CID", "_score"], ascending=[True, False], kind="mergesort")
        .drop_duplicates(subset=["PubChem CID"], keep="first")
        .drop(columns=["_score"])
    )

    return df

def _in_running_event_loop() -> bool:
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False

def _debug(msg: str) -> None:
    print(f"[CompoundDb] {msg}")
    
@dataclass(slots=True)
class CompoundDb:
    """
    Lightweight manager for the compound database (Parquet).

    - Reads from a user-writable cache path by default.
    - If the DB is missing in cache, attempts to copy the packaged DB into cache.
    - If force_reload=True, overwrites cache from packaged DB.
    - Optionally can fetch missing CIDs from PubChem (off by default).
    """

    path: str | Path | None = None
    pubchem: PubChemClient | None = None

    def get_path(self) -> Path:
        return Path(self.path) if self.path else default_db_path()

    @staticmethod
    def normalize(df: pd.DataFrame) -> pd.DataFrame:
        """Normalize common fields to reduce subtle mismatches."""
        if df.empty:
            return df

        if "PubChem CID" in df.columns:
            df["PubChem CID"] = (
                df["PubChem CID"]
                .astype(str)
                .str.strip()
                .str.replace(r"\.0$", "", regex=True)
            )

        for col in ("PubChem Name", "Formula", "Formula (-H2O)"):
            if col in df.columns:
                df[col] = df[col].astype(str)

        for col in ("MW", "MW (-H2O)"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df

    @staticmethod
    def validate_schema(df: pd.DataFrame) -> None:
        missing = REQUIRED_COLUMNS - set(df.columns)
        if missing:
            raise DataError(f"DB missing required columns: {sorted(missing)}")

    def load(self, *, force_reload: bool = False) -> pd.DataFrame:
        """
        Load DB (prefer cache). If force_reload=True, re-copy from packaged DB into cache.
        """
        p = self.get_path()
        ensure_db_in_cache(p, force_reload=force_reload)

        try:
            df = pd.read_parquet(p)
        except FileNotFoundError as e:
            raise DataError(
                f"Compound DB not found at: {p}. "
                f"Expected either a cached DB or a packaged DB to be available."
            ) from e
        except Exception as e:
            raise DataError(f"Failed to read parquet DB at: {p}") from e

        self.validate_schema(df)
        return self.normalize(df)

    def _write_cache(self, df: pd.DataFrame) -> None:
        """
        Write updated DB into the cache path.
        """
        p = self.get_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(p, index=False)

    async def _fetch_missing_rows_async(self, missing_cids: list[str]) -> pd.DataFrame:
        if not missing_cids:
            return pd.DataFrame(columns=list(REQUIRED_COLUMNS))

        _debug(f"Fetching {len(missing_cids)} missing CIDs from PubChem: {missing_cids}")

        client = self.pubchem or PubChemClient()
        records: list[dict[str, object]] = []

        for cid in missing_cids:
            _debug(f" Fetching CID {cid} from PubChem")
            rec = await client.fetch_by_cid(cid)

            if not rec:
                _debug(f" CID {cid}: no data returned")
                continue

            cid_norm = _normalize_cid(rec.get("PubChem CID", cid))
            _debug(f" CID {cid_norm}: fetched successfully")

            records.append(
                {
                    "PubChem CID": cid_norm,
                    "PubChem Name": rec.get("PubChem Name") or "",
                    "Formula": rec.get("Formula") or "",
                    "Formula (-H2O)": rec.get("Formula") or "",
                    "MW": rec.get("MW"),
                    "MW (-H2O)": rec.get("MW"),
                }
            )

        df_new = pd.DataFrame.from_records(records)
        if df_new.empty:
            _debug("No new compounds fetched from PubChem.")
            return df_new

        df_new = self.normalize(df_new)
        df_new = ensure_db_schema(df_new)

        _debug(f"Fetched {len(df_new)} new compounds from PubChem.")
        return df_new


    async def get_compounds_by_cids_async(
        self,
        cids: Iterable[str | int],
        *,
        force_reload: bool = False,
        fetch_missing: bool = False,
        update_cache: bool = True,
    ) -> pd.DataFrame:
        wanted = [_normalize_cid(x) for x in cids]
        wanted = [w for w in wanted if w]
        if not wanted:
            return empty_db_df()

        df = self.load(force_reload=force_reload)
        if df.empty:
            return empty_db_df()

        wanted_set = set(wanted)
        hit = df[df["PubChem CID"].isin(wanted_set)].copy()

        if fetch_missing:
            found_set = set(hit["PubChem CID"].astype(str)) if not hit.empty else set()
            missing = [cid for cid in wanted if cid not in found_set]

            if missing:
                _debug(f"Missing CIDs in DB: {missing}")
                
                df_new = await self._fetch_missing_rows_async(missing)
                if not df_new.empty:
                    df_all = pd.concat([df, df_new], ignore_index=True)
                    df_all = self.normalize(df_all)
                    df_all = ensure_db_schema(df_all)
                    df_all = _dedupe_keep_most_complete(df_all)

                        
                    if update_cache:
                        _debug("Updating local compound DB cache with fetched compounds.")
                        self._write_cache(df_all)
                        _debug("Local compound DB cache updated.")

                    df = df_all
                    hit = df[df["PubChem CID"].isin(wanted_set)].copy()
            else:
                _debug("No missing CIDs; PubChem fetch not needed.")
        
        if hit.empty:
            return empty_db_df()

        order = pd.Categorical(hit["PubChem CID"], categories=wanted, ordered=True)
        hit = hit.assign(_order=order).sort_values("_order").drop(columns=["_order"])
        return hit.reset_index(drop=True)

    def get_compounds_by_cids(
        self,
        cids: Iterable[str | int],
        *,
        force_reload: bool = False,
        fetch_missing: bool = False,
        update_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Sync wrapper.

        IMPORTANT: If you're in a notebook (running event loop) and set fetch_missing=True,
        call `await repo.get_compounds_by_cids_async(...)` instead.
        """
        if fetch_missing and _in_running_event_loop():
            raise RuntimeError(
                "fetch_missing=True cannot run in a running event loop (e.g. Jupyter). "
                "Use: `await repo.get_compounds_by_cids_async(..., fetch_missing=True)`"
            )

        if fetch_missing:
            return asyncio.run(
                self.get_compounds_by_cids_async(
                    cids,
                    force_reload=force_reload,
                    fetch_missing=fetch_missing,
                    update_cache=update_cache,
                )
            )

        # No network path: pure sync
        wanted = [_normalize_cid(x) for x in cids]
        wanted = [w for w in wanted if w]
        if not wanted:
            return empty_db_df()

        df = self.load(force_reload=force_reload)
        if df.empty:
            return empty_db_df()

        wanted_set = set(wanted)
        hit = df[df["PubChem CID"].isin(wanted_set)].copy()
        if hit.empty:
            return empty_db_df()

        order = pd.Categorical(hit["PubChem CID"], categories=wanted, ordered=True)
        hit = hit.assign(_order=order).sort_values("_order").drop(columns=["_order"])
        return hit.reset_index(drop=True)
    