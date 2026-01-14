import os
import pathlib
import sys

from promptrefine.utils import functions
from promptrefine.db import dbStoring

ROOT_DIR = pathlib.Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "backEnd" / "src"
sys.path.insert(0, str(SRC_DIR))


def test_token_used_creates_file(tmp_path, monkeypatch):
    # Call tokenUsed and ensure tokenUsed.txt is created and contains an integer
    # Backup existing file if present
    backend_dir = ROOT_DIR / "backEnd"
    token_file = backend_dir / "tokenUsed.txt"
    if token_file.exists():
        backup = tmp_path / "tokenUsed_backup.txt"
        token_file.replace(backup)
        restored = True
    else:
        restored = False

    try:
        functions.tokenUsed(3)
        assert token_file.exists()
        content = token_file.read_text().strip()
        assert content.isdigit()
    finally:
        # cleanup: remove token file
        if token_file.exists():
            token_file.unlink()
        if restored:
            (tmp_path / "tokenUsed_backup.txt").replace(token_file)


def test_init_db_creates_sqlite_file():
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(dbStoring.__file__), "..", "..", ".."))
    db_path = os.path.join(backend_dir, "db", "scoringHistory.sqlite")
    # remove if exists
    if os.path.exists(db_path):
        os.remove(db_path)
    dbStoring.init_db()
    assert os.path.exists(db_path)
