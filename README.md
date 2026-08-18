# Base Uniswap v3 Price Dislocation Analysis

A blockchain data-discovery project analyzing temporary price differences between Uniswap v3 WETH/USDC liquidity pools on Base.

This project was developed for the **Lindenshore Technical Assessment: Blockchain Data Discovery**.

---

## TL;DR

I collected **13,780 Uniswap v3 WETH/USDC Swap events** directly from Base using JSON-RPC and reconstructed **27,215 recent cross-pool market-state observations**.

The median observed cross-pool price difference was **4.33 basis points**, but only **8 observations (0.029%)** remained positive after accounting for both Uniswap liquidity-provider fees.

Trades above approximately **$10,000** were associated with much larger cross-pool price dislocations than smaller trades in this sample.

The main conclusion is:

> **Raw DEX price differences substantially overstate economically meaningful arbitrage opportunities.**

---

## Research Question

Uniswap v3 allows multiple independent liquidity pools for the same token pair, each with a different fee tier.

For WETH/USDC, these pools can temporarily disagree on price because:

1. each pool has separate liquidity,
2. each pool has separate state,
3. a large trade can move one pool more than another,
4. arbitrageurs can subsequently trade against the discrepancy.

This project investigates:

1. Which WETH/USDC Uniswap v3 fee tiers are most active on Base?
2. How large are cross-pool price differences under normal conditions?
3. Are larger swaps associated with larger temporary price dislocations?
4. How quickly do large dislocations recover?
5. How many observed spreads remain positive after accounting for both Uniswap LP fees?

---

## Why This Dataset?

DEX liquidity is fragmented across independent pools.

Even when several pools trade the same asset pair, each pool maintains its own:

- liquidity,
- tick state,
- post-swap price,
- fee tier,
- and transaction flow.

This fragmentation creates a market-microstructure question:

> When one pool temporarily disagrees with another on the price of WETH, is the discrepancy large enough to matter economically?

This makes the dataset useful for studying:

- arbitrage detection,
- MEV-related behavior,
- trade execution,
- liquidity fragmentation,
- market efficiency,
- and price-impact risk.

Base was selected because it is an EVM-compatible network with public JSON-RPC access and active decentralized-exchange usage.

---

# Data Source

All primary blockchain data is collected directly from **Base Mainnet** using Ethereum JSON-RPC.

Default RPC endpoint:

```text
https://mainnet.base.org
```

Base Mainnet chain ID:

```text
8453
```

The project does **not** depend on a subgraph or centralized blockchain indexer for its core transaction dataset.

The main RPC operation used for historical swap collection is:

```text
eth_getLogs
```

---

# Protocol

The project analyzes **Uniswap v3 WETH/USDC pools on Base**.

Rather than hard-coding pool addresses, the application queries the canonical Uniswap v3 Factory deployment and calls:

```solidity
getPool(tokenA, tokenB, fee)
```

for configured WETH/USDC fee tiers.

Canonical Base Uniswap v3 Factory:

```text
0x33128a8fC17869897dcE68Ed026d694621f6FDfD
```

Configured fee tiers:

```text
0.01%  -> 100
0.05%  -> 500
0.30%  -> 3000
1.00%  -> 10000
```

---

# Tokens

## WETH

```text
0x4200000000000000000000000000000000000006
```

## USDC

```text
0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913
```

Token metadata is queried directly from the ERC-20 contracts using:

```solidity
symbol()
decimals()
```

This avoids relying on hard-coded decimal assumptions.

---

# Architecture

```text
                       Base Mainnet
                            |
                            | JSON-RPC
                            v
                    Uniswap v3 Factory
                            |
                            | getPool(...)
                            v
                      Pool Discovery
                            |
                            v
                       eth_getLogs
                            |
                            v
                    Swap Event Decoder
                            |
                            v
                         SQLite
                            |
              +-------------+-------------+
              |                           |
              v                           v
       Token Normalization          Pool Price Decode
                                      sqrtPriceX96
              |                           |
              +-------------+-------------+
                            |
                            v
                 Ordered Market-State
                    Reconstruction
                            |
              +-------------+-------------+
              |             |             |
              v             v             v
          Spread        Swap Size      Recovery
          Analysis      Analysis       Analysis
              |             |             |
              +-------------+-------------+
                            |
                            v
              Arbitrage Candidate Filter
                            |
                            v
                CSV + JSON + PNG Outputs
```

---

# Repository Structure

```text
lindenshore-blockchain-discovery/
│
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── main.py
│
├── src/
│   ├── __init__.py
│   ├── abis.py
│   ├── analysis.py
│   ├── collector.py
│   ├── config.py
│   ├── database.py
│   ├── pools.py
│   ├── pricing.py
│   ├── rpc.py
│   └── tokens.py
│
├── scripts/
│   ├── __init__.py
│   ├── collect_swaps.py
│   ├── discover_pools.py
│   ├── run_analysis.py
│   └── validate_data.py
│
├── tests/
│   ├── __init__.py
│   ├── test_analysis.py
│   ├── test_database.py
│   └── test_pricing.py
│
├── data/
│   └── sample_swaps.csv
│
└── output/
    ├── 01_pool_prices.png
    ├── 02_spread_distribution.png
    ├── 03_swap_size_vs_spread.png
    ├── 04_recovery_times.png
    └── summary.json
```

Generated databases and large analysis CSV files are intentionally excluded from version control because they can be recreated from public blockchain data.

---

# Methodology

## 1. RPC Connection

The project connects to Base using `web3.py`.

The RPC layer verifies:

- the endpoint is reachable,
- the connection succeeds,
- and the returned chain ID is `8453`.

Example:

```python
w3 = Web3(Web3.HTTPProvider(RPC_URL))

if not w3.is_connected():
    raise RuntimeError("Unable to connect to Base RPC")

if w3.eth.chain_id != 8453:
    raise RuntimeError("Unexpected blockchain network")
```

---

## 2. Pool Discovery

The Uniswap v3 Factory contract is queried for WETH/USDC pools across the configured fee tiers.

For each fee tier:

```python
factory.functions.getPool(
    WETH_ADDRESS,
    USDC_ADDRESS,
    fee
).call()
```

If the returned address is not the zero address, the pool exists and is included in the dataset.

The pool contract is then queried for:

- `token0()`
- `token1()`
- `fee()`

This makes pool discovery reproducible and avoids depending on manually copied addresses.

---

## 3. Token Metadata

For each token, the application queries:

```solidity
symbol()
decimals()
```

The metadata is stored in SQLite.

Raw token amounts are converted with:

```text
human_amount =
raw_amount / 10^decimals
```

---

## 4. Swap Event Collection

Uniswap v3 pools emit:

```solidity
event Swap(
    address indexed sender,
    address indexed recipient,
    int256 amount0,
    int256 amount1,
    uint160 sqrtPriceX96,
    uint128 liquidity,
    int24 tick
);
```

The collector retrieves these events using:

```text
eth_getLogs
```

with filters for:

- pool address,
- block range,
- and the `Swap` event topic.

For each Swap event, the project stores:

```text
chain
block_number
block_timestamp
transaction_hash
transaction_index
log_index
pool_address
fee_tier
sender
recipient
amount0_raw
amount1_raw
sqrt_price_x96
liquidity
tick
```

---

## 5. Block-Range Chunking

Large historical log requests can exceed public RPC limits.

The collector therefore divides the requested block interval into smaller chunks.

Example:

```text
50130000 - 50130499
50130500 - 50130999
50131000 - 50131499
...
```

The chunk size is configurable.

If the public RPC rejects large requests, the user can reduce it:

```bash
python -m scripts.collect_swaps --days 1 --chunk-size 200
```

or:

```bash
python -m scripts.collect_swaps --days 1 --chunk-size 100
```

---

## 6. RPC Retry Logic

RPC calls can fail because of:

- public-node congestion,
- network errors,
- response-size limits,
- or rate limits.

The RPC helper therefore uses exponential backoff.

Approximate retry delays:

```text
1 second
2 seconds
4 seconds
8 seconds
16 seconds
```

---

## 7. Checkpointing

For every pool, the collector stores:

```text
last_processed_block
```

inside the `collector_state` table.

The checkpoint is only updated after an entire block chunk completes successfully.

This allows interrupted collection to resume from the last successful block range.

---

## 8. Duplicate Protection

Every event is uniquely identified by:

```text
transaction_hash + log_index
```

SQLite enforces:

```sql
UNIQUE(transaction_hash, log_index)
```

The collector also uses `INSERT OR IGNORE`, preventing duplicated records when a collection is repeated.

---

# SQLite Schema

The local database contains four main tables.

## `tokens`

```text
address
symbol
decimals
```

## `pools`

```text
address
token0
token1
fee
```

## `swaps`

```text
chain
block_number
block_timestamp
transaction_hash
transaction_index
log_index
pool_address
fee_tier
sender
recipient
amount0_raw
amount1_raw
sqrt_price_x96
liquidity
tick
```

Raw large integer values are preserved in SQLite instead of being prematurely converted into floating-point storage.

## `collector_state`

```text
pool_address
last_processed_block
updated_at
```

---

# Price Calculation

## Human-Readable Token Amounts

Raw ERC-20 values are converted using:

```text
human amount =
raw amount / 10^token_decimals
```

Example:

```text
1,000,000 raw USDC
with 6 decimals
=
1 USDC
```

---

## Execution Price

Once the token ordering is normalized into WETH and USDC:

```text
execution price =
|USDC amount / WETH amount|
```

This represents the swap's average execution price.

---

## `sqrtPriceX96`

Uniswap v3 stores pool price using Q64.96 fixed-point representation.

Conceptually:

```text
sqrtPriceX96
-------------
    2^96

=
sqrt(raw token1 / raw token0)
```

Therefore:

```text
raw_price =
(sqrtPriceX96 / 2^96)^2
```

The price is then adjusted for token decimals:

```text
human token1/token0 price =
raw_price × 10^(decimals0 - decimals1)
```

Finally, the project normalizes the result into:

```text
USDC per WETH
```

regardless of whether WETH is `token0` or `token1`.

---

# Ordered Market-State Reconstruction

The analysis processes Swap events in deterministic blockchain order:

```text
block_number
    ↓
transaction_index
    ↓
log_index
```

After each Swap event:

1. the affected pool's latest post-swap price is updated;
2. the affected pool is compared against the latest known state of every other active WETH/USDC pool;
3. comparisons between two unaffected pools are not duplicated.

This avoids associating an unrelated trigger swap with a pool pair that did not change.

---

# State Freshness

Pools do not update continuously.

A low-activity pool may retain an old observed price while other pools continue trading.

To avoid treating stale prices as contemporaneous quotes, this analysis excludes cross-pool comparisons when the other pool's latest observed state is more than:

```text
60 seconds
```

old.

This is still an approximation rather than exact historical state simulation, but it materially reduces false dislocations caused by inactive pools.

---

# Cross-Pool Spread

For two normalized WETH prices:

```text
price_a
price_b
```

the absolute price dislocation is:

```text
spread_bps =
|price_a - price_b|
-------------------
min(price_a, price_b)

× 10,000
```

where:

```text
1 basis point = 0.01%
```

Example:

```text
20 bps = 0.20%
```

---

# Fee-Adjusted Arbitrage Signal

If one pool has a lower observed WETH price than another:

```text
buy_price  = lower pool price
sell_price = higher pool price
```

the directional raw edge is:

```text
gross edge =
sell_price / buy_price - 1
```

The project then subtracts both Uniswap LP fees.

For example:

```text
0.01% pool = 1 bp
0.05% pool = 5 bps
```

A 10-bps raw difference between those pools becomes approximately:

```text
10 - 1 - 5 = 4 bps
```

before accounting for any other costs.

A positive fee-adjusted value is treated only as a:

> **candidate arbitrage signal**

It is not equivalent to guaranteed profit.

A production arbitrage strategy would additionally need to model:

- gas,
- price impact,
- slippage,
- route size,
- transaction latency,
- state changes,
- transaction ordering,
- competition,
- and failed execution risk.

---

# Swap-Size Analysis

Each cross-pool observation is grouped by the swap that triggered the state update.

Buckets:

```text
<$1k
$1k-$10k
$10k-$100k
$100k+
```

For each bucket, the project calculates:

- observation count,
- mean spread,
- median spread,
- 95th-percentile spread.

This allows the analysis to investigate whether larger trades are associated with greater temporary price dislocation.

---

# Price-Dislocation Recovery

The analysis defines a dislocation as:

```text
spread >= 20 bps
```

A strict recovery is defined as:

```text
spread <= 5 bps
```

within:

```text
300 seconds
```

For each detected episode, the project records:

```text
start_time
initial_spread_bps
recovery_time
recovery_seconds
fee_adjusted_edge_bps
```

This recovery analysis is intentionally conservative.

---

# Data Validation

The project includes:

```bash
python -m scripts.validate_data
```

The final dataset passed the following checks:

```text
True same-sign swap violations: 0
Zero-amount / dust events: 1
Duplicate event IDs: 0
Missing timestamps: 0
```

One event contained a zero-valued token side due to an extremely small dust-sized amount and was retained rather than treated as malformed data.

---

# Tests

Run:

```bash
pytest -v
```

The final test suite contains:

```text
12 tests
```

covering:

- token amount conversion,
- `sqrtPriceX96` conversion,
- decimal adjustment,
- execution-price calculation,
- spread calculation,
- gross edge calculation,
- fee-adjusted edge calculation,
- database schema creation,
- minimum two-pool market-state behavior,
- spread detection,
- trigger-pool-only comparison,
- stale-state filtering.

The final project passes all tests.

---

# Installation

Python 3.11+ is recommended.

## 1. Clone the repository

```bash
git clone <repository-url>
cd lindenshore-blockchain-discovery
```

## 2. Create a virtual environment

Windows:

```powershell
python -m venv .venv
```

Activate:

```powershell
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

## 4. Configure RPC

Create:

```text
.env
```

with:

```env
BASE_RPC_URL=https://mainnet.base.org
```

The repository also includes:

```text
.env.example
```

---

# Usage

## Discover pools

```bash
python -m scripts.discover_pools
```

This:

1. connects to Base,
2. loads the Uniswap v3 Factory,
3. discovers WETH/USDC pools,
4. reads pool metadata,
5. reads ERC-20 token metadata,
6. stores metadata locally.

---

## Collect a small smoke-test sample

```bash
python -m scripts.collect_swaps --days 0.02 --chunk-size 200
```

`0.02` days is approximately 29 minutes.

---

## Collect a six-hour dataset

```bash
python -m scripts.collect_swaps --days 0.25 --chunk-size 500
```

---

## Collect a one-day dataset

```bash
python -m scripts.collect_swaps --days 1 --chunk-size 500
```

If the RPC rejects large requests:

```bash
python -m scripts.collect_swaps --days 1 --chunk-size 200
```

---

## Validate the database

```bash
python -m scripts.validate_data
```

---

## Run tests

```bash
pytest -v
```

---

## Run analysis

```bash
python -m scripts.run_analysis
```

---

## Run the complete pipeline

```bash
python main.py --days 0.25
```

---

# Generated Outputs

The analysis generates:

```text
output/
├── 01_pool_prices.png
├── 02_spread_distribution.png
├── 03_swap_size_vs_spread.png
├── 04_recovery_times.png
├── pool_activity.csv
├── processed_swaps.csv
├── market_state.csv
├── swap_size_analysis.csv
├── recovery_events.csv
├── arbitrage_candidates.csv
└── summary.json
```

Large generated CSV files are excluded from Git, but the analysis can reproduce them from public blockchain data.

---

# Findings

## Dataset Overview

The final dataset contains **13,780 Uniswap v3 WETH/USDC Swap events** collected directly from Base through JSON-RPC over an approximately six-hour observation window.

After reconstructing pool state and applying a 60-second freshness limit to cross-pool comparisons, the analysis produced **27,215 market-state observations**.

Trading activity varied substantially across fee tiers:

| Fee Tier | Swaps | Observed Volume |
|---|---:|---:|
| 0.01% | 6,901 | ~$1.08M |
| 0.05% | 2,995 | ~$1.09M |
| 0.30% | 3,879 | ~$1.86M |
| 1.00% | 5 | ~$669 |

The **0.01% pool** processed the largest number of swaps, while the **0.30% pool** handled the greatest observed volume.

The **1.00% pool** was effectively inactive during the sample.

---

## Cross-Pool Price Efficiency

Across **27,215 recent-state cross-pool observations**, the median WETH/USDC price difference was:

```text
4.33 bps
```

The mean spread was:

```text
7.54 bps
```

The 95th percentile was:

```text
22.28 bps
```

The 99th percentile was:

```text
28.03 bps
```

The largest observed spread was:

```text
34.72 bps
```

A total of:

```text
1,969 observations
```

exceeded the project's 20-bps dislocation threshold.

These results show that independent fee-tier pools regularly disagree on price, although most discrepancies remain relatively small.

---

## Effect of Trading Fees

The strongest finding is that an observable price difference is very different from an economically plausible arbitrage signal.

Only:

```text
8 of 27,215 observations
```

or approximately:

```text
0.029%
```

remained positive after subtracting both Uniswap liquidity-provider fees.

That is roughly:

```text
1 in 3,402
```

market-state observations.

Therefore:

> **Raw price spread alone substantially overstates apparent cross-pool arbitrage opportunities.**

The strongest fee-adjusted candidate signal had an estimated remaining edge of approximately:

```text
5.68 bps
```

after both pool fees.

This should not be interpreted as guaranteed profit because the analysis does not fully model:

- gas,
- price impact,
- slippage,
- latency,
- state changes,
- or execution competition.

---

## Swap Size and Price Dislocation

Trades below $10,000 showed similar median cross-pool spreads:

| Trigger Swap Size | Observations | Median Spread | P95 Spread |
|---|---:|---:|---:|
| <$1k | 26,325 | 4.32 bps | 21.60 bps |
| $1k-$10k | 832 | 3.99 bps | 25.50 bps |
| $10k-$100k | 50 | 25.28 bps | 29.40 bps |
| $100k+ | 8 | 23.98 bps | 27.75 bps |

The data does **not** show a smooth monotonic relationship across all trade sizes.

However, the sample shows a clear threshold-like difference:

```text
under $10k
→ median spread ≈ 4 bps

$10k+
→ median spread ≈ 24-25 bps
```

This suggests that sufficiently large swaps can create materially larger temporary price dislocations.

The largest trade-size buckets contain fewer observations, so this result should be interpreted cautiously rather than as a universal causal relationship.

---

## Recovery Behavior

Using a strict definition:

```text
dislocation:
spread >= 20 bps

recovery:
spread <= 5 bps

maximum window:
300 seconds
```

the analysis detected:

```text
49 dislocation episodes
```

Only:

```text
5 episodes
```

recovered under this strict definition.

Among those recovered episodes:

```text
median recovery time = 124 seconds
p90 recovery time    = 150 seconds
```

It would therefore be misleading to say that dislocations usually recover in 124 seconds.

The correct interpretation is:

> Among the small subset of episodes that returned below the strict 5-bps threshold within five minutes, the median recovery time was 124 seconds.

The relatively low recovery count suggests that a 5-bps threshold is tighter than the persistent differences observed between some fee-tier pools.

---

## Candidate Arbitrage Signals

The analysis identified:

```text
8
```

market-state observations with a positive edge after accounting for both Uniswap LP fees.

The strongest observed candidate occurred around block:

```text
50131428
```

with approximately:

```text
buy price:  $1,900.3126
sell price: $1,902.5322
fee-adjusted edge: 5.68 bps
trigger swap size: ~$4,272
```

This is classified only as a:

> **fee-adjusted candidate arbitrage signal**

not a guaranteed profitable arbitrage opportunity.

A complete profitability model would additionally require route simulation, gas estimation, slippage, available liquidity, and execution-risk modeling.

---

## Final Interpretation

The central result of this project is:

> **Visible DEX price disagreement is far more common than fee-adjusted arbitrage opportunity.**

Different Uniswap v3 fee tiers can maintain measurable price differences, particularly around larger trades, but the liquidity-provider fees required to trade across two pools consume almost all observed raw spreads.

This demonstrates why practical arbitrage detection requires more than comparing two quoted prices.

The following factors materially affect whether a price difference is economically interesting:

- pool fee tiers,
- trade size,
- state freshness,
- liquidity,
- price impact,
- gas,
- slippage,
- and execution competition.

---

# Potential Applications

## 1. Arbitrage Detection

Cross-pool price discrepancies can be used as an initial arbitrage signal.

A production implementation could extend this project by:

- simulating exact swap routes,
- calculating executable trade size,
- estimating gas,
- modeling price impact,
- modeling slippage,
- and calculating expected net profit.

---

## 2. MEV Research

Transaction ordering around large dislocations can be used to investigate possible arbitrage and MEV behavior.

A future extension could analyze:

```text
block_number
transaction_index
log_index
sender
recipient
```

to identify addresses that repeatedly trade shortly after large pool-price movements.

Such addresses should only be described as:

> candidate arbitrage actors

unless more detailed transaction tracing supports stronger attribution.

---

## 3. Execution Analysis

The relationship between trade size and resulting dislocation can be useful for evaluating execution quality.

A large trader could use this information to decide whether:

- a single pool should be avoided,
- an order should be split,
- or liquidity should be routed across multiple venues.

---

## 4. Liquidity Risk

Persistent or unusually large price dislocations may indicate:

- shallow liquidity,
- fragmented liquidity,
- market stress,
- or poor execution quality.

This can support DEX market-quality monitoring.

---

## 5. Market-Efficiency Measurement

Cross-pool spread and recovery behavior provide observable measures of decentralized-market efficiency.

A highly efficient market should generally show:

- small ordinary spreads,
- relatively few economically meaningful discrepancies,
- and rapid convergence after large price movements.

---

# Limitations

## Public RPC Limits

The default Base public RPC endpoint can:

- rate-limit requests,
- reject very large historical log queries,
- or temporarily time out.

The collector therefore uses:

- block chunking,
- retry logic,
- exponential backoff,
- and persistent checkpoints.

A different Base RPC endpoint can be configured through `.env` without changing application code.

---

## Observed State vs Exact Executable State

The project reconstructs recent observed pool states from Swap events.

This is more informative than simple nearest-timestamp matching, but it is not identical to full historical state simulation.

Two compared prices should therefore not automatically be interpreted as guaranteed simultaneously executable quotes.

---

## State Freshness

Low-activity pools may retain stale observed prices.

To reduce this problem, the analysis excludes comparisons when the other pool's latest observed state is more than **60 seconds old**.

This is still an approximation.

---

## Pool Fees Are Not Total Trading Cost

The fee-adjusted signal includes both Uniswap LP fees but does not fully account for:

- gas,
- price impact,
- slippage,
- transaction latency,
- transaction ordering,
- competition,
- or failed execution.

Therefore:

> **fee-adjusted edge != guaranteed arbitrage profit**

---

## MEV Attribution

Rapid price convergence or repeated transaction timing can be consistent with arbitrage behavior.

It does not prove that:

- a specific address is a bot,
- a specific transaction is MEV,
- or a participant intentionally performed arbitrage.

More detailed tracing would be required for attribution.

---

## Dataset Scope

The project focuses on:

```text
Base
Uniswap v3
WETH/USDC
```

It does not represent every WETH/USDC venue on Base.

A broader study could include:

- other DEX protocols,
- Uniswap v2/v4,
- Aerodrome,
- centralized exchanges,
- or other blockchains.

---

## Observation Window

The final analytical dataset covers approximately six hours.

This is sufficient for the discovery objective and produces tens of thousands of state comparisons, but the findings should not automatically be generalized to all market regimes or all periods.

---

# Reproducibility

A new user can reproduce the project with:

```bash
python -m venv .venv
```

Activate the environment, then:

```bash
pip install -r requirements.txt
python -m scripts.discover_pools
python -m scripts.collect_swaps --days 0.25 --chunk-size 500
python -m scripts.validate_data
pytest -v
python -m scripts.run_analysis
```

The SQLite database and generated analysis files can be rebuilt entirely from public blockchain data.

---

# Future Work

Potential extensions include:

## Same-Block Arbitrage Detection

Analyze transaction and log ordering around detected price dislocations.

## Candidate Arbitrage-Actor Ranking

Rank addresses by:

- number of dislocation-adjacent transactions,
- reaction delay,
- pools interacted with,
- estimated fee-adjusted edge,
- recurrence across blocks.

## Gas-Cost Modeling

Retrieve transaction receipts and estimate:

```text
estimated profit =
trade notional × fee-adjusted edge
- gas
- price impact
```

## Liquidity-Depth Modeling

Use Uniswap v3 concentrated-liquidity state to estimate how much capital could realistically be traded before an apparent edge disappears.

## Cross-DEX Comparison

Compare WETH/USDC pricing on Uniswap v3 with other Base DEX venues.

## Cross-Chain Comparison

Repeat the same methodology on Ethereum and compare:

- spread magnitude,
- swap size,
- fee-adjusted opportunity frequency,
- recovery behavior,
- and market efficiency.

---

# Conclusion

This project demonstrates how raw blockchain RPC data can be transformed into a meaningful market-microstructure dataset.

The complete pipeline covers:

```text
RPC connectivity
        ↓
protocol discovery
        ↓
on-chain Swap collection
        ↓
event decoding
        ↓
local SQLite storage
        ↓
price normalization
        ↓
ordered market-state reconstruction
        ↓
freshness filtering
        ↓
cross-pool spread analysis
        ↓
fee-adjusted arbitrage filtering
        ↓
market-structure insights
```

The key finding is that:

> **raw cross-pool price differences are common, but economically interesting fee-adjusted signals are extremely rare.**

Across **27,215 recent-state observations**, only **8 (0.029%)** remained positive after accounting for both Uniswap LP fees.

The project therefore shows why useful blockchain arbitrage analysis requires more than detecting a difference between two prices: fee structure, state freshness, trade size, and execution costs all matter.
