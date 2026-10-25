"""Data pushed from the phone (iOS Shortcuts / Android automation) through GitHub repository_dispatch.

Two event types:
  health    {"date": "2026-10-25", "steps": 8432, "active_kcal": 410, "distance_km": 6.3}
  location  {"time": "2026-10-25 18:32", "lat": 13.779, "lon": 100.544, "name": "Fitness First",
             "address": "...", "event": "arrive|leave|ping", "kind": "gym"}
Phone apps often send numbers as text ("8,432", "6.3 km"), so values are parsed leniently.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime

from . import config, daylog, places, store
from .reminders import parse_date

LOCATION_FIELDS = ["time", "lat", "lon", "name", "address", "event", "kind", "source"]
_NUM = re.compile(r"-?\d[\d,]*\.?\d*")


def locations_file():
    return config.DATA / "locations.csv"


def number(value):
    """8432 / "8,432" / "6.3 km" / "" -> float or None."""
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    m = _NUM.search(str(value))
    return float(m.group().replace(",", "")) if m else None


def parse_time(value) -> datetime:
    text = str(value or "").strip()
    if not text:
        return config.now()
    for fmt in (None, "%Y-%m-%d %H:%M", "%d %b %Y at %H:%M", "%b %d, %Y at %H:%M", "%d/%m/%Y %H:%M"):
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00")) if fmt is None else datetime.strptime(text, fmt)
            break
        except ValueError:
            continue
    else:
        raise ValueError(f"unrecognised time {text!r}")
    zone = config.tz()
    return dt.astimezone(zone) if dt.tzinfo else dt.replace(tzinfo=zone)


def ingest_health(payload: dict) -> dict:
    day = parse_date(payload.get("date")) or config.now().date()
    if day > config.now().date():
        raise ValueError("date is in the future")
    fields = {k: number(payload.get(k)) for k in ("steps", "active_kcal", "distance_km")}
    if all(v is None for v in fields.values()):
        raise ValueError("no steps, active_kcal or distance_km in payload")
    return daylog.update(day, **{k: v for k, v in fields.items() if v is not None})


def ingest_location(payload: dict) -> dict:
    lat, lon = number(payload.get("lat")), number(payload.get("lon"))
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("lat/lon missing or out of range")
    when = parse_time(payload.get("time"))
    event = str(payload.get("event") or "ping").lower()
    kind = str(payload.get("kind") or "other").lower()
    row = {"time": when.strftime("%Y-%m-%d %H:%M"), "lat": round(lat, 5), "lon": round(lon, 5),
           "name": str(payload.get("name") or "")[:80], "address": str(payload.get("address") or "")[:160],
           "event": event if event in ("arrive", "leave", "ping") else "ping",
           "kind": kind if kind in places.KINDS else "other", "source": str(payload.get("source") or "phone")[:20]}
    store.append_csv(locations_file(), LOCATION_FIELDS, [row])
    if row["event"] != "leave" and row["name"]:
        places.add(when.date(), row["name"], row["kind"], row["address"][:60], when.strftime("%H:%M"),
                   None, lat, lon, "phone")
    return row


def ingest(event: str, payload) -> dict:
    if isinstance(payload, str):
        payload = json.loads(payload or "{}")
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")
    if event == "health":
        return ingest_health(payload)
    if event == "location":
        return ingest_location(payload)
    raise ValueError(f"unknown event {event!r}")


def app_writes(since: date) -> list[dict]:
    """ArtifactData batch writes that mirror recent phone data into the HQ app (idempotent ids)."""
    writes = []
    for row in daylog.load():
        if row["date"] >= since.isoformat() and row.get("steps"):
            writes.append({"op": "set", "collection": "health", "doc_id": row["date"], "data": {
                "day": row["date"], "steps": number(row.get("steps")), "active_kcal": number(row.get("active_kcal")),
                "distance_km": number(row.get("distance_km")), "exercise_min": None, "source": "phone",
                "updatedAt": datetime.now(config.tz()).isoformat(), "processed": True}})
    for row in store.read_csv(locations_file()):
        if row["time"][:10] < since.isoformat() or not row.get("name") or row.get("event") == "leave":
            continue
        doc_id = "loc-" + hashlib.sha1(f"{row['time']}|{row['name']}".encode()).hexdigest()[:12]
        writes.append({"op": "set", "collection": "places", "doc_id": doc_id, "data": {
            "day": row["time"][:10], "at": parse_time(row["time"]).isoformat(), "name": row["name"],
            "area": row.get("address", "")[:60] or None, "kind": row.get("kind") or "other", "arrived": row["time"][11:16],
            "minutes": None, "lat": number(row["lat"]), "lon": number(row["lon"]), "source": "phone", "processed": True}})
    return writes
