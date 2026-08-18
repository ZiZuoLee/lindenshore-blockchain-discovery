import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

from src.config import DATABASE_PATH


def get_connection(
    database_path: Path = DATABASE_PATH,
) -> sqlite3.Connection:
    """
    Create a SQLite connection.

    The parent directory is created automatically.
    """
    database_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(database_path)

    connection.execute(
        "PRAGMA journal_mode=WAL;"
    )

    connection.execute(
        "PRAGMA foreign_keys=ON;"
    )

    return connection


def initialize_database(
    database_path: Path = DATABASE_PATH,
) -> None:
    """
    Create all database tables if they do not exist.
    """
    with get_connection(database_path) as conn:

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tokens (
                address TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                decimals INTEGER NOT NULL
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pools (
                address TEXT PRIMARY KEY,
                token0 TEXT NOT NULL,
                token1 TEXT NOT NULL,
                fee INTEGER NOT NULL,
                FOREIGN KEY(token0)
                    REFERENCES tokens(address),
                FOREIGN KEY(token1)
                    REFERENCES tokens(address)
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS swaps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                chain TEXT NOT NULL,

                block_number INTEGER NOT NULL,
                block_timestamp INTEGER NOT NULL,

                transaction_hash TEXT NOT NULL,
                transaction_index INTEGER NOT NULL,
                log_index INTEGER NOT NULL,

                pool_address TEXT NOT NULL,
                fee_tier INTEGER NOT NULL,

                sender TEXT NOT NULL,
                recipient TEXT NOT NULL,

                amount0_raw TEXT NOT NULL,
                amount1_raw TEXT NOT NULL,

                sqrt_price_x96 TEXT NOT NULL,
                liquidity TEXT NOT NULL,
                tick INTEGER NOT NULL,

                UNIQUE(
                    transaction_hash,
                    log_index
                ),

                FOREIGN KEY(pool_address)
                    REFERENCES pools(address)
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS collector_state (
                pool_address TEXT PRIMARY KEY,
                last_processed_block INTEGER NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_swaps_pool_block
            ON swaps(pool_address, block_number)
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_swaps_timestamp
            ON swaps(block_timestamp)
            """
        )

        conn.commit()


def upsert_token(
    address: str,
    symbol: str,
    decimals: int,
) -> None:

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO tokens(
                address,
                symbol,
                decimals
            )
            VALUES (?, ?, ?)

            ON CONFLICT(address)
            DO UPDATE SET
                symbol = excluded.symbol,
                decimals = excluded.decimals
            """,
            (
                address.lower(),
                symbol,
                decimals,
            ),
        )

        conn.commit()


def upsert_pool(
    address: str,
    token0: str,
    token1: str,
    fee: int,
) -> None:

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO pools(
                address,
                token0,
                token1,
                fee
            )
            VALUES (?, ?, ?, ?)

            ON CONFLICT(address)
            DO UPDATE SET
                token0 = excluded.token0,
                token1 = excluded.token1,
                fee = excluded.fee
            """,
            (
                address.lower(),
                token0.lower(),
                token1.lower(),
                fee,
            ),
        )

        conn.commit()


def insert_swap(
    swap: dict[str, Any],
) -> bool:
    """
    Insert one swap.

    Returns True if inserted, False if duplicate.
    """
    with get_connection() as conn:

        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO swaps(
                chain,
                block_number,
                block_timestamp,
                transaction_hash,
                transaction_index,
                log_index,
                pool_address,
                fee_tier,
                sender,
                recipient,
                amount0_raw,
                amount1_raw,
                sqrt_price_x96,
                liquidity,
                tick
            )
            VALUES (
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?
            )
            """,
            (
                swap["chain"],
                swap["block_number"],
                swap["block_timestamp"],
                swap["transaction_hash"],
                swap["transaction_index"],
                swap["log_index"],
                swap["pool_address"].lower(),
                swap["fee_tier"],
                swap["sender"].lower(),
                swap["recipient"].lower(),
                str(swap["amount0_raw"]),
                str(swap["amount1_raw"]),
                str(swap["sqrt_price_x96"]),
                str(swap["liquidity"]),
                swap["tick"],
            ),
        )

        conn.commit()

        return cursor.rowcount > 0


def get_last_processed_block(
    pool_address: str,
) -> int | None:

    with get_connection() as conn:

        row = conn.execute(
            """
            SELECT last_processed_block
            FROM collector_state
            WHERE pool_address = ?
            """,
            (
                pool_address.lower(),
            ),
        ).fetchone()

    if row is None:
        return None

    return int(row[0])


def set_last_processed_block(
    pool_address: str,
    block_number: int,
) -> None:

    with get_connection() as conn:

        conn.execute(
            """
            INSERT INTO collector_state(
                pool_address,
                last_processed_block
            )
            VALUES (?, ?)

            ON CONFLICT(pool_address)
            DO UPDATE SET
                last_processed_block =
                    excluded.last_processed_block,
                updated_at =
                    CURRENT_TIMESTAMP
            """,
            (
                pool_address.lower(),
                block_number,
            ),
        )

        conn.commit()


def load_swaps_dataframe() -> pd.DataFrame:

    with get_connection() as conn:

        query = """
        SELECT
            s.*,

            p.token0,
            p.token1,

            t0.symbol AS token0_symbol,
            t0.decimals AS token0_decimals,

            t1.symbol AS token1_symbol,
            t1.decimals AS token1_decimals

        FROM swaps AS s

        JOIN pools AS p
            ON s.pool_address = p.address

        JOIN tokens AS t0
            ON p.token0 = t0.address

        JOIN tokens AS t1
            ON p.token1 = t1.address

        ORDER BY
            s.block_number,
            s.transaction_index,
            s.log_index
        """

        return pd.read_sql_query(
            query,
            conn,
        )


def get_pool_rows() -> list[dict]:

    with get_connection() as conn:

        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            """
            SELECT *
            FROM pools
            ORDER BY fee
            """
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]