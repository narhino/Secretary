import shutil
from pathlib import Path

import pytest

from secretary import config

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture
def home(tmp_path, monkeypatch):
    """A throwaway copy of the data files, with config pointed at it."""
    for rel in ("data/settings.yaml", "CLAUDE.md", "goals/goals.md", "profile/me.md"):
        src = REPO / rel
        if src.exists():
            (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, tmp_path / rel)
    (tmp_path / "data" / "state").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(config, "DATA", tmp_path / "data")
    monkeypatch.setattr(config, "STATE", tmp_path / "data" / "state")
    monkeypatch.setattr(config, "SETTINGS_FILE", tmp_path / "data" / "settings.yaml")
    monkeypatch.setattr(config, "REMINDERS_FILE", tmp_path / "data" / "reminders.yaml")
    monkeypatch.setattr(config, "TASKS_FILE", tmp_path / "data" / "tasks.yaml")
    monkeypatch.setattr(config, "SENT_FILE", tmp_path / "data" / "state" / "sent.json")
    monkeypatch.setattr(config, "WORKOUTS_FILE", tmp_path / "fitness" / "workouts.csv")
    monkeypatch.setattr(config, "BODY_FILE", tmp_path / "fitness" / "body.csv")
    monkeypatch.setattr(config, "GOALS_FILE", tmp_path / "goals" / "goals.md")
    monkeypatch.setenv("SECRETARY_GIT_SYNC", "0")
    monkeypatch.setenv("SECRETARY_NOW", "2026-10-21T08:00")
    return tmp_path
