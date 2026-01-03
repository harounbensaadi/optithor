# src/optithor/pubchem_client.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import aiohttp


@dataclass(slots=True, frozen=True)
class PubchemClientConfig:
    timeout_seconds: int = 20


@dataclass(slots=True)
class PubChemClient:
    """
    Keeps optithor "offline-first" unless explicitly enabled by flags.
    """

    config: PubchemClientConfig = PubchemClientConfig()

    async def fetch_by_cid(self, cid: str) -> dict[str, Any] | None:
        cid = str(cid).strip().removesuffix(".0")
        if not cid:
            return None

        props = "MolecularFormula,MolecularWeight,Title"
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{quote(cid)}/property/{props}/JSON"

        timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()

        props_list = data.get("PropertyTable", {}).get("Properties", [])
        if not props_list:
            return None

        p0 = props_list[0]
        # CID might come back as int/float; keep as string
        return {
            "PubChem CID": str(p0.get("CID", cid)).strip().removesuffix(".0"),
            "PubChem Name": p0.get("Title"),
            "Formula": p0.get("MolecularFormula"),
            "MW": p0.get("MolecularWeight"),
        }
