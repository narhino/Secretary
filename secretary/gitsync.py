"""Keep the local clone in sync with GitHub so every surface shares one memory."""
from __future__ import annotations

import logging
import os
import subprocess

from . import config

log = logging.getLogger(__name__)


def enabled() -> bool:
    return os.environ.get("SECRETARY_GIT_SYNC", "1") != "0" and (config.ROOT / ".git").exists()


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=config.ROOT, capture_output=True, text=True, timeout=120)


def pull() -> bool:
    if not enabled():
        return False
    res = _git("pull", "--rebase", "--autostash", "--quiet")
    if res.returncode != 0:
        log.warning("git pull failed: %s", res.stderr.strip())
        _git("rebase", "--abort")
        return False
    return True


def commit_and_push(message: str) -> bool:
    """Commit every change and push. Returns True if something was pushed."""
    if not enabled():
        return False
    _git("add", "-A")
    if _git("diff", "--cached", "--quiet").returncode == 0:
        return False
    res = _git("commit", "-m", message, "--quiet")
    if res.returncode != 0:
        log.warning("git commit failed: %s", res.stderr.strip())
        return False
    for _ in range(3):
        if _git("push", "--quiet").returncode == 0:
            return True
        pull()
    log.warning("git push failed; changes stay committed locally")
    return False
