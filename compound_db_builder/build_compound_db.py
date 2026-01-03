# compound_db_builder/build_compound_db.py

from __future__ import annotations

from pathlib import Path

import pandas as pd

from io_json import write_json_list
from pubchem_cache import best_per_cid, load_cache, merge_cache, successful_only
from db_state import filter_names_to_fetch, load_parquet_known
from step_01_extract_seeds import extract_raw_seed_names
from step_02_expand_hydrates import expand_hydrates_from_json
from step_03_fetch_pubchem import PubchemConfig, fetch_pubchem_from_extended_names
from step_04_build_parquet import build_and_save_parquet


def main() -> None:
    root = Path(__file__).resolve().parent
    raw_seeds = root / "raw_seeds"
    tmp = root / "tmp"
    out = root / "output"

    initial_xlsx = raw_seeds / "initial_compounds.xlsx"
    bio_roles_json = raw_seeds / "compounds_with_biological_roles.json"

    tmp_raw_names = tmp / "tmp_01_raw_seed_names.json"
    tmp_extended_names = tmp / "tmp_02_extended_names.json"
    tmp_only_missing = tmp / "tmp_02c_only_missing_names.json"

    # cache of ALL API calls (success + failure)
    cache_calls_json = tmp / "tmp_03_pubchem_calls_cache.json"
    last_run_json = tmp / "tmp_03_pubchem_raw_last_run.json"

    out.mkdir(parents=True, exist_ok=True)
    out_parquet = out / "compound_db.parquet"

    out_parquet_src = root.parent / "src" / "optithor" / "resources" / "compound_db.parquet"
    out_parquet_src.parent.mkdir(parents=True, exist_ok=True)

    # ---- State: parquet + cache
    known_names_lower, known_cids_str = load_parquet_known(out_parquet)
    df_cached, attempted_queries_lower = load_cache(cache_calls_json)

    print(f"[state] parquet names: {len(known_names_lower)} | parquet cids: {len(known_cids_str)}")
    print(f"[state] cached calls: {len(df_cached)} | attempted queries: {len(attempted_queries_lower)}")

    # ---- Step 1: seeds -> tmp json
    raw_names = extract_raw_seed_names(
        initial_xlsx_path=initial_xlsx,
        bio_roles_json_path=bio_roles_json,
        out_json_path=tmp_raw_names,
    )
    print(f"[step 1] raw names: {len(raw_names)} -> {tmp_raw_names}")

    # ---- Step 2: hydrate expansion -> tmp json
    extended_names = expand_hydrates_from_json(
        raw_names_json=tmp_raw_names,
        out_extended_json=tmp_extended_names,
    )
    print(f"[step 2] extended names: {len(extended_names)} -> {tmp_extended_names}")

    # ---- Step 2.5: decide what to fetch (skip parquet + skip cache)
    names_to_fetch = filter_names_to_fetch(
        extended_names,
        known_names_lower=known_names_lower,
        known_cids_str=known_cids_str,
        attempted_queries_lower=attempted_queries_lower,
    )
    print(f"[step 2.5] names to fetch (new): {len(names_to_fetch)}")

    # ---- Step 3: PubChem fetch (ONLY for new names)
    cfg = PubchemConfig(
        max_concurrent_requests=2,
        max_retries=5,
        initial_backoff_seconds=10,
        timeout_seconds=30,
        log_every=25,
        print_every_api_call=True,
    )

    if names_to_fetch:
        tmp.mkdir(parents=True, exist_ok=True)
        write_json_list(tmp_only_missing, names_to_fetch)

        df_new_calls = fetch_pubchem_from_extended_names(
            extended_names_json=tmp_only_missing,
            out_raw_json=last_run_json,
            pubchem_config=cfg,
        )
        print(f"[step 3] call records this run: {len(df_new_calls)} -> {last_run_json}")
    else:
        df_new_calls = pd.DataFrame()
        print("[step 3] nothing to fetch")

    # ---- Step 3.5: merge cache + new calls, store all outcomes (so we never redo them)
    df_all_calls = merge_cache(df_cached, df_new_calls, cache_calls_json)
    print(f"[step 3.5] cached calls updated: {len(df_all_calls)} -> {cache_calls_json}")

    # ---- Step 4: build parquet from successful-only, best-per-cid
    df_ok = successful_only(df_all_calls)
    df_best = best_per_cid(df_ok)

    written = build_and_save_parquet(df_best, out_parquet)
    written_src = build_and_save_parquet(df_best, out_parquet_src)

    print(f"[step 4] done -> {written}")
    print(f"[step 4] copied -> {written_src}")


if __name__ == "__main__":
    main()
