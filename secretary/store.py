"""Small helpers for reading and writing the YAML / CSV / JSON files."""
from __future__ import annotations

import csv
import json
import os
import tempfile
from datetime import date, datetime
from pathlib import Path

import yaml


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    os.replace(tmp, path)


def load_yaml(path: Path, default=None):
    if not path.exists():
        return default
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return default if data is None else data


def save_yaml(path: Path, data, header: str = "") -> None:
    body = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100)
    _atomic_write(path, header + body)


def yaml_header(path: Path) -> str:
    """Leading comment block of a YAML file, kept when the file is rewritten."""
    if not path.exists():
        return ""
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines(keepends=True):
        if line.startswith("#") or not line.strip():
            lines.append(line)
        else:
            break
    return "".join(lines)


def load_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8") or "null") or default


def save_json(path: Path, data) -> None:
    _atomic_write(path, json.dumps(data, indent=2, sort_keys=True) + "\n")


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def append_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists() or path.stat().st_size == 0
    with path.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        if new_file:
            writer.writeheader()
        writer.writerows(rows)


def iso(value) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)
