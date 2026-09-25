from contextlib import closing
from pathlib import Path
import sqlite3

import pandas as pd


db_path = Path(__file__).resolve().parent / "employee_events.db"
db_uri = f"{db_path.as_uri()}?mode=ro"


def _connect_read_only():
    """Open the bundled fixture without granting write access."""
    connection = sqlite3.connect(db_uri, uri=True)
    try:
        connection.execute("PRAGMA query_only = ON")
    except Exception:
        connection.close()
        raise
    return connection


class QueryMixin:
    """Execute read-only queries against the bundled SQLite database."""

    def pandas_query(self, sql_query, params=()):
        """Return a SQL query result as a Pandas DataFrame."""
        with closing(_connect_read_only()) as connection:
            return pd.read_sql_query(
                sql_query,
                connection,
                params=params,
            )

    def query(self, sql_query, params=()):
        """Return a SQL query result as a list of tuples."""
        with closing(_connect_read_only()) as connection:
            with closing(connection.cursor()) as cursor:
                cursor.execute(sql_query, params)
                return cursor.fetchall()
