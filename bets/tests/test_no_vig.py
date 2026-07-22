import pytest

from src.no_vig import (
    american_to_decimal,
    american_to_implied_probability,
    expected_value,
    remove_vig_two_way,
)


def test_american_to_decimal():
    assert american_to_decimal(150) == pytest.approx(2.5)
    assert american_to_decimal(-200) == pytest.approx(1.5)


def test_implied_probability():
    assert american_to_implied_probability(100) == pytest.approx(0.5)
    assert american_to_implied_probability(-150) == pytest.approx(0.6)


def test_no_vig_sums_to_one():
    pair = remove_vig_two_way(-120, 110)
    assert pair.side_a_probability + pair.side_b_probability == pytest.approx(1.0)
    assert pair.overround > 0


def test_expected_value():
    assert expected_value(0.55, 100) == pytest.approx(0.10)
