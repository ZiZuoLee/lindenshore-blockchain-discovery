import math

from src.pricing import (
    execution_price_quote_per_base,
    fee_adjusted_edge_bps,
    gross_directional_edge_bps,
    raw_to_human,
    spread_bps,
    sqrt_price_x96_to_token1_per_token0,
)


def test_raw_to_human():

    assert (
        raw_to_human(
            1_000_000,
            6,
        )
        == 1.0
    )

    assert (
        raw_to_human(
            10 ** 18,
            18,
        )
        == 1.0
    )


def test_sqrt_price_equal_raw_ratio():

    price = (
        sqrt_price_x96_to_token1_per_token0(
            2 ** 96,
            18,
            18,
        )
    )

    assert math.isclose(
        price,
        1.0,
        rel_tol=1e-12,
    )


def test_decimal_adjustment():

    price = (
        sqrt_price_x96_to_token1_per_token0(
            2 ** 96,
            18,
            6,
        )
    )

    assert math.isclose(
        price,
        10 ** 12,
        rel_tol=1e-12,
    )


def test_execution_price():

    result = (
        execution_price_quote_per_base(
            base_amount=2,
            quote_amount=-8_000,
        )
    )

    assert result == 4_000


def test_spread_bps():

    result = spread_bps(
        4_000,
        4_040,
    )

    assert math.isclose(
        result,
        100.0,
        rel_tol=1e-12,
    )


def test_gross_directional_edge():

    result = (
        gross_directional_edge_bps(
            4_000,
            4_040,
        )
    )

    assert math.isclose(
        result,
        100.0,
        rel_tol=1e-12,
    )


def test_fee_adjusted_edge():

    result = (
        fee_adjusted_edge_bps(
            buy_price=4_000,
            sell_price=4_040,
            buy_fee_tier=500,
            sell_fee_tier=3000,
        )
    )

    # Gross edge = 100 bps
    # 0.05% = 5 bps
    # 0.30% = 30 bps
    # Net = 65 bps
    assert math.isclose(
        result,
        65.0,
        rel_tol=1e-12,
    )