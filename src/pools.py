from dataclasses import dataclass

from web3 import Web3

from src.abis import (
    FACTORY_ABI,
    POOL_ABI,
)
from src.config import (
    FEE_TIERS,
    UNISWAP_V3_FACTORY,
    USDC_ADDRESS,
    WETH_ADDRESS,
)
from src.database import upsert_pool
from src.rpc import rpc_call_with_retry
from src.tokens import (
    TokenMetadata,
    get_token_metadata,
)


ZERO_ADDRESS = (
    "0x0000000000000000000000000000000000000000"
)


@dataclass(frozen=True)
class PoolMetadata:
    address: str
    fee: int
    token0: TokenMetadata
    token1: TokenMetadata


def discover_pool_addresses(
    w3: Web3,
) -> list[tuple[int, str]]:

    factory = w3.eth.contract(
        address=UNISWAP_V3_FACTORY,
        abi=FACTORY_ABI,
    )

    discovered = []

    for fee in FEE_TIERS:

        pool_address = rpc_call_with_retry(
            factory.functions.getPool(
                WETH_ADDRESS,
                USDC_ADDRESS,
                fee,
            ).call
        )

        if (
            pool_address
            and pool_address.lower()
            != ZERO_ADDRESS.lower()
        ):
            discovered.append(
                (
                    fee,
                    Web3.to_checksum_address(
                        pool_address
                    ),
                )
            )

    return discovered


def load_pool_metadata(
    w3: Web3,
    pool_address: str,
) -> PoolMetadata:

    checksum_pool = Web3.to_checksum_address(
        pool_address
    )

    contract = w3.eth.contract(
        address=checksum_pool,
        abi=POOL_ABI,
    )

    token0_address = rpc_call_with_retry(
        contract.functions.token0().call
    )

    token1_address = rpc_call_with_retry(
        contract.functions.token1().call
    )

    fee = int(
        rpc_call_with_retry(
            contract.functions.fee().call
        )
    )

    token0 = get_token_metadata(
        w3,
        token0_address,
    )

    token1 = get_token_metadata(
        w3,
        token1_address,
    )

    upsert_pool(
        address=checksum_pool,
        token0=token0.address,
        token1=token1.address,
        fee=fee,
    )

    return PoolMetadata(
        address=checksum_pool,
        fee=fee,
        token0=token0,
        token1=token1,
    )


def discover_and_load_pools(
    w3: Web3,
) -> list[PoolMetadata]:

    pools = []

    for _, address in discover_pool_addresses(w3):

        pool = load_pool_metadata(
            w3,
            address,
        )

        pools.append(pool)

    return pools