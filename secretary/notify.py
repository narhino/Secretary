"""Deliver messages to Discord through an incoming webhook (no bot needed)."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

LIMIT = 1900


def chunks(text: str, limit: int = LIMIT) -> list[str]:
    """Split on line boundaries so each piece fits in one Discord message."""
    out, current = [], ""
    for line in text.splitlines(keepends=True):
        while len(line) > limit:
            if current:
                out.append(current)
                current = ""
            out.append(line[:limit])
            line = line[limit:]
        if len(current) + len(line) > limit:
            out.append(current)
            current = ""
        current += line
    if current.strip():
        out.append(current)
    return out


def send_webhook(url: str, text: str, mention_user_id: str = "", username: str = "Secretary") -> None:
    for i, piece in enumerate(chunks(text)):
        content = f"<@{mention_user_id}> {piece}" if mention_user_id and i == 0 else piece
        payload = {"content": content, "username": username,
                   "allowed_mentions": {"users": [mention_user_id] if mention_user_id else []}}
        _post(url, payload)


def _post(url: str, payload: dict, attempts: int = 4) -> None:
    data = json.dumps(payload).encode()
    for attempt in range(attempts):
        req = urllib.request.Request(url, data=data, headers={
            "Content-Type": "application/json", "User-Agent": "secretary (github.com, 1.0)"})
        try:
            with urllib.request.urlopen(req, timeout=20):
                return
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < attempts - 1:
                retry = json.loads(exc.read() or b"{}").get("retry_after", 2)
                time.sleep(float(retry) + 0.5)
                continue
            raise
        except urllib.error.URLError:
            if attempt == attempts - 1:
                raise
            time.sleep(2 ** attempt)
