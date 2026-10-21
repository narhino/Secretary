"""Paths, settings and clock for the secretary."""
from __future__ import annotations

import os
import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(os.environ.get("SECRETARY_HOME", Path(__file__).resolve().parent.parent))
DATA = ROOT / "data"
STATE = DATA / "state"
SETTINGS_FILE = DATA / "settings.yaml"
REMINDERS_FILE = DATA / "reminders.yaml"
TASKS_FILE = DATA / "tasks.yaml"
SENT_FILE = STATE / "sent.json"
WORKOUTS_FILE = ROOT / "fitness" / "workouts.csv"
BODY_FILE = ROOT / "fitness" / "body.csv"
GOALS_FILE = ROOT / "goals" / "goals.md"

DEFAULT_SETTINGS = {
    "timezone": "Asia/Bangkok",
    "default_time": "09:00",
    "lookback_hours": 6,
    "morning_brief": {"enabled": True, "time": "07:30"},
    "evening_checkin": {"enabled": False, "time": "21:30"},
    "weekly_review": {"enabled": True, "day": "sun", "time": "19:00"},
    "discord": {"owner_user_id": "", "mention_owner": True},
}


def load_env_file(path: Path | None = None) -> None:
    """Load KEY=VALUE lines from .env into os.environ (existing vars win)."""
    path = path or ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if value[:1] in ("'", '"') and value[0] in value[1:]:
            value = value[1:value.index(value[0], 1)]
        else:
            value = re.split(r"\s+#", value, maxsplit=1)[0].strip()
        if value:
            os.environ.setdefault(key.strip(), value)


def _merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def load_settings() -> dict:
    raw = {}
    if SETTINGS_FILE.exists():
        raw = yaml.safe_load(SETTINGS_FILE.read_text(encoding="utf-8")) or {}
    return _merge(DEFAULT_SETTINGS, raw)


@lru_cache(maxsize=None)
def _zone(name: str) -> ZoneInfo:
    return ZoneInfo(name)


def tz(settings: dict | None = None) -> ZoneInfo:
    return _zone((settings or load_settings())["timezone"])


def now(settings: dict | None = None) -> datetime:
    """Current local time. SECRETARY_NOW (ISO format) overrides it for testing."""
    zone = tz(settings)
    fake = os.environ.get("SECRETARY_NOW")
    if fake:
        dt = datetime.fromisoformat(fake)
        return dt if dt.tzinfo else dt.replace(tzinfo=zone)
    return datetime.now(zone)


def owner_id(settings: dict | None = None) -> str:
    settings = settings or load_settings()
    return str(os.environ.get("DISCORD_OWNER_ID") or settings["discord"].get("owner_user_id") or "")
