from dataclasses import dataclass

from web3 import Web3

from src.abis import ERC20_ABI
from src.database import upsert_token
from src.rpc import rpc_call_with_retry


@dataclass(frozen=True)
class TokenMetadata:
    address: str
    symbol: str
    decimals: int


def get_token_metadata(
    w3: Web3,
    token_address: str,
) -> TokenMetadata:

    checksum_address = Web3.to_checksum_address(
        token_address
    )

    contract = w3.eth.contract(
        address=checksum_address,
        abi=ERC20_ABI,
    )

    symbol = rpc_call_with_retry(
        contract.functions.symbol().call
    )

    decimals = rpc_call_with_retry(
        contract.functions.decimals().call
    )

    metadata = TokenMetadata(
        address=checksum_address,
        symbol=str(symbol),
        decimals=int(decimals),
    )

    upsert_token(
        address=metadata.address,
        symbol=metadata.symbol,
        decimals=metadata.decimals,
    )

    return metadata