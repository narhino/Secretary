"""Places visited (data/places.csv), synced from the HQ app's Maps Timeline imports."""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from . import config, store

FIELDS = ["date", "arrived", "name", "area", "kind", "minutes", "lat", "lon", "source"]
KINDS = ["home", "gym", "work", "food", "shop", "health", "social", "transit", "outdoors", "other"]


def places_file():
    return config.DATA / "places.csv"


def add(day: date, name: str, kind: str = "other", area: str = "", arrived: str = "", minutes=None,
        lat=None, lon=None, source: str = "manual") -> dict:
    if not name.strip():
        raise ValueError("name required")
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    row = {"date": day.isoformat(), "arrived": arrived, "name": name.strip(), "area": area, "kind": kind,
           "minutes": "" if minutes in (None, "") else int(minutes),
           "lat": "" if lat in (None, "") else round(float(lat), 5),
           "lon": "" if lon in (None, "") else round(float(lon), 5), "source": source}
    store.append_csv(places_file(), FIELDS, [row])
    return row


def top(end: date, days: int = 30, n: int = 8) -> list[tuple[str, int]]:
    start = (end - timedelta(days=days - 1)).isoformat()
    rows = [r for r in store.read_csv(places_file()) if start <= r["date"] <= end.isoformat()]
    return Counter(r["name"] for r in rows).most_common(n)
