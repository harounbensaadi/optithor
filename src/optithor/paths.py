# src/optithor/paths.py

from __future__ import annotations

import os
import shutil
from importlib import resources
from pathlib import Path

import pandas as pd

from .utils import molar_mass_h2o, split_hydrate_formula


def default_data_dir() -> Path:
    """
    User-writable cache directory.

    Windows: %LOCALAPPDATA%/optithor
    Linux/macOS: ~/.cache/optithor (or XDG_CACHE_HOME/optithor)
    """
    app_name = "optithor"

    if os.name == "nt":
        base = os.getenv("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / app_name

    return Path(os.getenv("XDG_CACHE_HOME", Path.home() / ".cache")) / app_name


def default_db_path() -> Path:
    """Runtime DB path in user cache."""
    return default_data_dir() / "compound_db.parquet"


def packaged_db_path() -> Path:
    """
    Path to the packaged DB inside the installed wheel/sdist.

    Always returns a Path (even if missing), so callers don't crash on None.
    """
    pkg = "optithor"
    root = resources.files(pkg)
    return root.joinpath("resources", "compound_db.parquet")


def ensure_db_in_cache(
    target_path: Path | None = None,
    *,
    force_reload: bool = False,
) -> Path:
    """
    Ensure the DB exists at the cache location.

    If force_reload=True, overwrite cache from packaged DB.
    """
    target = Path(target_path) if target_path else default_db_path()

    if target.is_file() and not force_reload:
        return target

    src = packaged_db_path()
    if not src.is_file():
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, target)
    return target


def empty_db_df() -> pd.DataFrame:
    """Empty DB dataframe with the expected columns."""
    cols = [
        "PubChem CID",
        "PubChem Name",
        "Formula",
        "Formula (-H2O)",
        "MW",
        "MW (-H2O)",
    ]
    return pd.DataFrame(columns=cols)


def ensure_db_schema(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure hydrate-related columns exist and are consistent.

    Conservative rules:
    - If Formula (-H2O) is missing/empty, derive it from Formula (hydrate split).
    - If MW (-H2O) is missing/NaN, estimate it from MW and hydrate water count.
    """
    if df.empty:
        return df

    out = df.copy()

    # Coerce core fields (robust to user-provided DBs)
    if "Formula" in out.columns:
        out["Formula"] = out["Formula"].astype(str)
    if "Formula (-H2O)" in out.columns:
        out["Formula (-H2O)"] = out["Formula (-H2O)"].astype(str)

    if "MW" in out.columns:
        out["MW"] = pd.to_numeric(out["MW"], errors="coerce")
    else:
        out["MW"] = pd.NA

    if "MW (-H2O)" in out.columns:
        out["MW (-H2O)"] = pd.to_numeric(out["MW (-H2O)"], errors="coerce")
    else:
        out["MW (-H2O)"] = pd.NA

    # Ensure Formula (-H2O)
    if "Formula (-H2O)" not in out.columns:
        out["Formula (-H2O)"] = ""

    needs_formula = "Formula" in out.columns and (
        out["Formula (-H2O)"].isna() | (out["Formula (-H2O)"].astype(str).str.strip() == "")
    )
    needs_mw = out["MW (-H2O)"].isna()

    needs_any = needs_formula | needs_mw

    if "Formula" in out.columns and needs_any.any():
        bases = []
        waters = []
        for f in out.loc[needs_any, "Formula"].astype(str).tolist():
            base, water = split_hydrate_formula(f)
            bases.append(base)
            waters.append(water)

        out.loc[needs_any, "_water_count"] = waters

        if needs_formula.any():
            out.loc[needs_formula, "Formula (-H2O)"] = [
                b for b, need in zip(bases, needs_any.loc[needs_any].tolist()) if need
            ][: needs_formula.sum()]
    else:
        out["_water_count"] = 0

    # Ensure MW (-H2O)
    if needs_mw.any():
        h2o = molar_mass_h2o()
        out.loc[needs_mw, "MW (-H2O)"] = (
            out.loc[needs_mw, "MW"] - out.loc[needs_mw, "_water_count"].fillna(0).astype(float) * h2o
        )

    if "_water_count" in out.columns:
        out = out.drop(columns=["_water_count"])

    return out
