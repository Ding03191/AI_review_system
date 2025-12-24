import os
import pathlib

from backEnd import functions
from backEnd import dbStoring


def test_token_used_creates_file(tmp_path, monkeypatch):
    # Call tokenUsed and ensure tokenUsed.txt is created and contains an integer
    # Backup existing file if present
    base_dir = pathlib.Path(functions.__file__).parent
    token_file = base_dir / "tokenUsed.txt"
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
    base_dir = os.path.dirname(dbStoring.__file__)
    db_path = os.path.join(base_dir, 'scoringHistory.sqlite')
    # remove if exists
    if os.path.exists(db_path):
        os.remove(db_path)
    dbStoring.init_db()
    assert os.path.exists(db_path)
