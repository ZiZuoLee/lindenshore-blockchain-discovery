import logging
import time
from functools import lru_cache

from web3 import Web3

from src.config import (
    CHAIN_ID,
    MAX_RPC_RETRIES,
    RPC_URL,
)


logger = logging.getLogger(__name__)


def create_web3() -> Web3:
    """
    Create and validate a Web3 connection to Base.
    """
    w3 = Web3(
        Web3.HTTPProvider(
            RPC_URL,
            request_kwargs={
                "timeout": 30,
            },
        )
    )

    if not w3.is_connected():
        raise RuntimeError(
            f"Unable to connect to Base RPC: {RPC_URL}"
        )

    actual_chain_id = w3.eth.chain_id

    if actual_chain_id != CHAIN_ID:
        raise RuntimeError(
            f"Wrong network. Expected chain ID {CHAIN_ID}, "
            f"got {actual_chain_id}."
        )

    return w3


def rpc_call_with_retry(func, *args, **kwargs):
    """
    Execute an RPC call with exponential backoff.
    """
    last_exception = None

    for attempt in range(MAX_RPC_RETRIES):
        try:
            return func(*args, **kwargs)

        except Exception as exc:
            last_exception = exc

            wait_seconds = 2 ** attempt

            logger.warning(
                "RPC call failed. Attempt %s/%s. "
                "Retrying in %s seconds. Error: %s",
                attempt + 1,
                MAX_RPC_RETRIES,
                wait_seconds,
                exc,
            )

            time.sleep(wait_seconds)

    raise RuntimeError(
        "RPC call failed after "
        f"{MAX_RPC_RETRIES} attempts."
    ) from last_exception


@lru_cache(maxsize=4096)
def get_block_timestamp(
    w3: Web3,
    block_number: int,
) -> int:
    """
    Return a block's timestamp.

    Cached so repeated events in the same block do not
    trigger duplicate RPC requests.
    """
    block = rpc_call_with_retry(
        w3.eth.get_block,
        block_number,
    )

    return int(block["timestamp"])


def get_latest_block(w3: Web3) -> int:
    return int(
        rpc_call_with_retry(
            lambda: w3.eth.block_number
        )
    )