import math

import numpy as np
import pandas as pd


Q96 = 2 ** 96


def raw_to_human(
    raw_amount: int,
    decimals: int,
) -> float:
    return (
        raw_amount
        / (10 ** decimals)
    )


def sqrt_price_x96_to_token1_per_token0(
    sqrt_price_x96: int,
    decimals0: int,
    decimals1: int,
) -> float:
    """
    Convert Uniswap v3 sqrtPriceX96 into a
    human-readable token1/token0 price.

    sqrtPriceX96 encodes:

        sqrt(raw_token1 / raw_token0) * 2**96

    Token decimal adjustment is therefore required.
    """
    if sqrt_price_x96 <= 0:
        raise ValueError(
            "sqrt_price_x96 must be positive"
        )

    raw_ratio = (
        sqrt_price_x96 / Q96
    ) ** 2

    decimal_adjustment = (
        10 ** (decimals0 - decimals1)
    )

    return (
        raw_ratio
        * decimal_adjustment
    )


def execution_price_quote_per_base(
    base_amount: float,
    quote_amount: float,
) -> float:
    """
    Return quote-token units per one unit
    of base token.
    """
    if base_amount == 0:
        return np.nan

    return abs(
        quote_amount / base_amount
    )


def normalize_swap_dataframe(
    df: pd.DataFrame,
    base_symbol: str = "WETH",
    quote_symbol: str = "USDC",
) -> pd.DataFrame:
    """
    Convert raw blockchain swap data into
    normalized WETH/USDC prices and sizes.

    Output prices are always quote/base,
    e.g. USDC per WETH.
    """
    if df.empty:
        return df.copy()

    result = df.copy()

    result["amount0_raw"] = (
        result["amount0_raw"]
        .map(int)
    )

    result["amount1_raw"] = (
        result["amount1_raw"]
        .map(int)
    )

    result["sqrt_price_x96"] = (
        result["sqrt_price_x96"]
        .map(int)
    )

    result["amount0"] = (
        result["amount0_raw"]
        / (
            10.0
            ** result["token0_decimals"]
        )
    )

    result["amount1"] = (
        result["amount1_raw"]
        / (
            10.0
            ** result["token1_decimals"]
        )
    )

    result["token1_per_token0"] = result.apply(
        lambda row:
            sqrt_price_x96_to_token1_per_token0(
                int(row["sqrt_price_x96"]),
                int(row["token0_decimals"]),
                int(row["token1_decimals"]),
            ),
        axis=1,
    )

    base_amounts = []
    quote_amounts = []
    pool_prices = []

    for _, row in result.iterrows():

        token0_symbol = row[
            "token0_symbol"
        ]

        token1_symbol = row[
            "token1_symbol"
        ]

        if (
            token0_symbol == base_symbol
            and token1_symbol == quote_symbol
        ):
            base_amount = row["amount0"]
            quote_amount = row["amount1"]

            pool_price = (
                row["token1_per_token0"]
            )

        elif (
            token1_symbol == base_symbol
            and token0_symbol == quote_symbol
        ):
            base_amount = row["amount1"]
            quote_amount = row["amount0"]

            token1_per_token0 = (
                row["token1_per_token0"]
            )

            if token1_per_token0 == 0:
                pool_price = np.nan
            else:
                pool_price = (
                    1.0
                    / token1_per_token0
                )

        else:
            raise ValueError(
                "Unexpected pair: "
                f"{token0_symbol}/"
                f"{token1_symbol}"
            )

        base_amounts.append(
            float(base_amount)
        )

        quote_amounts.append(
            float(quote_amount)
        )

        pool_prices.append(
            float(pool_price)
        )

    result["base_amount"] = base_amounts
    result["quote_amount"] = quote_amounts

    result["execution_price"] = (
        np.abs(
            result["quote_amount"]
            / result["base_amount"]
        )
    )

    result["pool_price"] = (
        pool_prices
    )

    result["swap_usd"] = np.abs(
        result["quote_amount"]
    )

    result["direction"] = np.where(
        result["base_amount"] > 0,
        f"{base_symbol}_IN",
        f"{base_symbol}_OUT",
    )

    result["timestamp"] = pd.to_datetime(
        result["block_timestamp"],
        unit="s",
        utc=True,
    )

    result["fee_rate"] = (
        result["fee_tier"]
        / 1_000_000
    )

    result["fee_bps"] = (
        result["fee_tier"]
        / 100
    )

    return result


def spread_bps(
    price_a: float,
    price_b: float,
) -> float:

    if (
        price_a <= 0
        or price_b <= 0
        or math.isnan(price_a)
        or math.isnan(price_b)
    ):
        return np.nan

    return (
        abs(price_a - price_b)
        / min(price_a, price_b)
        * 10_000
    )


def gross_directional_edge_bps(
    buy_price: float,
    sell_price: float,
) -> float:
    """
    Gross arbitrage edge in basis points.

    Positive means selling at sell_price is
    above buying at buy_price.
    """
    if buy_price <= 0:
        return np.nan

    return (
        (sell_price / buy_price) - 1
    ) * 10_000


def fee_adjusted_edge_bps(
    buy_price: float,
    sell_price: float,
    buy_fee_tier: int,
    sell_fee_tier: int,
) -> float:

    gross = gross_directional_edge_bps(
        buy_price,
        sell_price,
    )

    buy_fee_bps = (
        buy_fee_tier / 100
    )

    sell_fee_bps = (
        sell_fee_tier / 100
    )

    return (
        gross
        - buy_fee_bps
        - sell_fee_bps
    )