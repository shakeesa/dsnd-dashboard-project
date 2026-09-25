from hashlib import sha256
from pathlib import Path
from sqlite3 import connect

import pytest


project_root = Path(__file__).resolve().parents[1]
EXPECTED_DB_SHA256 = (
    "0dd9f90df77f6dc580c34673f8b7f6011869cba36b9892114818b040f6d94d8e"
)


@pytest.fixture
def db_path():
    return (
        project_root
        / "python-package"
        / "employee_events"
        / "employee_events.db"
    )


@pytest.fixture
def db_conn(db_path):
    connection = connect(f"{db_path.as_uri()}?mode=ro", uri=True)
    try:
        yield connection
    finally:
        connection.close()


@pytest.fixture
def table_names(db_conn):
    rows = db_conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    return [row[0] for row in rows]


def test_db_exists(db_path):
    assert db_path.is_file()


def test_employee_table_exists(table_names):
    assert "employee" in table_names


def test_team_table_exists(table_names):
    assert "team" in table_names


def test_employee_events_table_exists(table_names):
    assert "employee_events" in table_names


def test_notes_table_exists(table_names):
    assert "notes" in table_names


def test_database_integrity(db_conn):
    assert db_conn.execute("PRAGMA integrity_check").fetchall() == [("ok",)]


def test_database_checksum(db_path):
    assert sha256(db_path.read_bytes()).hexdigest() == EXPECTED_DB_SHA256


def test_fixture_row_counts(db_conn):
    expected_counts = {
        "employee": 25,
        "team": 5,
        "employee_events": 6525,
        "notes": 125,
    }

    observed_counts = {
        table: db_conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        for table in expected_counts
    }

    assert observed_counts == expected_counts
