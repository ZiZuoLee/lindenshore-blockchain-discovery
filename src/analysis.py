import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.config import (
    DISLOCATION_THRESHOLD_BPS,
    MAX_RECOVERY_SECONDS,
    MAX_STATE_AGE_SECONDS,
    OUTPUT_DIR,
    RECOVERY_THRESHOLD_BPS,
)
from src.database import load_swaps_dataframe
from src.pricing import (
    fee_adjusted_edge_bps,
    normalize_swap_dataframe,
)


def prepare_output_directory() -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


def calculate_pool_activity(
    swaps: pd.DataFrame,
) -> pd.DataFrame:
    """
    Calculate basic trading statistics for each
    Uniswap v3 fee-tier pool.
    """
    if swaps.empty:
        return pd.DataFrame()

    return (
        swaps.groupby(
            [
                "pool_address",
                "fee_tier",
            ]
        )
        .agg(
            swaps=(
                "transaction_hash",
                "count",
            ),
            total_volume_usd=(
                "swap_usd",
                "sum",
            ),
            median_swap_usd=(
                "swap_usd",
                "median",
            ),
            mean_swap_usd=(
                "swap_usd",
                "mean",
            ),
            p95_swap_usd=(
                "swap_usd",
                lambda x: x.quantile(0.95),
            ),
            max_swap_usd=(
                "swap_usd",
                "max",
            ),
        )
        .reset_index()
        .sort_values("fee_tier")
    )


def build_market_state(
    swaps: pd.DataFrame,
) -> pd.DataFrame:
    """
    Reconstruct cross-pool market state after each Swap event.

    Events are processed in deterministic blockchain order:

        block_number
        transaction_index
        log_index

    After a pool changes, we compare ONLY the changed pool
    against every other pool whose latest state is already known.

    This avoids:
    - duplicating unchanged pool-pair observations
    - incorrectly associating an unrelated trigger swap with a pair
      that did not change
    """

    if swaps.empty:
        return pd.DataFrame()

    ordered = (
        swaps.sort_values(
            [
                "block_number",
                "transaction_index",
                "log_index",
            ]
        )
        .reset_index(drop=True)
    )

    latest_state = {}

    observations = []

    for _, row in ordered.iterrows():

        trigger_pool = row["pool_address"]

        latest_state[trigger_pool] = {
            "price": float(
                row["pool_price"]
            ),
            "fee_tier": int(
                row["fee_tier"]
            ),
            "block_number": int(
                row["block_number"]
            ),
            "transaction_index": int(
                row["transaction_index"]
            ),
            "log_index": int(
                row["log_index"]
            ),
            "timestamp": row[
                "timestamp"
            ],
            "tx_hash": row[
                "transaction_hash"
            ],
            "swap_usd": float(
                row["swap_usd"]
            ),
        }

        if len(latest_state) < 2:
            continue

        trigger_state = latest_state[
            trigger_pool
        ]

        for other_pool, other_state in (
            latest_state.items()
        ):

            if other_pool == trigger_pool:
                continue

            state_age_seconds = (
                row["timestamp"]
                - other_state["timestamp"]
            ).total_seconds()

            if (
                state_age_seconds < 0
                or
                state_age_seconds
                > MAX_STATE_AGE_SECONDS
            ):
                continue

            price_trigger = (
                trigger_state["price"]
            )

            price_other = (
                other_state["price"]
            )

            if (
                not np.isfinite(
                    price_trigger
                )
                or not np.isfinite(
                    price_other
                )
                or price_trigger <= 0
                or price_other <= 0
            ):
                continue

            # Canonical ordering avoids storing
            # A/B and B/A as different pair identities.
            if trigger_pool < other_pool:

                pool_a = trigger_pool
                pool_b = other_pool

                price_a = price_trigger
                price_b = price_other

                fee_a = (
                    trigger_state[
                        "fee_tier"
                    ]
                )

                fee_b = (
                    other_state[
                        "fee_tier"
                    ]
                )

            else:

                pool_a = other_pool
                pool_b = trigger_pool

                price_a = price_other
                price_b = price_trigger

                fee_a = (
                    other_state[
                        "fee_tier"
                    ]
                )

                fee_b = (
                    trigger_state[
                        "fee_tier"
                    ]
                )

            spread = (
                abs(
                    price_a
                    - price_b
                )
                / min(
                    price_a,
                    price_b,
                )
                * 10_000
            )

            if price_a < price_b:

                buy_pool = pool_a
                sell_pool = pool_b

                buy_price = price_a
                sell_price = price_b

                buy_fee = fee_a
                sell_fee = fee_b

            else:

                buy_pool = pool_b
                sell_pool = pool_a

                buy_price = price_b
                sell_price = price_a

                buy_fee = fee_b
                sell_fee = fee_a

            net_edge = (
                fee_adjusted_edge_bps(
                    buy_price=
                        buy_price,
                    sell_price=
                        sell_price,
                    buy_fee_tier=
                        buy_fee,
                    sell_fee_tier=
                        sell_fee,
                )
            )

            observations.append(
                {
                    "timestamp":
                        row[
                            "timestamp"
                        ],

                    "block_number":
                        int(
                            row[
                                "block_number"
                            ]
                        ),

                    "transaction_index":
                        int(
                            row[
                                "transaction_index"
                            ]
                        ),

                    "log_index":
                        int(
                            row[
                                "log_index"
                            ]
                        ),
                    "other_state_age_seconds":
                        float(
                            state_age_seconds
                        ),

                    "trigger_pool":
                        trigger_pool,

                    "trigger_fee_tier":
                        int(
                            row[
                                "fee_tier"
                            ]
                        ),

                    "trigger_tx_hash":
                        row[
                            "transaction_hash"
                        ],

                    "trigger_swap_usd":
                        float(
                            row[
                                "swap_usd"
                            ]
                        ),

                    "pool_a":
                        pool_a,

                    "pool_b":
                        pool_b,

                    "price_a":
                        price_a,

                    "price_b":
                        price_b,

                    "fee_a":
                        fee_a,

                    "fee_b":
                        fee_b,

                    "spread_bps":
                        spread,

                    "buy_pool":
                        buy_pool,

                    "sell_pool":
                        sell_pool,

                    "buy_price":
                        buy_price,

                    "sell_price":
                        sell_price,

                    "fee_adjusted_edge_bps":
                        net_edge,
                }
            )

    if not observations:
        return pd.DataFrame()

    return (
        pd.DataFrame(
            observations
        )
        .sort_values(
            [
                "block_number",
                "transaction_index",
                "log_index",
            ]
        )
        .reset_index(drop=True)
    )

def calculate_spread_summary(
    market_state: pd.DataFrame,
) -> dict:
    """
    Summarize cross-pool price dislocations.
    """

    if market_state.empty:
        return {}

    spread = (
        market_state[
            "spread_bps"
        ]
        .dropna()
    )

    net_edges = (
        market_state[
            "fee_adjusted_edge_bps"
        ]
        .dropna()
    )

    return {
        "observations":
            int(
                len(spread)
            ),

        "mean_spread_bps":
            float(
                spread.mean()
            ),

        "median_spread_bps":
            float(
                spread.median()
            ),

        "p95_spread_bps":
            float(
                spread.quantile(
                    0.95
                )
            ),

        "p99_spread_bps":
            float(
                spread.quantile(
                    0.99
                )
            ),

        "maximum_spread_bps":
            float(
                spread.max()
            ),

        "dislocations_above_threshold":
            int(
                (
                    spread
                    >=
                    DISLOCATION_THRESHOLD_BPS
                ).sum()
            ),

        "positive_fee_adjusted_edges":
            int(
                (
                    net_edges
                    > 0
                ).sum()
            ),

        "positive_fee_adjusted_percentage":
            float(
                (
                    net_edges
                    > 0
                ).mean()
                * 100
            ),
    }


def add_swap_size_buckets(
    market_state: pd.DataFrame,
) -> pd.DataFrame:

    result = (
        market_state.copy()
    )

    bins = [
        0,
        1_000,
        10_000,
        100_000,
        np.inf,
    ]

    labels = [
        "<$1k",
        "$1k-$10k",
        "$10k-$100k",
        "$100k+",
    ]

    result[
        "swap_size_bucket"
    ] = pd.cut(
        result[
            "trigger_swap_usd"
        ],
        bins=bins,
        labels=labels,
        right=False,
    )

    return result


def swap_size_analysis(
    market_state: pd.DataFrame,
) -> pd.DataFrame:

    if market_state.empty:
        return pd.DataFrame()

    temp = (
        add_swap_size_buckets(
            market_state
        )
    )

    return (
        temp.groupby(
            "swap_size_bucket",
            observed=False,
        )
        .agg(
            observations=(
                "spread_bps",
                "count",
            ),

            median_spread_bps=(
                "spread_bps",
                "median",
            ),

            mean_spread_bps=(
                "spread_bps",
                "mean",
            ),

            p95_spread_bps=(
                "spread_bps",
                lambda x:
                    x.quantile(
                        0.95
                    ),
            ),
        )
        .reset_index()
    )


def detect_dislocation_events(
    market_state: pd.DataFrame,
) -> pd.DataFrame:
    """
    Detect the beginning of cross-pool dislocations.

    Consecutive observations involving the same pair
    above the threshold are treated as one episode.
    """

    if market_state.empty:
        return pd.DataFrame()

    ordered = (
        market_state
        .sort_values(
            [
                "block_number",
                "transaction_index",
                "log_index",
            ]
        )
        .reset_index(drop=True)
    )

    active_pairs = {}

    events = []

    for _, row in ordered.iterrows():

        pair = tuple(
            sorted(
                [
                    row["pool_a"],
                    row["pool_b"],
                ]
            )
        )

        dislocated = (
            row["spread_bps"]
            >=
            DISLOCATION_THRESHOLD_BPS
        )

        was_dislocated = (
            active_pairs.get(
                pair,
                False,
            )
        )

        if (
            dislocated
            and not
            was_dislocated
        ):

            events.append(
                {
                    "timestamp":
                        row[
                            "timestamp"
                        ],

                    "block_number":
                        row[
                            "block_number"
                        ],

                    "transaction_index":
                        row[
                            "transaction_index"
                        ],

                    "log_index":
                        row[
                            "log_index"
                        ],

                    "pool_a":
                        row[
                            "pool_a"
                        ],

                    "pool_b":
                        row[
                            "pool_b"
                        ],

                    "trigger_pool":
                        row[
                            "trigger_pool"
                        ],

                    "trigger_tx_hash":
                        row[
                            "trigger_tx_hash"
                        ],

                    "trigger_swap_usd":
                        row[
                            "trigger_swap_usd"
                        ],

                    "initial_spread_bps":
                        row[
                            "spread_bps"
                        ],

                    "fee_adjusted_edge_bps":
                        row[
                            "fee_adjusted_edge_bps"
                        ],
                }
            )

        active_pairs[pair] = (
            dislocated
        )

    return pd.DataFrame(
        events
    )


def detect_recovery_events(
    market_state: pd.DataFrame,
) -> pd.DataFrame:
    """
    For every detected dislocation episode, find the
    first subsequent observation for the same pool pair
    where the spread falls below the recovery threshold.
    """

    dislocations = (
        detect_dislocation_events(
            market_state
        )
    )

    if dislocations.empty:
        return pd.DataFrame()

    ordered = (
        market_state
        .sort_values(
            [
                "block_number",
                "transaction_index",
                "log_index",
            ]
        )
        .reset_index(drop=True)
    )

    results = []

    for _, event in (
        dislocations.iterrows()
    ):

        pair = {
            event["pool_a"],
            event["pool_b"],
        }

        start_time = (
            event["timestamp"]
        )

        candidates = ordered[
            (
                ordered["timestamp"]
                >= start_time
            )
        ]

        recovery_time = pd.NaT
        recovery_seconds = np.nan

        for _, row in (
            candidates.iterrows()
        ):

            row_pair = {
                row["pool_a"],
                row["pool_b"],
            }

            if row_pair != pair:
                continue

            elapsed = (
                row["timestamp"]
                - start_time
            ).total_seconds()

            if elapsed < 0:
                continue

            if (
                elapsed
                >
                MAX_RECOVERY_SECONDS
            ):
                break

            if (
                row["spread_bps"]
                <=
                RECOVERY_THRESHOLD_BPS
            ):

                recovery_time = (
                    row[
                        "timestamp"
                    ]
                )

                recovery_seconds = (
                    float(elapsed)
                )

                break

        results.append(
            {
                **event.to_dict(),

                "recovery_time":
                    recovery_time,

                "recovery_seconds":
                    recovery_seconds,
            }
        )

    return pd.DataFrame(
        results
    )


def identify_candidate_arbitrage_events(
    market_state: pd.DataFrame,
) -> pd.DataFrame:
    """
    Extract observations where the cross-pool edge
    remains positive after accounting for both
    Uniswap pool fees.

    These are only candidate signals, not guaranteed
    executable arbitrage opportunities.
    """

    if market_state.empty:
        return pd.DataFrame()

    candidates = market_state[
        market_state[
            "fee_adjusted_edge_bps"
        ] > 0
    ].copy()

    return (
        candidates
        .sort_values(
            "fee_adjusted_edge_bps",
            ascending=False,
        )
        .reset_index(drop=True)
    )


def plot_pool_prices(
    swaps: pd.DataFrame,
) -> None:

    if swaps.empty:
        return

    plt.figure(
        figsize=(12, 6)
    )

    for (
        fee_tier,
        group
    ) in swaps.groupby(
        "fee_tier"
    ):

        group = (
            group.sort_values(
                "timestamp"
            )
        )

        plt.plot(
            group["timestamp"],
            group["pool_price"],
            label=(
                f"{fee_tier / 10000:.2f}%"
            ),
            linewidth=1,
            alpha=0.8,
        )

    plt.xlabel(
        "Time"
    )

    plt.ylabel(
        "USDC per WETH"
    )

    plt.title(
        "Uniswap v3 WETH/USDC "
        "Pool Prices on Base"
    )

    plt.legend(
        title="Fee tier"
    )

    plt.tight_layout()

    plt.savefig(
        OUTPUT_DIR
        / "01_pool_prices.png",
        dpi=180,
    )

    plt.close()


def plot_spread_distribution(
    market_state: pd.DataFrame,
) -> None:

    if market_state.empty:
        return

    usable = (
        market_state[
            "spread_bps"
        ]
        .dropna()
    )

    if usable.empty:
        return

    upper = (
        usable.quantile(
            0.99
        )
    )

    displayed = usable[
        usable <= upper
    ]

    plt.figure(
        figsize=(10, 6)
    )

    plt.hist(
        displayed,
        bins=60,
    )

    plt.xlabel(
        "Cross-pool spread "
        "(basis points)"
    )

    plt.ylabel(
        "Market-state observations"
    )

    plt.title(
        "Distribution of Cross-Pool "
        "WETH/USDC Price Dislocations"
    )

    plt.tight_layout()

    plt.savefig(
        OUTPUT_DIR
        /
        "02_spread_distribution.png",
        dpi=180,
    )

    plt.close()


def plot_swap_size_vs_spread(
    market_state: pd.DataFrame,
) -> None:

    if market_state.empty:
        return

    usable = market_state[
        (
            market_state[
                "trigger_swap_usd"
            ] > 0
        )
        &
        (
            market_state[
                "spread_bps"
            ].notna()
        )
    ]

    if usable.empty:
        return

    plt.figure(
        figsize=(10, 6)
    )

    plt.scatter(
        usable[
            "trigger_swap_usd"
        ],
        usable[
            "spread_bps"
        ],
        alpha=0.25,
        s=12,
    )

    plt.xscale(
        "log"
    )

    plt.xlabel(
        "Trigger swap size "
        "(USD, log scale)"
    )

    plt.ylabel(
        "Cross-pool spread "
        "(bps)"
    )

    plt.title(
        "Trigger Swap Size vs "
        "Cross-Pool Price Dislocation"
    )

    plt.tight_layout()

    plt.savefig(
        OUTPUT_DIR
        /
        "03_swap_size_vs_spread.png",
        dpi=180,
    )

    plt.close()


def plot_recovery_times(
    recovery: pd.DataFrame,
) -> None:

    output_path = (
        OUTPUT_DIR
        / "04_recovery_times.png"
    )

    # Remove stale chart from an earlier run.
    if output_path.exists():
        output_path.unlink()

    if recovery.empty:
        return

    usable = (
        recovery[
            "recovery_seconds"
        ]
        .dropna()
    )

    if usable.empty:
        return

    plt.figure(
        figsize=(10, 6)
    )

    plt.hist(
        usable,
        bins=min(
            40,
            max(
                5,
                len(
                    usable.unique()
                )
                * 2,
            ),
        ),
    )

    plt.xlabel(
        "Recovery time "
        "(seconds)"
    )

    plt.ylabel(
        "Dislocation episodes"
    )

    plt.title(
        "Time for Cross-Pool "
        "Price Dislocations to Recover"
    )

    plt.tight_layout()

    plt.savefig(
        output_path,
        dpi=180,
    )

    plt.close()


def run_analysis() -> dict:

    prepare_output_directory()

    raw = (
        load_swaps_dataframe()
    )

    if raw.empty:
        raise RuntimeError(
            "No swaps found in database. "
            "Run collection first."
        )

    swaps = (
        normalize_swap_dataframe(
            raw
        )
    )

    market_state = (
        build_market_state(
            swaps
        )
    )

    activity = (
        calculate_pool_activity(
            swaps
        )
    )

    summary = (
        calculate_spread_summary(
            market_state
        )
    )

    size_analysis = (
        swap_size_analysis(
            market_state
        )
    )

    recovery = (
        detect_recovery_events(
            market_state
        )
    )

    arbitrage_candidates = (
        identify_candidate_arbitrage_events(
            market_state
        )
    )

    if not recovery.empty:

        usable_recovery = (
            recovery[
                "recovery_seconds"
            ]
            .dropna()
        )

        summary[
            "dislocation_episodes"
        ] = int(
            len(recovery)
        )

        summary[
            "recovered_event_count"
        ] = int(
            len(
                usable_recovery
            )
        )

        if not usable_recovery.empty:

            summary[
                "median_recovery_seconds"
            ] = float(
                usable_recovery.median()
            )

            summary[
                "p90_recovery_seconds"
            ] = float(
                usable_recovery.quantile(
                    0.90
                )
            )

    activity.to_csv(
        OUTPUT_DIR
        /
        "pool_activity.csv",
        index=False,
    )

    swaps.to_csv(
        OUTPUT_DIR
        /
        "processed_swaps.csv",
        index=False,
    )

    market_state.to_csv(
        OUTPUT_DIR
        /
        "market_state.csv",
        index=False,
    )

    size_analysis.to_csv(
        OUTPUT_DIR
        /
        "swap_size_analysis.csv",
        index=False,
    )

    recovery.to_csv(
        OUTPUT_DIR
        /
        "recovery_events.csv",
        index=False,
    )

    arbitrage_candidates.to_csv(
        OUTPUT_DIR
        /
        "arbitrage_candidates.csv",
        index=False,
    )

    with open(
        OUTPUT_DIR
        /
        "summary.json",
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            summary,
            file,
            indent=2,
        )

    plot_pool_prices(
        swaps
    )

    plot_spread_distribution(
        market_state
    )

    plot_swap_size_vs_spread(
        market_state
    )

    plot_recovery_times(
        recovery
    )

    return {
        "raw_swaps":
            len(raw),

        "market_state_observations":
            len(
                market_state
            ),

        "pool_activity":
            activity,

        "summary":
            summary,

        "swap_size_analysis":
            size_analysis,

        "recovery":
            recovery,

        "arbitrage_candidates":
            arbitrage_candidates,
    }