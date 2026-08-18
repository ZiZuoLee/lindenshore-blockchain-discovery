# Base Uniswap v3 Price Dislocation Analysis

A blockchain data-discovery project analyzing temporary price differences between Uniswap v3 WETH/USDC liquidity pools on Base.

This project was developed for the **Lindenshore Technical Assessment: Blockchain Data Discovery**.

---

## TL;DR

This project connects directly to the Base blockchain through JSON-RPC, discovers Uniswap v3 WETH/USDC pools from the canonical Uniswap v3 Factory, collects `Swap` events with `eth_getLogs`, stores the raw data in SQLite, converts Uniswap v3 `sqrtPriceX96` values into human-readable prices, and analyzes cross-pool price dislocations.

The main research question is:

> **How efficiently do independent Uniswap v3 WETH/USDC pools on Base remain synchronized, and do temporary price dislocations create observable arbitrage signals?**

The analysis focuses on:

- activity across fee tiers,
- cross-pool WETH/USDC price differences,
- the relationship between swap size and price dislocation,
- how quickly large dislocations disappear,
- and whether observed price spreads remain positive after accounting for Uniswap liquidity-provider fees.

The project deliberately distinguishes **observable price dislocations** from **guaranteed executable arbitrage**. A positive observed spread can still disappear after accounting for pool fees, gas, slippage, price impact, state changes, and competition.

---

## Research Question

Uniswap v3 allows multiple independent liquidity pools for the same token pair, each with a different fee tier.

For WETH/USDC, these pools can temporarily disagree on price because:

1. each pool has separate liquidity,
2. each pool has separate state,
3. a large trade can move one pool more than another,
4. arbitrageurs can subsequently trade against the discrepancy.

This project investigates the following questions:

1. Which WETH/USDC Uniswap v3 fee tiers are the most active on Base?
2. How large are cross-pool price differences under normal conditions?
3. Are larger swaps associated with larger temporary price dislocations?
4. How quickly do large dislocations recover?
5. How many apparent arbitrage opportunities remain after accounting for both Uniswap pool fees?

---

## Why This Dataset?

Decentralized exchange liquidity is fragmented.

Even when several pools trade the same pair, each pool independently maintains:

- liquidity,
- reserves,
- tick state,
- price,
- and fee configuration.

That fragmentation makes cross-pool synchronization an interesting market-microstructure problem.

If one pool is moved significantly by a large trade, another pool may temporarily quote a different price for the same asset. In theory, arbitrageurs can exploit that difference and cause prices to converge again.

This makes Uniswap v3 WETH/USDC data useful for studying:

- arbitrage,
- MEV-related behavior,
- execution quality,
- DEX market efficiency,
- liquidity fragmentation,
- and price-impact risk.

Base was selected because it is an EVM-compatible Layer 2 network with public JSON-RPC access and active decentralized-exchange usage.

---

## Data Source

All primary blockchain data is collected directly from **Base Mainnet** through Ethereum JSON-RPC.

Default RPC endpoint:

```text
https://mainnet.base.org
```

Base Mainnet chain ID:

```text
8453
```

The project does **not** depend on a subgraph or centralized blockchain indexer for its core dataset.

The collector primarily uses:

```text
eth_getLogs
```

to retrieve Uniswap v3 `Swap` events directly from Base.

---

## Protocol

The project analyzes **Uniswap v3**.

Rather than hard-coding individual pool addresses, the application queries the canonical Uniswap v3 Factory deployment on Base and calls:

```solidity
getPool(tokenA, tokenB, fee)
```

for the configured WETH/USDC fee tiers.

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

## Tokens

### WETH

```text
0x4200000000000000000000000000000000000006
```

### USDC

```text
0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913
```

Token metadata such as `symbol()` and `decimals()` is queried directly from the ERC-20 contracts and stored locally.

The analysis therefore does not rely on hard-coded assumptions about token decimal precision.

---

## Architecture

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
                   Cross-Pool Matching
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
                CSV + JSON + PNG Outputs
```

---

## Repository Structure

```text
lindenshore-blockchain-discovery/
│
├── .env
├── .env.example
├── .gitignore
├── README.md
├── requirements.txt
├── main.py
│
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── abis.py
│   ├── rpc.py
│   ├── database.py
│   ├── tokens.py
│   ├── pools.py
│   ├── collector.py
│   ├── pricing.py
│   └── analysis.py
│
├── scripts/
│   ├── __init__.py
│   ├── discover_pools.py
│   ├── collect_swaps.py
│   └── run_analysis.py
│
├── tests/
│   ├── __init__.py
│   ├── test_pricing.py
│   └── test_database.py
│
├── data/
│   └── blockchain.db
│
└── output/
    ├── 01_pool_prices.png
    ├── 02_spread_distribution.png
    ├── 03_swap_size_vs_spread.png
    ├── 04_recovery_times.png
    ├── pool_activity.csv
    ├── processed_swaps.csv
    ├── cross_pool_matches.csv
    ├── swap_size_analysis.csv
    ├── recovery_events.csv
    └── summary.json
```

Generated database and analysis files are excluded from Git by default because they can be reproduced from the blockchain.

---

# Methodology

## 1. RPC Connection

The project connects to Base using `web3.py`.

The RPC module verifies:

- that the endpoint is reachable,
- that the connection succeeds,
- and that the returned chain ID is `8453`.

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

The Uniswap v3 Factory contract is queried for WETH/USDC pools.

For each configured fee tier:

```python
factory.functions.getPool(
    WETH_ADDRESS,
    USDC_ADDRESS,
    fee
).call()
```

If the returned address is not the zero address, the pool exists and is included in the dataset.

The application then queries the pool contract for:

- `token0()`
- `token1()`
- `fee()`

This makes the pool-discovery process reproducible and avoids depending on manually copied pool addresses.

---

## 3. Token Metadata

For each token, the application queries:

```solidity
symbol()
decimals()
```

The metadata is stored in SQLite.

This is important because blockchain token quantities are integers and must be converted using the token's actual number of decimal places.

For example:

```text
human_amount =
raw_amount / 10^decimals
```

---

## 4. Swap Event Collection

Uniswap v3 pools emit the following event:

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

---

## 5. Block-Range Chunking

Historical blockchain log requests can become large.

To avoid oversized RPC requests, the requested block interval is divided into smaller chunks.

Example:

```text
50134595 - 50134794
50134795 - 50134994
50134995 - 50135194
...
```

Each successful chunk is processed independently.

The default chunk size is configurable.

If the free RPC endpoint rejects large requests, the user can reduce the size:

```bash
python -m scripts.collect_swaps --days 1 --chunk-size 200
```

or:

```bash
python -m scripts.collect_swaps --days 1 --chunk-size 100
```

---

## 6. RPC Retry Logic

RPC failures may occur because of:

- rate limits,
- temporary network errors,
- response-size limits,
- or public-node congestion.

RPC calls therefore use exponential backoff.

The retry sequence is approximately:

```text
1 second
2 seconds
4 seconds
8 seconds
16 seconds
```

This makes long-running historical collection more robust.

---

## 7. Checkpointing

For every pool, the collector stores:

```text
last_processed_block
```

inside the `collector_state` table.

The checkpoint is only advanced after an entire block chunk has completed successfully.

This means a failed collection can resume from the last successful chunk rather than starting from the beginning.

---

## 8. Duplicate Protection

Every swap is uniquely identified by:

```text
transaction_hash + log_index
```

SQLite enforces:

```sql
UNIQUE(transaction_hash, log_index)
```

The collector also uses `INSERT OR IGNORE`.

This prevents duplicate records when data collection is resumed or repeated.

---

# SQLite Schema

The local database contains four main tables.

## `tokens`

Stores token metadata.

```text
address
symbol
decimals
```

---

## `pools`

Stores discovered Uniswap pools.

```text
address
token0
token1
fee
```

---

## `swaps`

Stores raw on-chain Swap event data.

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

Raw large blockchain integer values are preserved instead of prematurely converting them into floating-point database values.

---

## `collector_state`

Stores collection progress:

```text
pool_address
last_processed_block
updated_at
```

---

# Price Calculation

## Token Amounts

Raw ERC-20 values are converted using:

```text
human amount =
raw amount / 10^token_decimals
```

For example:

```text
1,000,000 raw USDC
with 6 decimals
=
1 USDC
```

---

## Execution Price

A swap contains both token quantities.

Once token ordering has been normalized into WETH and USDC:

```text
execution price =
|USDC amount / WETH amount|
```

This represents the average execution price of that individual swap.

---

## `sqrtPriceX96`

Uniswap v3 stores its pool price using a Q64.96 fixed-point representation.

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

The value must then be corrected for token decimals:

```text
human token1/token0 price =
raw_price × 10^(decimals0 - decimals1)
```

Finally, the application normalizes the value into:

```text
USDC per WETH
```

regardless of whether WETH is `token0` or `token1`.

---

# Cross-Pool Matching

Pools do not necessarily emit Swap events at exactly the same timestamp.

To compare independent pool states, each swap observation is matched against the nearest observed Swap event from another pool within a configurable time tolerance.

The current discovery configuration uses:

```text
maximum timestamp difference = 10 seconds
```

This is an observational approximation.

It allows the project to study cross-pool price behavior, but it does **not** imply that both prices were simultaneously executable at the exact same blockchain state.

---

# Cross-Pool Spread

For two normalized WETH prices:

```text
price_a
price_b
```

the absolute price dislocation is expressed in basis points:

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

the raw directional edge is:

```text
gross edge =
sell_price / buy_price - 1
```

The project then subtracts both Uniswap LP fees.

For example:

```text
0.05% pool = 5 bps
0.30% pool = 30 bps
```

So a 40 bps raw difference between those two pools would have an approximate fee-adjusted edge of:

```text
40 - 5 - 30 = 5 bps
```

before accounting for any other costs.

A positive fee-adjusted edge is treated only as a **candidate arbitrage signal**.

It is not equivalent to guaranteed profit.

A production arbitrage strategy would additionally need to model:

- gas,
- price impact,
- slippage,
- route size,
- state changes,
- transaction latency,
- competition,
- reordering,
- and failed-transaction risk.

---

# Swap-Size Analysis

For matched cross-pool observations, the application groups swap size into:

```text
<$1k
$1k-$10k
$10k-$100k
$100k+
```

For each bucket it calculates:

- observation count,
- mean spread,
- median spread,
- 95th-percentile spread.

This tests whether larger trades are associated with larger temporary cross-pool dislocations.

---

# Price-Dislocation Recovery

The application identifies a dislocation when:

```text
spread >= 20 bps
```

It then searches forward in time until the observed spread falls below:

```text
5 bps
```

within the configured maximum recovery window.

For each event, it records:

```text
start_time
initial_spread_bps
recovery_time
recovery_seconds
fee_adjusted_edge_bps
```

This allows the project to measure how rapidly independent pools return toward price consistency.

Rapid recovery is **consistent with** competitive arbitrage activity.

It does not prove that a specific transaction or wallet caused the convergence.

---

# Generated Analysis

The analysis pipeline produces four primary visualizations.

## 1. Pool Prices Over Time

```text
output/01_pool_prices.png
```

Shows normalized WETH/USDC prices for different Uniswap v3 fee tiers over time.

Purpose:

- verify that the pools broadly follow the same market,
- identify temporary divergence,
- visually compare price synchronization.

---

## 2. Cross-Pool Spread Distribution

```text
output/02_spread_distribution.png
```

Shows the distribution of observed cross-pool spreads in basis points.

Purpose:

- measure normal market synchronization,
- quantify tail dislocations,
- identify unusually large discrepancies.

---

## 3. Swap Size vs Price Dislocation

```text
output/03_swap_size_vs_spread.png
```

Compares matched swap size with cross-pool spread.

Swap size is plotted on a logarithmic scale because transaction sizes can be strongly skewed.

Purpose:

- investigate market impact,
- test whether large trades correspond to larger temporary discrepancies.

---

## 4. Recovery-Time Distribution

```text
output/04_recovery_times.png
```

Shows how long detected dislocations take to fall below the recovery threshold.

Purpose:

- measure market-efficiency response,
- estimate how quickly cross-pool price inconsistencies disappear.

---

# CSV and JSON Outputs

The project also exports machine-readable results.

```text
output/pool_activity.csv
```

Contains swap counts and volume statistics by pool.

```text
output/processed_swaps.csv
```

Contains normalized human-readable swap data.

```text
output/cross_pool_matches.csv
```

Contains matched observations from different pools.

```text
output/swap_size_analysis.csv
```

Contains spread statistics grouped by swap-size bucket.

```text
output/recovery_events.csv
```

Contains identified dislocation and recovery events.

```text
output/summary.json
```

Contains high-level spread and recovery statistics used in the final findings.

---

# Installation

Python 3.11+ is recommended.

## 1. Clone the Repository

```bash
git clone <repository-url>
cd lindenshore-blockchain-discovery
```

---

## 2. Create a Virtual Environment

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

---

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 4. Configure RPC

Create:

```text
.env
```

with:

```env
BASE_RPC_URL=https://mainnet.base.org
```

The project also includes `.env.example`.

---

# Usage

## Phase 1 — Test RPC Connection

The RPC connection is automatically checked whenever the application starts.

The expected network is:

```text
Base Mainnet
Chain ID: 8453
```

---

## Phase 2 — Discover Pools

Run:

```bash
python -m scripts.discover_pools
```

The program:

1. connects to Base,
2. loads the Uniswap v3 Factory,
3. checks configured WETH/USDC fee tiers,
4. discovers existing pools,
5. reads pool token ordering,
6. reads token metadata,
7. stores the metadata in SQLite.

---

## Phase 3 — Small Collection Smoke Test

Before requesting a large dataset, collect approximately 0.02 days of data:

```bash
python -m scripts.collect_swaps --days 0.02 --chunk-size 200
```

`0.02` days is approximately 29 minutes.

This validates:

- historical block lookup,
- `eth_getLogs`,
- event decoding,
- SQLite inserts,
- checkpointing,
- and multiple pool collection.

---

## Phase 4 — Run Tests

```bash
pytest -v
```

The test suite validates:

- raw token amount conversion,
- `sqrtPriceX96` conversion,
- decimal adjustment,
- execution-price calculation,
- spread calculation,
- fee-adjusted edge calculation,
- and database schema creation.

---

## Phase 5 — Run Analysis

```bash
python -m scripts.run_analysis
```

The results are written into:

```text
output/
```

---

## Phase 6 — Expand Dataset

After the smoke test succeeds, progressively increase the collection period.

Six hours:

```bash
python -m scripts.collect_swaps --days 0.25 --chunk-size 500
```

One day:

```bash
python -m scripts.collect_swaps --days 1 --chunk-size 500
```

Three days:

```bash
python -m scripts.collect_swaps --days 3 --chunk-size 500
```

Seven days:

```bash
python -m scripts.collect_swaps --days 7 --chunk-size 500
```

Because the collector uses checkpoints and unique event identifiers, rerunning collection does not intentionally duplicate already stored swaps.

---

## Complete Pipeline

The complete collection and analysis workflow can also be run through:

```bash
python main.py --days 1
```

For a larger final dataset:

```bash
python main.py --days 7
```

---

# Manual SQLite Verification

The database is located at:

```text
data/blockchain.db
```

Useful verification queries include:

```sql
SELECT COUNT(*)
FROM swaps;
```

View example swaps:

```sql
SELECT *
FROM swaps
LIMIT 20;
```

Count swaps by fee tier:

```sql
SELECT
    fee_tier,
    COUNT(*) AS swap_count
FROM swaps
GROUP BY fee_tier
ORDER BY fee_tier;
```

Inspect discovered pools:

```sql
SELECT *
FROM pools
ORDER BY fee;
```

Inspect token metadata:

```sql
SELECT *
FROM tokens;
```

Inspect collector checkpoints:

```sql
SELECT *
FROM collector_state
ORDER BY pool_address;
```

---

# Tests

Run:

```bash
pytest -v
```

A successful test run should report all tests as passed.

---

# Findings

> **Important:** this section should be updated only after the final multi-day dataset has been collected and analyzed. The project should not fabricate conclusions before observing the data.

## Initial Collection Validation

A short smoke-test collection successfully demonstrated that the full RPC-to-SQLite ingestion path works.

For an approximately 0.02-day collection window, the collector retrieved Swap events from several WETH/USDC Uniswap v3 pools.

Observed activity included:

- active 0.01% pool,
- active 0.05% pool,
- active 0.30% pool,
- no observed swaps from the 1.00% pool during that short sample window.

This confirms that activity is not evenly distributed across fee tiers and that a pool can exist while remaining inactive during a particular observation period.

These numbers are only a collection validation sample and are **not** treated as the final analytical dataset.

---

## Final Pool Activity

TODO after final collection:

Report:

- total swaps collected,
- total swaps by fee tier,
- estimated volume by fee tier,
- median swap size,
- dominant pool.

---

## Final Cross-Pool Price Efficiency

TODO after final analysis:

Report:

- median spread in bps,
- mean spread,
- 95th percentile,
- 99th percentile,
- maximum observed spread,
- count of dislocations above the configured threshold.

---

## Final Swap Size vs Dislocation Result

TODO after final analysis:

Determine whether larger matched swaps are associated with larger cross-pool spreads.

The conclusion should be based on:

```text
output/swap_size_analysis.csv
```

and:

```text
output/03_swap_size_vs_spread.png
```

---

## Final Recovery Behavior

TODO after final analysis:

Report:

- number of detected dislocations,
- number that recovered within the observation window,
- median recovery time,
- 90th-percentile recovery time.

The conclusion should be based on:

```text
output/recovery_events.csv
```

and:

```text
output/04_recovery_times.png
```

---

## Final Fee-Adjusted Arbitrage Signals

TODO after final analysis:

Report:

- raw cross-pool matches,
- number with positive gross spread,
- number remaining positive after both pool fees,
- distribution of fee-adjusted edge.

A positive fee-adjusted signal must **not** be described as guaranteed profit.

---

# Potential Applications

## 1. Arbitrage Detection

Cross-pool discrepancies can provide an initial signal for possible arbitrage.

A production implementation could extend this project by:

- simulating exact trade routes,
- estimating price impact,
- estimating gas,
- evaluating available liquidity,
- and calculating executable net profit.

---

## 2. MEV Research

Transaction timing and ordering around large dislocations can be used to investigate potential arbitrage and MEV behavior.

A future extension could identify addresses repeatedly interacting with affected pools immediately after large price movements.

Such addresses should be treated as **candidate arbitrage actors** unless their behavior can be more conclusively classified.

---

## 3. Execution Analysis

Large traders can use market-impact analysis to evaluate whether:

- one pool should be avoided,
- an order should be split across pools,
- or execution should be routed through the deepest available liquidity.

---

## 4. Liquidity Risk

Large or persistent price dislocations may indicate:

- insufficient liquidity,
- fragmented liquidity,
- unusual market stress,
- or poor execution quality.

This can be useful for DEX market-quality monitoring.

---

## 5. Market-Efficiency Measurement

Cross-pool spread and recovery time can act as observable measures of decentralized market efficiency.

A highly efficient market should generally show:

- small cross-pool spreads,
- few economically meaningful dislocations,
- and rapid recovery after large price movements.

---

# Limitations

## Public RPC Limits

The default Base public RPC endpoint may:

- rate-limit requests,
- reject very large log ranges,
- or temporarily time out.

The collector therefore uses:

- configurable block chunking,
- retry logic,
- exponential backoff,
- and persistent checkpoints.

A user can substitute another public or free-tier Base RPC endpoint through `.env` without changing source code.

---

## Observed State vs Executable State

Cross-pool matching uses nearby Swap observations.

Two matched observations should not automatically be interpreted as two prices that were guaranteed to be simultaneously executable.

Exact executable arbitrage analysis would require state reconstruction or block-level simulation.

---

## Timestamp Resolution

Blockchain timestamps alone do not provide exact intra-block ordering.

Where ordering matters, the raw dataset also stores:

```text
block_number
transaction_index
log_index
```

These can be used for more detailed same-block analysis.

---

## Pool Fees Are Not Total Trading Costs

The fee-adjusted analysis currently includes Uniswap LP fees but does not fully account for:

- gas,
- slippage,
- price impact,
- latency,
- state changes,
- competition,
- transaction ordering,
- or failed transactions.

Therefore:

> **fee-adjusted edge != guaranteed arbitrage profit**

---

## MEV Attribution

Rapid convergence after a large price discrepancy is consistent with arbitrage.

It does not prove that:

- a particular address is a bot,
- a particular transaction is MEV,
- or a particular participant intentionally performed arbitrage.

More detailed transaction tracing would be required for attribution.

---

## Dataset Scope

The project currently focuses on:

```text
Base
Uniswap v3
WETH/USDC
```

It does not capture every WETH/USDC venue on Base.

A more complete market analysis could compare:

- other DEX protocols,
- Uniswap v2/v4,
- Aerodrome,
- centralized exchanges,
- or another blockchain.

---

# Reproducibility

A new user should be able to reproduce the project with:

```bash
python -m venv .venv
```

Activate the environment and run:

```bash
pip install -r requirements.txt
python -m scripts.discover_pools
python -m scripts.collect_swaps --days 1 --chunk-size 500
pytest -v
python -m scripts.run_analysis
```

The generated SQLite database and analysis files can be recreated from public blockchain data.

---

# Future Work

Potential high-value extensions include:

## Same-Block Arbitrage Detection

Analyze:

```text
block_number
transaction_index
log_index
sender
recipient
```

around large dislocations.

This could reveal recurring addresses that consistently trade immediately after one pool is moved.

---

## Candidate Arbitrage-Actor Ranking

Rank addresses using metrics such as:

- number of dislocation-adjacent transactions,
- median reaction delay,
- pools interacted with,
- estimated raw edge,
- recurrence across blocks.

---

## Exact Gas Modeling

Retrieve transaction receipts and Base gas costs to estimate:

```text
estimated profit =
trade notional × fee-adjusted edge
- gas cost
- price impact
```

---

## Liquidity-Depth Modeling

Use Uniswap v3 concentrated-liquidity state to estimate how much capital could realistically be traded before the apparent arbitrage disappears.

---

## Cross-Chain Comparison

Repeat the same methodology on Ethereum and compare:

- swap volume,
- spread magnitude,
- recovery time,
- fee-adjusted opportunities,
- and arbitrage efficiency.

This would directly test whether market efficiency differs between Ethereum and Base.

---

# Conclusion

This project demonstrates how raw blockchain RPC data can be transformed into an interpretable market-microstructure dataset.

The pipeline covers the complete process:

```text
RPC connectivity
        ↓
protocol discovery
        ↓
on-chain event collection
        ↓
event decoding
        ↓
local persistence
        ↓
price normalization
        ↓
cross-pool comparison
        ↓
arbitrage-signal analysis
        ↓
market-efficiency insights
```

The central goal is not merely to download blockchain transactions, but to use immutable on-chain data to answer a practical financial question:

> **When independent decentralized liquidity pools temporarily disagree on price, how large are those differences, how quickly do they disappear, and how often do they remain economically interesting after fees?**

The final conclusions in this repository are based only on collected on-chain observations and are updated after the full analysis dataset has been generated.
