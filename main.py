import argparse
import logging

from src.analysis import run_analysis
from src.collector import (
    collect_pool_swaps,
)
from src.config import (
    DEFAULT_BLOCK_CHUNK_SIZE,
)
from src.database import (
    initialize_database,
)
from src.pools import (
    discover_and_load_pools,
)
from src.rpc import (
    create_web3,
    get_latest_block,
    rpc_call_with_retry,
)


logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s "
        "%(levelname)s "
        "%(message)s"
    ),
)


def get_timestamp(
    w3,
    block_number: int,
) -> int:

    block = rpc_call_with_retry(
        w3.eth.get_block,
        block_number,
    )

    return int(
        block["timestamp"]
    )


def find_start_block(
    w3,
    latest_block: int,
    target_timestamp: int,
) -> int:

    low = 0
    high = latest_block

    while low < high:

        mid = (
            low + high
        ) // 2

        timestamp = get_timestamp(
            w3,
            mid,
        )

        if timestamp < target_timestamp:
            low = mid + 1
        else:
            high = mid

    return low


def parse_arguments():

    parser = argparse.ArgumentParser(
        description=(
            "Base Uniswap v3 "
            "WETH/USDC discovery pipeline."
        )
    )

    parser.add_argument(
        "--days",
        type=float,
        default=1.0,
        help=(
            "Historical days to collect."
        ),
    )

    parser.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_BLOCK_CHUNK_SIZE,
    )

    return parser.parse_args()


def main() -> None:

    args = parse_arguments()

    initialize_database()

    print(
        "[1/4] Connecting to Base..."
    )

    w3 = create_web3()

    print(
        f"Connected. "
        f"Chain ID = "
        f"{w3.eth.chain_id}"
    )

    print()
    print(
        "[2/4] Discovering "
        "Uniswap v3 pools..."
    )

    pools = discover_and_load_pools(
        w3
    )

    for pool in pools:

        print(
            f"  {pool.fee / 10000:.2f}% "
            f"{pool.address}"
        )

    if not pools:
        raise RuntimeError(
            "No pools discovered."
        )

    print()
    print(
        "[3/4] Collecting Swap events..."
    )

    latest_block = get_latest_block(
        w3
    )

    latest_timestamp = get_timestamp(
        w3,
        latest_block,
    )

    target_timestamp = int(
        latest_timestamp
        - args.days * 86_400
    )

    start_block = find_start_block(
        w3,
        latest_block,
        target_timestamp,
    )

    print(
        f"Blocks "
        f"{start_block:,} -> "
        f"{latest_block:,}"
    )

    total = 0

    for pool in pools:

        inserted = collect_pool_swaps(
            w3=w3,
            pool=pool,
            start_block=start_block,
            end_block=latest_block,
            chunk_size=args.chunk_size,
            resume=True,
        )

        total += inserted

        print(
            f"  {pool.fee / 10000:.2f}%: "
            f"{inserted:,} new swaps"
        )

    print(
        f"Total new swaps: {total:,}"
    )

    print()
    print(
        "[4/4] Running analysis..."
    )

    results = run_analysis()

    print()
    print(
        "Analysis complete."
    )

    print(
        f"Swaps analyzed: "
        f"{results['raw_swaps']:,}"
    )

    print(
        f"Cross-pool matches: "
        f"{results['matches']:,}"
    )

    print()
    print(
        "Summary:"
    )

    for key, value in (
        results["summary"].items()
    ):

        if isinstance(
            value,
            float,
        ):
            print(
                f"  {key}: "
                f"{value:.4f}"
            )
        else:
            print(
                f"  {key}: {value}"
            )

    print()
    print(
        "Results written to output/."
    )


if __name__ == "__main__":
    main()