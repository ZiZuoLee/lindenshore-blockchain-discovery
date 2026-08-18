from pathlib import Path

from src.database import (
    get_connection,
    initialize_database,
)


def test_database_tables_created(
    tmp_path: Path,
):

    database_path = (
        tmp_path
        / "test.db"
    )

    initialize_database(
        database_path
    )

    with get_connection(
        database_path
    ) as conn:

        rows = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            """
        ).fetchall()

    tables = {
        row[0]
        for row in rows
    }

    assert "tokens" in tables
    assert "pools" in tables
    assert "swaps" in tables
    assert "collector_state" in tables