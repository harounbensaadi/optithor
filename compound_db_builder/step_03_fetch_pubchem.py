# compound_db_builder/step_03_fetch_pubchem.py

from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import aiohttp
import asyncio
import pandas as pd

from io_json import read_json_list, write_json


@dataclass(frozen=True)
class PubchemConfig:
    max_concurrent_requests: int = 2
    max_retries: int = 8
    initial_backoff_seconds: int = 10
    timeout_seconds: int = 30
    log_every: int = 25
    print_every_api_call: bool = False


async def _get_json_with_retries(
    session: aiohttp.ClientSession,
    url: str,
    config: PubchemConfig,
) -> dict[str, Any] | None:
    backoff = config.initial_backoff_seconds

    for _ in range(config.max_retries):
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    if config.print_every_api_call:
                        print(f"[pubchem] {response.status} {url}")
                    return await response.json()

                if response.status in (429, 503):
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 300)
                    continue

                return None

        except (aiohttp.ClientError, asyncio.TimeoutError):
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 300)

    return None


async def _fetch_record_for_name(
    session: aiohttp.ClientSession,
    compound_name: str,
    config: PubchemConfig,
) -> dict[str, Any]:
    """
    IMPORTANT:
    - Always returns a record for every input name (success or failure).
    - This lets us cache failed attempts and avoid repeating them next time.
    """
    compound_name = str(compound_name).strip()
    if not compound_name:
        return {"Query Name": "", "Status": "skipped-empty"}

    base_url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{quote(compound_name)}"

    # Resolve CID
    cids_url = f"{base_url}/cids/JSON"
    cids_json = await _get_json_with_retries(session, cids_url, config)
    cid = None
    if cids_json:
        cid_list = cids_json.get("IdentifierList", {}).get("CID", [])
        cid = str(cid_list[0]) if cid_list else None

    # Fetch properties
    props_url = f"{base_url}/property/MolecularFormula,MolecularWeight,CanonicalSMILES,Title/JSON"
    props_json = await _get_json_with_retries(session, props_url, config)
    if not props_json:
        return {
            "Query Name": compound_name,
            "Status": "failed-no-props",
            "PubChem CID": cid,
        }

    props_list = props_json.get("PropertyTable", {}).get("Properties", [])
    if not props_list:
        return {
            "Query Name": compound_name,
            "Status": "failed-empty-props",
            "PubChem CID": cid,
        }

    props = props_list[0]
    name = props.get("Title")

    return {
        "Query Name": compound_name,
        "Status": "ok",
        "PubChem CID": cid or props.get("CID"),
        "PubChem Name": name,
        "Molecular Formula": props.get("MolecularFormula"),
        "Molecular Weight": props.get("MolecularWeight"),
        "SMILES": props.get("CanonicalSMILES"),
    }


async def fetch_pubchem_raw_async(names: list[str], config: PubchemConfig) -> pd.DataFrame:
    sem = asyncio.Semaphore(config.max_concurrent_requests)
    timeout = aiohttp.ClientTimeout(total=config.timeout_seconds)

    results: list[dict[str, Any]] = []
    total = len(names)
    done = 0

    async with aiohttp.ClientSession(timeout=timeout) as session:

        async def runner(n: str):
            nonlocal done
            async with sem:
                rec = await _fetch_record_for_name(session, n, config)
                done += 1
                if done % config.log_every == 0 or done == total:
                    print(f"processed {done}/{total}")
                return rec

        tasks = [runner(n) for n in names]
        for fut in asyncio.as_completed(tasks):
            rec = await fut
            # ALWAYS append, even if failed
            results.append(rec)

    return pd.DataFrame(results)


def fetch_pubchem_from_extended_names(
    *,
    extended_names_json: str | Path,
    out_raw_json: str | Path,
    pubchem_config: PubchemConfig | None = None,
) -> pd.DataFrame:
    names = read_json_list(extended_names_json)
    cfg = pubchem_config or PubchemConfig()

    df = asyncio.run(fetch_pubchem_raw_async(names, cfg))

    # Save ALL call outcomes (success + failure)
    write_json(out_raw_json, df.to_dict(orient="records"))
    return df
