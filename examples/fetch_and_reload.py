# examples/fetch_and_reload.py

# ---------------------------------------------------------------------
# What this example demonstrates
#
# This example focuses ONLY on compound database handling.
#
# It shows:
# 1) Default behavior:
#    - Uses the local cached compound DB
#    - If no cache exists, copies the packaged DB from the wheel
#    - No network access
#
# 2) force_reload=True:
#    - Overwrites the local cache by re-copying the packaged DB
#    - Useful to reset the cache to a clean, shipped state
#    - Still no network access
#
# 3) fetch_missing=True:
#    - Explicitly queries PubChem for missing CIDs (network access)
#    - Optionally writes fetched compounds back into the local cache
#
# IMPORTANT:
# - force_reload controls cache reset from the packaged DB
# - fetch_missing controls PubChem network access
# - PubChem is NEVER contacted unless explicitly requested
# ---------------------------------------------------------------------

from optithor import CompoundDb

def main() -> None:
    # Load compound database (packaged or local cache)
    repo = CompoundDb()

    # One CID present in the shipped DB + one CID to demonstrate fetching
    compound_cids = [
        "5793",  # D-Glucose (present in the DB)
        "3478",  # Example CID (may be missing locally)
    ]

    # -----------------------------------------------------------------
    # Default: use local cache (offline)
    # -----------------------------------------------------------------
    df_local = repo.get_compounds_by_cids(
        compound_cids,
        force_reload=False,
        fetch_missing=False,
    )
    print("\n=== Local DB (offline) ===")
    print(df_local.to_string(index=False) if not df_local.empty else "(empty)")

    # -----------------------------------------------------------------
    # Reset cache from packaged DB (offline)
    # -----------------------------------------------------------------
    # This overwrites the local cache using the DB shipped in the wheel.
    _ = repo.load(force_reload=True)

    df_after_reload = repo.get_compounds_by_cids(
        compound_cids,
        force_reload=False,
        fetch_missing=False,
    )
    print("\n=== After force_reload (offline) ===")
    print(df_after_reload.to_string(index=False) if not df_after_reload.empty else "(empty)")

    # -----------------------------------------------------------------
    # Fetch missing compounds from PubChem (network)
    # -----------------------------------------------------------------
    df_after_fetch = repo.get_compounds_by_cids(
        compound_cids,
        force_reload=False,
        fetch_missing=True,
        update_cache=True,
    )
    print("\n=== After PubChem fetch (network) ===")
    print(df_after_fetch.to_string(index=False) if not df_after_fetch.empty else "(empty)")


if __name__ == "__main__":
    main()
