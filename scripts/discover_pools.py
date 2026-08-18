import logging

from src.database import (
    initialize_database,
)
from src.pools import (
    discover_and_load_pools,
)
from src.rpc import create_web3


logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s "
        "%(levelname)s "
        "%(message)s"
    ),
)


def main() -> None:

    initialize_database()

    w3 = create_web3()

    print(
        f"Connected to Base "
        f"(chain ID {w3.eth.chain_id})"
    )

    pools = discover_and_load_pools(
        w3
    )

    if not pools:
        raise RuntimeError(
            "No WETH/USDC Uniswap v3 "
            "pools were found."
        )

    print()
    print(
        "Discovered Uniswap v3 "
        "WETH/USDC pools:"
    )
    print()

    for pool in pools:

        print(
            f"Fee: "
            f"{pool.fee / 10000:.2f}%"
        )

        print(
            f"Pool: {pool.address}"
        )

        print(
            f"token0: "
            f"{pool.token0.symbol} "
            f"({pool.token0.address})"
        )

        print(
            f"token1: "
            f"{pool.token1.symbol} "
            f"({pool.token1.address})"
        )

        print(
            "-" * 60
        )


if __name__ == "__main__":
    main()