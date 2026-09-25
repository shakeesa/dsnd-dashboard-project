from hashlib import sha256
import sqlite3

import pandas as pd
import pytest

import employee_events
import employee_events.sql_execution as sql_execution
from employee_events import Employee, QueryBase, QueryMixin, Team


EXPECTED_TABLE_COUNTS = {
    "employee": 25,
    "team": 5,
    "employee_events": 6525,
    "notes": 125,
}
EXPECTED_DB_SHA256 = (
    "0dd9f90df77f6dc580c34673f8b7f6011869cba36b9892114818b040f6d94d8e"
)
QUERY_ERROR_TYPES = {
    "query": sqlite3.OperationalError,
    "pandas_query": pd.errors.DatabaseError,
}


def _database_checksum():
    return sha256(sql_execution.db_path.read_bytes()).hexdigest()


@pytest.fixture
def tracked_connections(monkeypatch):
    real_connect = sqlite3.connect
    state = {"calls": [], "connections": []}

    class TrackingConnection(sqlite3.Connection):
        was_closed = False

        def close(self):
            self.was_closed = True
            super().close()

    def tracking_connect(*args, **kwargs):
        state["calls"].append((args, kwargs.copy()))
        kwargs["factory"] = TrackingConnection
        connection = real_connect(*args, **kwargs)
        state["connections"].append(connection)
        return connection

    monkeypatch.setattr(sql_execution.sqlite3, "connect", tracking_connect)
    return state


def test_public_api_and_inheritance():
    assert employee_events.__all__ == [
        "Employee",
        "QueryBase",
        "QueryMixin",
        "Team",
    ]
    assert issubclass(QueryBase, QueryMixin)
    assert issubclass(Employee, QueryBase)
    assert issubclass(Team, QueryBase)
    assert QueryBase.name == ""
    assert QueryBase().names() == []
    assert sql_execution.db_path.is_absolute()
    assert sql_execution.db_path.is_file()
    assert sql_execution.db_uri == f"{sql_execution.db_path.as_uri()}?mode=ro"


def test_execution_methods_return_expected_types():
    query_model = QueryMixin()

    tuple_rows = query_model.query(
        "SELECT employee_id FROM employee ORDER BY employee_id LIMIT 2"
    )
    frame_rows = query_model.pandas_query(
        "SELECT employee_id FROM employee ORDER BY employee_id LIMIT 2"
    )

    assert tuple_rows == [(1,), (2,)]
    assert isinstance(tuple_rows, list)
    assert isinstance(frame_rows, pd.DataFrame)
    assert frame_rows.to_dict("records") == [
        {"employee_id": 1},
        {"employee_id": 2},
    ]


def test_execution_connections_enforce_query_only_mode():
    query_model = QueryMixin()

    assert query_model.query("PRAGMA query_only") == [(1,)]
    query_only = query_model.pandas_query("PRAGMA query_only")
    assert query_only.iloc[0, 0] == 1


@pytest.mark.parametrize(
    ("method_name", "sql_query"),
    [
        ("query", "SELECT COUNT(*) FROM employee"),
        ("pandas_query", "SELECT COUNT(*) FROM employee"),
    ],
)
def test_connection_closes_after_success(
    tracked_connections,
    method_name,
    sql_query,
):
    getattr(QueryMixin(), method_name)(sql_query)

    assert len(tracked_connections["connections"]) == 1
    assert tracked_connections["connections"][0].was_closed
    connect_args, connect_kwargs = tracked_connections["calls"][0]
    assert connect_args == (sql_execution.db_uri,)
    assert connect_kwargs == {"uri": True}


@pytest.mark.parametrize("method_name", ["query", "pandas_query"])
def test_connection_closes_when_query_fails(
    tracked_connections,
    method_name,
):
    with pytest.raises(QUERY_ERROR_TYPES[method_name]) as error:
        getattr(QueryMixin(), method_name)("SELECT * FROM missing_table")

    if method_name == "pandas_query":
        assert isinstance(error.value.__cause__, sqlite3.OperationalError)
    assert len(tracked_connections["connections"]) == 1
    assert tracked_connections["connections"][0].was_closed


def test_connection_closes_when_read_only_setup_fails(monkeypatch):
    real_connect = sqlite3.connect
    opened_connections = []

    class SetupFailureConnection(sqlite3.Connection):
        was_closed = False

        def execute(self, sql_query, *args, **kwargs):
            if sql_query == "PRAGMA query_only = ON":
                raise sqlite3.OperationalError("query-only setup failed")
            return super().execute(sql_query, *args, **kwargs)

        def close(self):
            self.was_closed = True
            super().close()

    def setup_failure_connect(*args, **kwargs):
        kwargs["factory"] = SetupFailureConnection
        connection = real_connect(*args, **kwargs)
        opened_connections.append(connection)
        return connection

    monkeypatch.setattr(
        sql_execution.sqlite3,
        "connect",
        setup_failure_connect,
    )

    with pytest.raises(
        sqlite3.OperationalError,
        match="query-only setup failed",
    ):
        QueryMixin().query("SELECT 1")

    assert len(opened_connections) == 1
    assert opened_connections[0].was_closed


@pytest.mark.parametrize("method_name", ["query", "pandas_query"])
@pytest.mark.parametrize(
    "sql_query",
    [
        "UPDATE employee SET first_name = 'Changed' WHERE employee_id = 1",
        "DROP TABLE notes",
    ],
)
def test_mutating_sql_is_rejected_and_fixture_is_unchanged(
    method_name,
    sql_query,
):
    checksum_before = _database_checksum()

    with pytest.raises(QUERY_ERROR_TYPES[method_name]) as error:
        getattr(QueryMixin(), method_name)(sql_query)

    if method_name == "pandas_query":
        assert isinstance(error.value.__cause__, sqlite3.OperationalError)
    assert "readonly" in str(error.value).lower()
    assert _database_checksum() == checksum_before == EXPECTED_DB_SHA256


def test_read_only_uri_does_not_create_a_missing_database(
    tmp_path,
    monkeypatch,
):
    missing_database = tmp_path / "missing.db"
    missing_uri = f"{missing_database.as_uri()}?mode=ro"
    monkeypatch.setattr(sql_execution, "db_uri", missing_uri)

    with pytest.raises(sqlite3.OperationalError):
        QueryMixin().query("SELECT 1")

    assert not missing_database.exists()


def test_good_query_succeeds_after_failed_query():
    query_model = QueryMixin()

    with pytest.raises(sqlite3.OperationalError):
        query_model.query("SELECT * FROM missing_table")

    assert query_model.query("SELECT COUNT(*) FROM employee") == [(25,)]


def test_employee_names_and_username():
    model = Employee()
    names = model.names()

    assert len(names) == 25
    assert names[0] == ("Alex Martinez", 1)
    assert [entity_id for _, entity_id in names] == list(range(1, 26))
    assert model.username(1) == [("Alex Martinez",)]
    assert model.username(9999) == []
    assert model.username("1 OR 1=1") == []


def test_team_names_and_username():
    model = Team()
    names = model.names()

    assert names == [
        ("Alpha Team", 1),
        ("Bravo Team", 2),
        ("Charlie Team", 3),
        ("Delta Team", 4),
        ("Echo Team", 5),
    ]
    assert model.username(1) == [("Alpha Team",)]
    assert model.username(9999) == []
    assert model.username("1 OR 1=1") == []


@pytest.mark.parametrize("model", [Employee(), Team()])
def test_event_counts_are_ordered_and_have_stable_columns(model):
    event_counts = model.event_counts(1)

    assert list(event_counts.columns) == [
        "event_date",
        "positive_events",
        "negative_events",
    ]
    assert len(event_counts) == 261
    assert event_counts["event_date"].is_monotonic_increasing
    assert event_counts["event_date"].iloc[0] == "2023-10-23"
    assert event_counts["event_date"].iloc[-1] == "2024-10-21"


def test_employee_event_aggregation_matches_fixture():
    event_counts = Employee().event_counts(1)

    assert int(event_counts["positive_events"].sum()) == 677
    assert int(event_counts["negative_events"].sum()) == 411


@pytest.mark.parametrize(
    ("model", "expected_count"),
    [(Employee(), 5), (Team(), 35)],
)
def test_notes_are_ordered_and_have_stable_columns(model, expected_count):
    notes = model.notes(1)

    assert list(notes.columns) == ["note_date", "note"]
    assert len(notes) == expected_count
    assert notes["note_date"].is_monotonic_increasing
    assert notes["note"].notna().all()


def test_employee_model_data_shape_feature_order_and_values():
    model_data = Employee().model_data(1)

    assert list(model_data.columns) == [
        "positive_events",
        "negative_events",
    ]
    assert model_data.shape == (1, 2)
    assert model_data.iloc[0].tolist() == [677, 411]


def test_team_model_data_is_one_row_per_employee():
    model_data = Team().model_data(1)

    assert list(model_data.columns) == [
        "positive_events",
        "negative_events",
    ]
    assert model_data.shape == (7, 2)
    assert model_data.notna().all().all()


@pytest.mark.parametrize("model", [Employee(), Team()])
def test_nonexistent_and_injection_like_ids_do_not_broaden_results(model):
    for entity_id in (9999, "1 OR 1=1", "1; DROP TABLE employee"):
        assert model.event_counts(entity_id).empty
        assert model.notes(entity_id).empty
        assert model.username(entity_id) == []


def test_only_controlled_identifiers_can_be_interpolated():
    class UnsafeEntity(QueryBase):
        name = 'employee; DROP TABLE employee; --'

    with pytest.raises(ValueError, match="Unsupported query entity"):
        UnsafeEntity().event_counts(1)


def test_database_remains_read_only():
    checksum_before = _database_checksum()
    query_model = QueryMixin()
    observed_counts = {
        table: query_model.query(f'SELECT COUNT(*) FROM "{table}"')[0][0]
        for table in EXPECTED_TABLE_COUNTS
    }

    assert observed_counts == EXPECTED_TABLE_COUNTS
    assert _database_checksum() == checksum_before == EXPECTED_DB_SHA256
