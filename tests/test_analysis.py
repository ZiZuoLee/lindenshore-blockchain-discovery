import pandas as pd

from src.analysis import (
    build_market_state,
)


def test_market_state_requires_two_pools():

    swaps = pd.DataFrame(
        [
            {
                "block_number": 1,
                "transaction_index": 0,
                "log_index": 0,
                "pool_address": "pool_a",
                "pool_price": 4000.0,
                "fee_tier": 500,
                "timestamp":
                    pd.Timestamp(
                        "2026-01-01",
                        tz="UTC",
                    ),
                "transaction_hash":
                    "0x1",
                "swap_usd": 1000.0,
            }
        ]
    )

    result = (
        build_market_state(
            swaps
        )
    )

    assert result.empty


def test_market_state_detects_spread():

    swaps = pd.DataFrame(
        [
            {
                "block_number": 1,
                "transaction_index": 0,
                "log_index": 0,
                "pool_address": "pool_a",
                "pool_price": 4000.0,
                "fee_tier": 500,
                "timestamp":
                    pd.Timestamp(
                        "2026-01-01",
                        tz="UTC",
                    ),
                "transaction_hash":
                    "0x1",
                "swap_usd": 1000.0,
            },
            {
                "block_number": 1,
                "transaction_index": 1,
                "log_index": 0,
                "pool_address": "pool_b",
                "pool_price": 4040.0,
                "fee_tier": 3000,
                "timestamp":
                    pd.Timestamp(
                        "2026-01-01",
                        tz="UTC",
                    ),
                "transaction_hash":
                    "0x2",
                "swap_usd": 2000.0,
            },
        ]
    )

    result = (
        build_market_state(
            swaps
        )
    )

    assert len(result) == 1

    row = result.iloc[0]

    assert round(
        row["spread_bps"],
        6,
    ) == 100.0

    assert round(
        row[
            "fee_adjusted_edge_bps"
        ],
        6,
    ) == 65.0

def test_market_state_only_compares_trigger_pool():

    swaps = pd.DataFrame(
        [
            {
                "block_number": 1,
                "transaction_index": 0,
                "log_index": 0,
                "pool_address": "pool_a",
                "pool_price": 4000.0,
                "fee_tier": 100,
                "timestamp":
                    pd.Timestamp(
                        "2026-01-01",
                        tz="UTC",
                    ),
                "transaction_hash":
                    "0x1",
                "swap_usd": 100.0,
            },
            {
                "block_number": 1,
                "transaction_index": 1,
                "log_index": 0,
                "pool_address": "pool_b",
                "pool_price": 4001.0,
                "fee_tier": 500,
                "timestamp":
                    pd.Timestamp(
                        "2026-01-01",
                        tz="UTC",
                    ),
                "transaction_hash":
                    "0x2",
                "swap_usd": 200.0,
            },
            {
                "block_number": 1,
                "transaction_index": 2,
                "log_index": 0,
                "pool_address": "pool_c",
                "pool_price": 4002.0,
                "fee_tier": 3000,
                "timestamp":
                    pd.Timestamp(
                        "2026-01-01",
                        tz="UTC",
                    ),
                "transaction_hash":
                    "0x3",
                "swap_usd": 300.0,
            },
            {
                "block_number": 1,
                "transaction_index": 3,
                "log_index": 0,
                "pool_address": "pool_a",
                "pool_price": 4010.0,
                "fee_tier": 100,
                "timestamp":
                    pd.Timestamp(
                        "2026-01-01",
                        tz="UTC",
                    ),
                "transaction_hash":
                    "0x4",
                "swap_usd": 400.0,
            },
        ]
    )

    result = build_market_state(
        swaps
    )

    last_trigger = result[
        result[
            "trigger_tx_hash"
        ] == "0x4"
    ]

    # pool_a changed, therefore it should
    # be compared with B and C only.
    assert len(
        last_trigger
    ) == 2

    for _, row in (
        last_trigger.iterrows()
    ):
        assert (
            row["pool_a"]
            == "pool_a"
            or row["pool_b"]
            == "pool_a"
        )

def test_market_state_ignores_stale_pool():

    swaps = pd.DataFrame(
        [
            {
                "block_number": 1,
                "transaction_index": 0,
                "log_index": 0,
                "pool_address": "pool_a",
                "pool_price": 4000.0,
                "fee_tier": 100,
                "timestamp":
                    pd.Timestamp(
                        "2026-01-01 00:00:00",
                        tz="UTC",
                    ),
                "transaction_hash":
                    "0x1",
                "swap_usd": 100.0,
            },

            {
                "block_number": 1,
                "transaction_index": 1,
                "log_index": 0,
                "pool_address": "pool_b",
                "pool_price": 4001.0,
                "fee_tier": 500,
                "timestamp":
                    pd.Timestamp(
                        "2026-01-01 00:00:01",
                        tz="UTC",
                    ),
                "transaction_hash":
                    "0x2",
                "swap_usd": 100.0,
            },

            {
                "block_number": 2,
                "transaction_index": 0,
                "log_index": 0,
                "pool_address": "pool_a",
                "pool_price": 4010.0,
                "fee_tier": 100,
                "timestamp":
                    pd.Timestamp(
                        "2026-01-01 00:02:00",
                        tz="UTC",
                    ),
                "transaction_hash":
                    "0x3",
                "swap_usd": 100.0,
            },
        ]
    )

    result = build_market_state(
        swaps
    )

    latest = result[
        result[
            "trigger_tx_hash"
        ] == "0x3"
    ]

    # pool_b's last observed state is
    # 119 seconds old, so it should not
    # be compared with pool_a.
    assert latest.empty