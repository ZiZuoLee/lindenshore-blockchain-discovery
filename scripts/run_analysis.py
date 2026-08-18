import json

from src.analysis import run_analysis


def main() -> None:

    results = run_analysis()

    print()
    print(
        "=" * 70
    )

    print(
        "Lindenshore Blockchain "
        "Discovery Analysis"
    )

    print(
        "=" * 70
    )

    print()

    print(
        f"Total swaps: "
        f"{results['raw_swaps']:,}"
    )

    print(
        f"Cross-pool matches: "
        f"{results['matches']:,}"
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
        "Spread summary:"
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

    print()
    print(
        "Generated files are available "
        "in output/."
    )


if __name__ == "__main__":
    main()