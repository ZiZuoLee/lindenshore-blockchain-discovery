import json

from src.analysis import (
    run_analysis,
)


def main() -> None:

    results = (
        run_analysis()
    )

    print()
    print(
        "=" * 72
    )

    print(
        "Lindenshore Blockchain "
        "Discovery Analysis"
    )

    print(
        "=" * 72
    )

    print()

    print(
        f"Total swaps: "
        f"{results['raw_swaps']:,}"
    )

    print(
        "Market-state observations: "
        f"{results['market_state_observations']:,}"
    )

    print()

    print(
        "Pool activity:"
    )

    print(
        results[
            "pool_activity"
        ].to_string(
            index=False
        )
    )

    print()
    print(
        "Spread / arbitrage summary:"
    )

    print(
        json.dumps(
            results["summary"],
            indent=2,
        )
    )

    print()
    print(
        "Swap-size analysis:"
    )

    print(
        results[
            "swap_size_analysis"
        ].to_string(
            index=False
        )
    )

    candidates = results[
        "arbitrage_candidates"
    ]

    print()
    print(
        "Fee-adjusted candidate "
        "arbitrage observations: "
        f"{len(candidates):,}"
    )

    if not candidates.empty:

        print()
        print(
            "Top candidate signals:"
        )

        columns = [
            "timestamp",
            "block_number",
            "buy_price",
            "sell_price",
            "fee_adjusted_edge_bps",
            "trigger_swap_usd",
        ]

        print(
            candidates[
                columns
            ]
            .head(10)
            .to_string(
                index=False
            )
        )

    print()
    print(
        "Generated files are "
        "available in output/."
    )


if __name__ == "__main__":
    main()