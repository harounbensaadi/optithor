# compound_db_builder/io_json.py

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_json(path: str | Path, obj: Any) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def read_json(path: str | Path) -> Any:
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_list(path: str | Path, items: list[str]) -> Path:
    return write_json(path, items)


def read_json_list(path: str | Path) -> list[str]:
    data = read_json(path)
    if not isinstance(data, list) or not all(isinstance(x, str) for x in data):
        raise ValueError(f"Expected a JSON list[str] at {path}")
    return data


def dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for s in items:
        s = str(s).strip()
        if not s:
            continue
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out
