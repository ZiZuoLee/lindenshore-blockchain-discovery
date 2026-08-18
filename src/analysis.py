import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.config import (
    DISLOCATION_THRESHOLD_BPS,
    MAX_PRICE_MATCH_SECONDS,
    MAX_RECOVERY_SECONDS,
    OUTPUT_DIR,
    RECOVERY_THRESHOLD_BPS,
)
from src.database import (
    load_swaps_dataframe,
)
from src.pricing import (
    fee_adjusted_edge_bps,
    normalize_swap_dataframe,
)


def prepare_output_directory() -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


def build_cross_pool_matches(
    swaps: pd.DataFrame,
    max_match_seconds: int
    = MAX_PRICE_MATCH_SECONDS,
) -> pd.DataFrame:
    """
    Match each swap with the temporally nearest swap
    from another fee-tier pool.

    This produces observations of cross-pool prices
    close in time.
    """
    if swaps.empty:
        return pd.DataFrame()

    pools = sorted(
        swaps["pool_address"].unique()
    )

    if len(pools) < 2:
        return pd.DataFrame()

    matches = []

    for i in range(len(pools)):

        for j in range(i + 1, len(pools)):

            pool_a = pools[i]
            pool_b = pools[j]

            a = (
                swaps[
                    swaps["pool_address"]
                    == pool_a
                ]
                .sort_values("timestamp")
                .copy()
            )

            b = (
                swaps[
                    swaps["pool_address"]
                    == pool_b
                ]
                .sort_values("timestamp")
                .copy()
            )

            if a.empty or b.empty:
                continue

            a = a.rename(
                columns={
                    "pool_price":
                        "price_a",
                    "fee_tier":
                        "fee_a",
                    "swap_usd":
                        "swap_usd_a",
                    "transaction_hash":
                        "tx_hash_a",
                    "block_number":
                        "block_a",
                }
            )

            b = b.rename(
                columns={
                    "pool_price":
                        "price_b",
                    "fee_tier":
                        "fee_b",
                    "swap_usd":
                        "swap_usd_b",
                    "transaction_hash":
                        "tx_hash_b",
                    "block_number":
                        "block_b",
                }
            )

            matched = pd.merge_asof(
                a[
                    [
                        "timestamp",
                        "price_a",
                        "fee_a",
                        "swap_usd_a",
                        "tx_hash_a",
                        "block_a",
                    ]
                ],
                b[
                    [
                        "timestamp",
                        "price_b",
                        "fee_b",
                        "swap_usd_b",
                        "tx_hash_b",
                        "block_b",
                    ]
                ],
                on="timestamp",
                direction="nearest",
                tolerance=pd.Timedelta(
                    seconds=max_match_seconds
                ),
            )

            matched = matched.dropna(
                subset=["price_b"]
            )

            if matched.empty:
                continue

            matched["pool_a"] = pool_a
            matched["pool_b"] = pool_b

            matched["spread_bps"] = (
                np.abs(
                    matched["price_a"]
                    - matched["price_b"]
                )
                / np.minimum(
                    matched["price_a"],
                    matched["price_b"],
                )
                * 10_000
            )

            matched[
                "larger_swap_usd"
            ] = np.maximum(
                matched["swap_usd_a"],
                matched["swap_usd_b"],
            )

            net_edges = []
            routes = []

            for _, row in matched.iterrows():

                if (
                    row["price_a"]
                    < row["price_b"]
                ):
                    buy_price = row["price_a"]
                    sell_price = row["price_b"]

                    buy_fee = int(
                        row["fee_a"]
                    )

                    sell_fee = int(
                        row["fee_b"]
                    )

                    route = (
                        f"{pool_a} -> {pool_b}"
                    )

                else:
                    buy_price = row["price_b"]
                    sell_price = row["price_a"]

                    buy_fee = int(
                        row["fee_b"]
                    )

                    sell_fee = int(
                        row["fee_a"]
                    )

                    route = (
                        f"{pool_b} -> {pool_a}"
                    )

                net_edge = (
                    fee_adjusted_edge_bps(
                        buy_price,
                        sell_price,
                        buy_fee,
                        sell_fee,
                    )
                )

                net_edges.append(
                    net_edge
                )

                routes.append(
                    route
                )

            matched[
                "fee_adjusted_edge_bps"
            ] = net_edges

            matched[
                "candidate_route"
            ] = routes

            matches.append(
                matched
            )

    if not matches:
        return pd.DataFrame()

    result = pd.concat(
        matches,
        ignore_index=True,
    )

    result = (
        result
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    return result


def calculate_pool_activity(
    swaps: pd.DataFrame,
) -> pd.DataFrame:

    if swaps.empty:
        return pd.DataFrame()

    activity = (
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
            max_swap_usd=(
                "swap_usd",
                "max",
            ),
        )
        .reset_index()
    )

    return activity


def calculate_spread_summary(
    matches: pd.DataFrame,
) -> dict:

    if matches.empty:
        return {}

    spread = (
        matches["spread_bps"]
        .dropna()
    )

    return {
        "observations":
            int(len(spread)),

        "mean_spread_bps":
            float(spread.mean()),

        "median_spread_bps":
            float(spread.median()),

        "p95_spread_bps":
            float(
                spread.quantile(0.95)
            ),

        "p99_spread_bps":
            float(
                spread.quantile(0.99)
            ),

        "maximum_spread_bps":
            float(spread.max()),

        "dislocations_above_threshold":
            int(
                (
                    spread
                    >= DISLOCATION_THRESHOLD_BPS
                ).sum()
            ),

        "positive_fee_adjusted_edges":
            int(
                (
                    matches[
                        "fee_adjusted_edge_bps"
                    ]
                    > 0
                ).sum()
            ),
    }


def add_swap_size_buckets(
    matches: pd.DataFrame,
) -> pd.DataFrame:

    result = matches.copy()

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

    result["swap_size_bucket"] = (
        pd.cut(
            result["larger_swap_usd"],
            bins=bins,
            labels=labels,
            right=False,
        )
    )

    return result


def swap_size_analysis(
    matches: pd.DataFrame,
) -> pd.DataFrame:

    if matches.empty:
        return pd.DataFrame()

    temp = add_swap_size_buckets(
        matches
    )

    result = (
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
                    x.quantile(0.95),
            ),
        )
        .reset_index()
    )

    return result


def detect_recovery_events(
    matches: pd.DataFrame,
    dislocation_threshold:
        float = DISLOCATION_THRESHOLD_BPS,
    recovery_threshold:
        float = RECOVERY_THRESHOLD_BPS,
    max_recovery_seconds:
        int = MAX_RECOVERY_SECONDS,
) -> pd.DataFrame:
    """
    Find how long a detected price dislocation takes
    to return below recovery_threshold.

    This is an observational metric rather than proof
    that a specific arbitrageur caused convergence.
    """
    if matches.empty:
        return pd.DataFrame()

    matches = (
        matches
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    events = []

    previous_was_dislocated = False

    for i, row in matches.iterrows():

        currently_dislocated = (
            row["spread_bps"]
            >= dislocation_threshold
        )

        if (
            currently_dislocated
            and not previous_was_dislocated
        ):
            start_time = row["timestamp"]

            recovered = False

            for j in range(
                i + 1,
                len(matches),
            ):

                next_row = (
                    matches.iloc[j]
                )

                elapsed = (
                    next_row["timestamp"]
                    - start_time
                ).total_seconds()

                if (
                    elapsed
                    > max_recovery_seconds
                ):
                    break

                if (
                    next_row["spread_bps"]
                    <= recovery_threshold
                ):
                    events.append(
                        {
                            "start_time":
                                start_time,

                            "initial_spread_bps":
                                float(
                                    row[
                                        "spread_bps"
                                    ]
                                ),

                            "recovery_time":
                                next_row[
                                    "timestamp"
                                ],

                            "recovery_seconds":
                                float(elapsed),

                            "fee_adjusted_edge_bps":
                                float(
                                    row[
                                        "fee_adjusted_edge_bps"
                                    ]
                                ),
                        }
                    )

                    recovered = True
                    break

            if not recovered:
                events.append(
                    {
                        "start_time":
                            start_time,

                        "initial_spread_bps":
                            float(
                                row[
                                    "spread_bps"
                                ]
                            ),

                        "recovery_time":
                            pd.NaT,

                        "recovery_seconds":
                            np.nan,

                        "fee_adjusted_edge_bps":
                            float(
                                row[
                                    "fee_adjusted_edge_bps"
                                ]
                            ),
                    }
                )

        previous_was_dislocated = (
            currently_dislocated
        )

    return pd.DataFrame(events)


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
    ) in swaps.groupby("fee_tier"):

        group = group.sort_values(
            "timestamp"
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

    plt.xlabel("Time")
    plt.ylabel("USDC per WETH")

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
    matches: pd.DataFrame,
) -> None:

    if matches.empty:
        return

    usable = matches[
        "spread_bps"
    ].dropna()

    if usable.empty:
        return

    # Trim only extreme visualization outliers.
    upper = usable.quantile(0.99)

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
        "Cross-pool spread (basis points)"
    )

    plt.ylabel(
        "Observations"
    )

    plt.title(
        "Distribution of Cross-Pool "
        "WETH/USDC Price Dislocations"
    )

    plt.tight_layout()

    plt.savefig(
        OUTPUT_DIR
        / "02_spread_distribution.png",
        dpi=180,
    )

    plt.close()


def plot_swap_size_vs_spread(
    matches: pd.DataFrame,
) -> None:

    if matches.empty:
        return

    usable = matches[
        (
            matches[
                "larger_swap_usd"
            ] > 0
        )
        & (
            matches[
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
        usable["larger_swap_usd"],
        usable["spread_bps"],
        alpha=0.3,
        s=12,
    )

    plt.xscale("log")

    plt.xlabel(
        "Larger matched swap size "
        "(USD, log scale)"
    )

    plt.ylabel(
        "Cross-pool spread (bps)"
    )

    plt.title(
        "Swap Size vs Cross-Pool "
        "Price Dislocation"
    )

    plt.tight_layout()

    plt.savefig(
        OUTPUT_DIR
        / "03_swap_size_vs_spread.png",
        dpi=180,
    )

    plt.close()


def plot_recovery_times(
    recovery: pd.DataFrame,
) -> None:

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
        bins=40,
    )

    plt.xlabel(
        "Recovery time (seconds)"
    )

    plt.ylabel(
        "Dislocation events"
    )

    plt.title(
        "Time for Price Dislocations "
        "to Revert"
    )

    plt.tight_layout()

    plt.savefig(
        OUTPUT_DIR
        / "04_recovery_times.png",
        dpi=180,
    )

    plt.close()


def run_analysis() -> dict:

    prepare_output_directory()

    raw = load_swaps_dataframe()

    if raw.empty:
        raise RuntimeError(
            "No swaps found in database. "
            "Run collection first."
        )

    swaps = normalize_swap_dataframe(
        raw
    )

    matches = build_cross_pool_matches(
        swaps
    )

    activity = calculate_pool_activity(
        swaps
    )

    spread_summary = (
        calculate_spread_summary(
            matches
        )
    )

    size_analysis = (
        swap_size_analysis(
            matches
        )
    )

    recovery = detect_recovery_events(
        matches
    )

    activity.to_csv(
        OUTPUT_DIR
        / "pool_activity.csv",
        index=False,
    )

    swaps.to_csv(
        OUTPUT_DIR
        / "processed_swaps.csv",
        index=False,
    )

    matches.to_csv(
        OUTPUT_DIR
        / "cross_pool_matches.csv",
        index=False,
    )

    size_analysis.to_csv(
        OUTPUT_DIR
        / "swap_size_analysis.csv",
        index=False,
    )

    recovery.to_csv(
        OUTPUT_DIR
        / "recovery_events.csv",
        index=False,
    )

    if not recovery.empty:

        valid_recovery = recovery[
            "recovery_seconds"
        ].dropna()

        if not valid_recovery.empty:

            spread_summary[
                "median_recovery_seconds"
            ] = float(
                valid_recovery.median()
            )

            spread_summary[
                "p90_recovery_seconds"
            ] = float(
                valid_recovery.quantile(
                    0.90
                )
            )

            spread_summary[
                "recovered_event_count"
            ] = int(
                len(valid_recovery)
            )

    with open(
        OUTPUT_DIR
        / "summary.json",
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            spread_summary,
            file,
            indent=2,
        )

    plot_pool_prices(
        swaps
    )

    plot_spread_distribution(
        matches
    )

    plot_swap_size_vs_spread(
        matches
    )

    plot_recovery_times(
        recovery
    )

    return {
        "raw_swaps":
            len(raw),

        "pool_activity":
            activity,

        "matches":
            len(matches),

        "summary":
            spread_summary,

        "swap_size_analysis":
            size_analysis,

        "recovery":
            recovery,
    }