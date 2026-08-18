from pathlib import Path
import os

from dotenv import load_dotenv
from web3 import Web3


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


RPC_URL = os.getenv("BASE_RPC_URL", "https://mainnet.base.org")

CHAIN_NAME = "base"
CHAIN_ID = 8453


UNISWAP_V3_FACTORY = Web3.to_checksum_address(
    "0x33128a8fC17869897dcE68Ed026d694621f6FDfD"
)

WETH_ADDRESS = Web3.to_checksum_address(
    "0x4200000000000000000000000000000000000006"
)

USDC_ADDRESS = Web3.to_checksum_address(
    "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
)


# Uniswap v3 fee tiers
FEE_TIERS = [
    100,     # 0.01%
    500,     # 0.05%
    3000,    # 0.30%
    10000,   # 1.00%
]


DATABASE_PATH = PROJECT_ROOT / "data" / "blockchain.db"
OUTPUT_DIR = PROJECT_ROOT / "output"

DEFAULT_BLOCK_CHUNK_SIZE = 500

MAX_RPC_RETRIES = 5

DEFAULT_COLLECTION_DAYS = 1


# Analysis configuration
MAX_PRICE_MATCH_SECONDS = 10
DISLOCATION_THRESHOLD_BPS = 20.0
RECOVERY_THRESHOLD_BPS = 5.0
MAX_RECOVERY_SECONDS = 300