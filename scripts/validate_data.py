import sqlite3

from src.config import DATABASE_PATH


def main() -> None:

    connection = sqlite3.connect(
        DATABASE_PATH
    )

    cursor = (
        connection.cursor()
    )

    print()
    print(
        "=" * 72
    )

    print(
        "Blockchain Dataset Validation"
    )

    print(
        "=" * 72
    )

    tables = cursor.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        ORDER BY name
        """
    ).fetchall()

    print()
    print(
        "Database tables:"
    )

    for table in tables:
        print(
            f"  - {table[0]}"
        )

    total_swaps = cursor.execute(
        """
        SELECT COUNT(*)
        FROM swaps
        """
    ).fetchone()[0]

    print()
    print(
        f"Total swaps: "
        f"{total_swaps:,}"
    )

    pools = cursor.execute(
        """
        SELECT
            p.address,
            p.fee,
            t0.symbol,
            t1.symbol,
            COUNT(s.id) AS swap_count
        FROM pools p

        JOIN tokens t0
            ON p.token0 = t0.address

        JOIN tokens t1
            ON p.token1 = t1.address

        LEFT JOIN swaps s
            ON p.address =
               s.pool_address

        GROUP BY
            p.address,
            p.fee,
            t0.symbol,
            t1.symbol

        ORDER BY p.fee
        """
    ).fetchall()

    print()
    print(
        "Pools:"
    )

    for (
        address,
        fee,
        token0,
        token1,
        swaps,
    ) in pools:

        print(
            f"  "
            f"{fee / 10000:.2f}% "
            f"{token0}/{token1} "
            f"{address} "
            f"swaps={swaps:,}"
        )

    invalid_signs = (
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM swaps
            WHERE
                (
                    CAST(amount0_raw AS REAL) > 0
                    AND
                    CAST(amount1_raw AS REAL) > 0
                )
                OR
                (
                    CAST(amount0_raw AS REAL) < 0
                    AND
                    CAST(amount1_raw AS REAL) < 0
                )
            """
        )
        .fetchone()[0]
    )


    zero_amount_events = (
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM swaps
            WHERE
                CAST(amount0_raw AS REAL) = 0
                OR
                CAST(amount1_raw AS REAL) = 0
            """
        )
        .fetchone()[0]
    )

    print()
    print(
        "True same-sign swap violations: "
        f"{invalid_signs}"
    )

    print(
        "Zero-amount / dust events: "
        f"{zero_amount_events}"
    )

    duplicates = (
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM (
                SELECT
                    transaction_hash,
                    log_index,
                    COUNT(*) AS n

                FROM swaps

                GROUP BY
                    transaction_hash,
                    log_index

                HAVING n > 1
            )
            """
        )
        .fetchone()[0]
    )

    print(
        "Duplicate event IDs: "
        f"{duplicates}"
    )

    missing_timestamps = (
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM swaps
            WHERE block_timestamp IS NULL
            """
        )
        .fetchone()[0]
    )

    print(
        "Missing timestamps: "
        f"{missing_timestamps}"
    )

    checkpoints = (
        cursor.execute(
            """
            SELECT
                pool_address,
                last_processed_block
            FROM collector_state
            ORDER BY pool_address
            """
        )
        .fetchall()
    )

    print()
    print(
        "Collector checkpoints:"
    )

    for (
        pool,
        block,
    ) in checkpoints:

        print(
            f"  {pool}: "
            f"{block}"
        )

    connection.close()

    print()
    print(
        "=" * 72
    )

    if (
        invalid_signs == 0
        and duplicates == 0
        and missing_timestamps == 0
    ):

        print(
            "Validation result: PASS"
        )

    else:

        print(
            "Validation result: "
            "REVIEW REQUIRED"
        )

    print(
        "=" * 72
    )


if __name__ == "__main__":
    main()