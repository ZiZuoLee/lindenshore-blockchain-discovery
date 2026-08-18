import logging
from typing import Iterable

from web3 import Web3
from web3._utils.events import get_event_data

from src.abis import POOL_ABI
from src.config import (
    CHAIN_NAME,
    DEFAULT_BLOCK_CHUNK_SIZE,
)
from src.database import (
    get_last_processed_block,
    insert_swap,
    set_last_processed_block,
)
from src.pools import PoolMetadata
from src.rpc import (
    get_block_timestamp,
    rpc_call_with_retry,
)


logger = logging.getLogger(__name__)


def get_swap_event_abi() -> dict:
    for item in POOL_ABI:
        if (
            item.get("type") == "event"
            and item.get("name") == "Swap"
        ):
            return item

    raise RuntimeError(
        "Swap event ABI not found."
    )


SWAP_EVENT_ABI = get_swap_event_abi()


def get_swap_topic(w3: Web3) -> str:
    """
    Compute event topic:
    keccak(
        "Swap(address,address,int256,int256,"
        "uint160,uint128,int24)"
    )
    """
    signature = (
        "Swap(address,address,int256,int256,"
        "uint160,uint128,int24)"
    )

    return w3.keccak(
        text=signature
    ).hex()


def decode_swap_log(
    w3: Web3,
    raw_log,
    pool: PoolMetadata,
) -> dict:

    decoded = get_event_data(
        w3.codec,
        SWAP_EVENT_ABI,
        raw_log,
    )

    args = decoded["args"]

    block_number = int(
        decoded["blockNumber"]
    )

    return {
        "chain": CHAIN_NAME,

        "block_number": block_number,

        "block_timestamp":
            get_block_timestamp(
                w3,
                block_number,
            ),

        "transaction_hash":
            decoded["transactionHash"].hex(),

        "transaction_index":
            int(decoded["transactionIndex"]),

        "log_index":
            int(decoded["logIndex"]),

        "pool_address":
            pool.address,

        "fee_tier":
            pool.fee,

        "sender":
            args["sender"],

        "recipient":
            args["recipient"],

        "amount0_raw":
            int(args["amount0"]),

        "amount1_raw":
            int(args["amount1"]),

        "sqrt_price_x96":
            int(args["sqrtPriceX96"]),

        "liquidity":
            int(args["liquidity"]),

        "tick":
            int(args["tick"]),
    }


def get_logs_for_range(
    w3: Web3,
    pool_address: str,
    from_block: int,
    to_block: int,
):
    """
    Fetch Swap logs for one pool over a block range.
    """
    topic = get_swap_topic(w3)

    return rpc_call_with_retry(
        w3.eth.get_logs,
        {
            "address":
                Web3.to_checksum_address(
                    pool_address
                ),

            "fromBlock":
                from_block,

            "toBlock":
                to_block,

            "topics":
                [topic],
        },
    )


def chunk_block_range(
    start_block: int,
    end_block: int,
    chunk_size: int,
) -> Iterable[tuple[int, int]]:

    current = start_block

    while current <= end_block:

        chunk_end = min(
            current + chunk_size - 1,
            end_block,
        )

        yield current, chunk_end

        current = chunk_end + 1


def collect_pool_swaps(
    w3: Web3,
    pool: PoolMetadata,
    start_block: int,
    end_block: int,
    chunk_size: int = DEFAULT_BLOCK_CHUNK_SIZE,
    resume: bool = True,
) -> int:
    """
    Collect and store Swap events for a single pool.

    Returns number of newly inserted swaps.
    """
    if end_block < start_block:
        raise ValueError(
            "end_block must be >= start_block"
        )

    actual_start = start_block

    if resume:
        last_processed = (
            get_last_processed_block(
                pool.address
            )
        )

        if last_processed is not None:
            actual_start = max(
                actual_start,
                last_processed + 1,
            )

    if actual_start > end_block:

        logger.info(
            "Pool %s is already processed "
            "through block %s.",
            pool.address,
            end_block,
        )

        return 0

    inserted_count = 0

    for chunk_start, chunk_end in chunk_block_range(
        actual_start,
        end_block,
        chunk_size,
    ):

        logger.info(
            "Collecting pool=%s fee=%s "
            "blocks=%s-%s",
            pool.address,
            pool.fee,
            chunk_start,
            chunk_end,
        )

        try:
            logs = get_logs_for_range(
                w3,
                pool.address,
                chunk_start,
                chunk_end,
            )

        except Exception as exc:
            raise RuntimeError(
                "Failed to collect logs for "
                f"{pool.address} between "
                f"{chunk_start}-{chunk_end}."
            ) from exc

        chunk_inserted = 0

        for raw_log in logs:

            swap = decode_swap_log(
                w3,
                raw_log,
                pool,
            )

            if insert_swap(swap):
                inserted_count += 1
                chunk_inserted += 1

        # We only checkpoint after the
        # entire chunk succeeded.
        set_last_processed_block(
            pool.address,
            chunk_end,
        )

        logger.info(
            "Finished blocks %s-%s. "
            "RPC logs=%s, new rows=%s",
            chunk_start,
            chunk_end,
            len(logs),
            chunk_inserted,
        )

    return inserted_count