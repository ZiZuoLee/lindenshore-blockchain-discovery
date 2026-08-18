import argparse
import logging
import time

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


logger = logging.getLogger(__name__)


def get_block_timestamp_uncached(
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


def find_block_at_or_after_timestamp(
    w3,
    target_timestamp: int,
    low: int,
    high: int,
) -> int:
    """
    Binary search for the first block whose
    timestamp is >= target_timestamp.
    """
    while low < high:

        mid = (
            low + high
        ) // 2

        timestamp = (
            get_block_timestamp_uncached(
                w3,
                mid,
            )
        )

        if timestamp < target_timestamp:
            low = mid + 1
        else:
            high = mid

    return low


def parse_arguments():

    parser = argparse.ArgumentParser(
        description=(
            "Collect Uniswap v3 WETH/USDC "
            "Swap events from Base."
        )
    )

    parser.add_argument(
        "--days",
        type=float,
        default=1.0,
        help=(
            "Number of historical days "
            "to collect. Default: 1."
        ),
    )

    parser.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_BLOCK_CHUNK_SIZE,
        help=(
            "eth_getLogs block chunk size. "
            "Default: 500."
        ),
    )

    parser.add_argument(
        "--no-resume",
        action="store_true",
        help=(
            "Ignore collector checkpoints."
        ),
    )

    return parser.parse_args()


def main() -> None:

    args = parse_arguments()

    if args.days <= 0:
        raise ValueError(
            "--days must be positive."
        )

    if args.chunk_size <= 0:
        raise ValueError(
            "--chunk-size must be positive."
        )

    initialize_database()

    w3 = create_web3()

    latest_block = get_latest_block(
        w3
    )

    latest_timestamp = (
        get_block_timestamp_uncached(
            w3,
            latest_block,
        )
    )

    target_timestamp = int(
        latest_timestamp
        - args.days * 86_400
    )

    logger.info(
        "Finding block approximately "
        "%.2f days ago...",
        args.days,
    )

    start_block = (
        find_block_at_or_after_timestamp(
            w3,
            target_timestamp,
            0,
            latest_block,
        )
    )

    print()
    print(
        f"Collection range:"
    )

    print(
        f"  Start block: {start_block}"
    )

    print(
        f"  End block:   {latest_block}"
    )

    print(
        f"  Days:        {args.days}"
    )

    print()

    pools = discover_and_load_pools(
        w3
    )

    if len(pools) < 2:

        print(
            "WARNING: fewer than two "
            "WETH/USDC pools found."
        )

        print(
            "Cross-pool analysis requires "
            "at least two active pools."
        )

    total_inserted = 0

    for pool in pools:

        print()
        print(
            "=" * 70
        )

        print(
            f"Collecting "
            f"{pool.token0.symbol}/"
            f"{pool.token1.symbol}"
        )

        print(
            f"Fee tier: "
            f"{pool.fee / 10000:.2f}%"
        )

        print(
            f"Pool: {pool.address}"
        )

        inserted = collect_pool_swaps(
            w3=w3,
            pool=pool,
            start_block=start_block,
            end_block=latest_block,
            chunk_size=args.chunk_size,
            resume=not args.no_resume,
        )

        total_inserted += inserted

        print(
            f"New swaps inserted: "
            f"{inserted}"
        )

    print()
    print(
        "=" * 70
    )

    print(
        f"Collection complete. "
        f"New swaps inserted: "
        f"{total_inserted}"
    )


if __name__ == "__main__":
    main()