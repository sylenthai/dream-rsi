from __future__ import annotations

import os
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
# Ephemeral runtime state written by default-constructed services (RunStore, create_app).
_DEFAULT_DB = _REPO_ROOT / "runs" / "dream_rsi.sqlite3"


def _remove_if_created() -> None:
    if not _DEFAULT_DB.exists():
        return
    try:
        _DEFAULT_DB.unlink()
    except OSError:  # pragma: no cover - file still held by another process
        return
    runs_dir = _DEFAULT_DB.parent
    try:
        if not any(runs_dir.iterdir()):
            runs_dir.rmdir()
    except OSError:  # pragma: no cover - directory not empty or in use
        pass


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus) -> None:
    """Keep the working tree portable: default services must not leave runtime artifacts."""
    _remove_if_created()


def pytest_sessionstart(session) -> None:
    _remove_if_created()


@pytest.fixture(scope="session")
def isolated_home(tmp_path_factory) -> Path:
    """Dedicated HOME/XDG directory for tests that spawn nested interpreters."""
    home = tmp_path_factory.mktemp("home")
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    return home
