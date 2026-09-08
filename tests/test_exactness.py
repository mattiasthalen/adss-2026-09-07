"""The acceptance check compares two answers row by row, by value. That is exact or it is not.

A float makes the comparison order-dependent rather than merely imprecise: DuckDB's sum over
doubles is not associative, so two queries summing one measure in two orders disagree by a bit
-- on some machines, some of the time. The check that says no answer holds one is the only
thing standing between that and a failure nobody can reproduce. ADR 0007.
"""

from decimal import Decimal

import pytest

from adss.checks import inexact


def test_an_answer_of_counts_and_exact_decimals_is_accepted():
    assert inexact([("1996-07", 17, Decimal("109.00000000")), ("1996-08", 23, None)]) == []


@pytest.mark.parametrize(
    "value",
    [8.49, float("nan"), float("inf"), 0.0, -1.5],
)
def test_any_float_at_all_is_reported(value: float):
    assert inexact([("a", 1, value)]) == ["float"]


def test_a_bool_is_not_inexact():
    """True is an int in Python, and an int is exact. Refusing it would refuse a flag."""
    assert inexact([(True, False)]) == []


def test_it_looks_at_every_row_and_not_only_the_first():
    """A ratio that is whole in the first month and not in the second is the realistic shape."""
    assert inexact([("a", 1), ("b", 2), ("c", 8.49)]) == ["float"]


def test_an_empty_answer_reports_nothing():
    assert inexact([]) == []
