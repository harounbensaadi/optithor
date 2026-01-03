# compound_db_builder/step_02_expand_hydrates.py

from __future__ import annotations

from pathlib import Path
import re
from io_json import read_json_list, write_json_list


HYDRATE_DESCRIPTIONS = [
    "hydrate",
    "monohydrate",
    "dihydrate",
    "trihydrate",
    "tetrahydrate",
    "pentahydrate",
    "hexahydrate",
    "heptahydrate",
    "octahydrate",
    "nonahydrate",
    "decahydrate",
]

SALT_HINT_WORDS = {
    "chloride",
    "sulfate",
    "sulphate",
    "phosphate",
    "nitrate",
    "carbonate",
    "bicarbonate",
    "acetate",
    "citrate",
    "bromide",
    "iodide",
    "fluoride",
    "hydroxide",
    "chlorate",
    "perchlorate",
    "ferric",
    "ferrous",
}


def _remove_hydrate_description(name: str) -> str:
    pattern = r"\b(?:%s)\b" % "|".join(map(re.escape, HYDRATE_DESCRIPTIONS))
    return re.sub(pattern, "", name, flags=re.IGNORECASE).strip()


def hydrate_variants(name: str) -> list[str]:
    """
    Expand hydrate variants only when it makes sense:
      - name already mentions hydrate
      - OR name looks like a salt (SALT_HINT_WORDS)
    """
    name = str(name).strip()
    if not name:
        return []

    base = _remove_hydrate_description(name)
    if not base:
        return []

    tokens = {t.strip(" ,;-").lower() for t in base.split()}
    should_expand = bool(tokens & SALT_HINT_WORDS) or ("hydrate" in name.lower())
    if not should_expand:
        return []

    return [f"{base} {h}" for h in HYDRATE_DESCRIPTIONS]


def expand_names_with_hydrates(raw_names: list[str]) -> list[str]:
    """
    Return an extended list:
      - includes the original names
      - plus hydrate variants (when applicable)
      - deduped case-insensitively, preserving order
    """
    seen: set[str] = set()
    out: list[str] = []

    def add(s: str) -> None:
        s = str(s).strip()
        if not s:
            return
        key = s.lower()
        if key in seen:
            return
        seen.add(key)
        out.append(s)

    for n in raw_names:
        add(n)
        for v in hydrate_variants(n):
            add(v)

    return out


def expand_hydrates_from_json(
    *,
    raw_names_json: str | Path,
    out_extended_json: str | Path,
) -> list[str]:
    raw_names = read_json_list(raw_names_json)
    extended = expand_names_with_hydrates(raw_names)
    write_json_list(out_extended_json, extended)
    return extended