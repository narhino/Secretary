import json

import pytest

from secretary import cli, daylog, ingest, places, store


def test_number_parsing():
    assert ingest.number("8,432") == 8432
    assert ingest.number("6.3 km") == 6.3
    assert ingest.number(410) == 410
    assert ingest.number("") is None and ingest.number("n/a") is None


def test_health_payload_updates_daily_log(home):
    row = ingest.ingest("health", {"date": "2026-10-20", "steps": "8,432", "active_kcal": "410 kcal", "distance_km": "6.27"})
    assert (row["steps"], row["active_kcal"], row["distance_km"]) == ("8432", "410", "6.3")
    ingest.ingest("health", json.dumps({"date": "2026-10-20", "steps": 9001}))
    assert daylog.get(__import__("datetime").date(2026, 10, 20))["steps"] == "9001"
    with pytest.raises(ValueError):
        ingest.ingest("health", {"date": "2026-10-20"})
    with pytest.raises(ValueError):
        ingest.ingest("health", {"date": "2030-01-01", "steps": 5})


def test_location_payload_logs_breadcrumb_and_place(home):
    ingest.ingest("location", {"time": "2026-10-20 18:32", "lat": "13.7790", "lon": "100.5440", "name": "Fitness First Ari",
                               "event": "arrive", "kind": "gym"})
    ingest.ingest("location", {"time": "2026-10-20T20:00:00+07:00", "lat": 13.77, "lon": 100.54, "event": "ping"})
    ingest.ingest("location", {"time": "2026-10-20 19:50", "lat": 13.779, "lon": 100.544, "name": "Fitness First Ari", "event": "leave"})
    crumbs = store.read_csv(ingest.locations_file())
    assert len(crumbs) == 3 and crumbs[1]["time"] == "2026-10-20 20:00"
    assert [r["name"] for r in store.read_csv(places.places_file())] == ["Fitness First Ari"]
    with pytest.raises(ValueError):
        ingest.ingest("location", {"lat": 200, "lon": 1})
    with pytest.raises(ValueError):
        ingest.ingest("weather", {})


def test_app_sync_writes_are_idempotent(home, capsys):
    ingest.ingest("health", {"date": "2026-10-20", "steps": 7000})
    ingest.ingest("location", {"time": "2026-10-20 18:32", "lat": 13.779, "lon": 100.544, "name": "Gym", "kind": "gym"})
    assert cli.main(["app-sync", "--since", "2026-10-19"]) == 0
    writes = json.loads(capsys.readouterr().out)
    assert {w["collection"] for w in writes} == {"health", "places"}
    health = next(w for w in writes if w["collection"] == "health")
    assert health["doc_id"] == "2026-10-20" and health["data"]["steps"] == 7000
    again = ingest.app_writes(__import__("datetime").date(2026, 10, 19))
    assert [w["doc_id"] for w in again] == [w["doc_id"] for w in writes]


def test_cli_ingest_reads_payload_env(home, monkeypatch, capsys):
    monkeypatch.setenv("PAYLOAD", json.dumps({"date": "2026-10-21", "steps": 1234}))
    assert cli.main(["ingest", "health"]) == 0
    assert "1234" in capsys.readouterr().out
