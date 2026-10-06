import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import database.db as db  # noqa: E402

# app.py runs init_db()/seed_db() at import time, so point the DB at a
# throwaway file before importing it to keep the real database untouched.
db.DB_PATH = Path(tempfile.mkdtemp()) / "bootstrap.db"

from app import app as flask_app  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    db.seed_db()
    flask_app.config["TESTING"] = True
    return flask_app.test_client()
