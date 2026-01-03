# compound_db_builder/step_01_extract_seeds.py

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

from io_json import dedupe_preserve_order, write_json_list


def seed_list_from_initial_xlsx(xlsx_path: str | Path, name_column: str = "Name") -> list[str]:
    xlsx_path = Path(xlsx_path)
    if not xlsx_path.exists():
        raise FileNotFoundError(f"Excel seed file not found: {xlsx_path}")

    df = pd.read_excel(xlsx_path)
    if name_column not in df.columns:
        raise ValueError(f"Expected column '{name_column}', found: {list(df.columns)}")

    names = df[name_column].dropna().astype(str).map(str.strip).tolist()
    return [n for n in names if n]


def seed_list_from_bio_roles_json(json_path: str | Path) -> list[str]:
    json_path = Path(json_path)
    if not json_path.exists():
        raise FileNotFoundError(f"JSON seed file not found: {json_path}")

    data = json.loads(json_path.read_text(encoding="utf-8"))

    skip_branches = {
        "Glycolipids [Fig]",
        "Eicosanoids [Fig]",
        "Nucleic acids",
        "Steroids",
        "Hormones and transmitters",
        "Antibiotics",
    }

    names: list[str] = []

    def traverse(node: dict[str, Any]) -> None:
        name = node.get("name")
        if name in skip_branches:
            return

        children = node.get("children")
        if children:
            for child in children:
                traverse(child)
            return

        if not name:
            return

        raw = str(name).strip()
        raw = re.sub(r"^[GC]\d+\s+", "", raw)        # remove KEGG-like id prefix
        raw = re.sub(r"\s*\(.*?\)", "", raw).strip() # remove parentheses blocks
        preferred = raw.split(";")[-1].strip()       # keep last alias

        if preferred:
            names.append(preferred)

    traverse(data)
    return names


def extract_raw_seed_names(
    *,
    initial_xlsx_path: str | Path,
    bio_roles_json_path: str | Path,
    out_json_path: str | Path,
) -> list[str]:
    seeds: list[str] = []
    seeds.extend(seed_list_from_initial_xlsx(initial_xlsx_path))
    seeds.extend(seed_list_from_bio_roles_json(bio_roles_json_path))

    seeds = dedupe_preserve_order(seeds)
    write_json_list(out_json_path, seeds)
    return seeds
