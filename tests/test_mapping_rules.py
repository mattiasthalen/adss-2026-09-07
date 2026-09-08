"""The engine accepts several kinds of wrong mapping without complaint. These refuse them.

Two of the seven are not style: FULL against a multi-row-per-key source duplicates silently
and every presentation view hides it, and a second primary key means alternate identifiers
rather than a composite key, which cannot be undone once loaded. Conventions section 1.4.
"""

from pathlib import Path

import pytest

from adss.mapping import MappingError, check_mapping, reaching, read_mapping

FIXTURES = Path(__file__).parent / "fixtures" / "mappings"
PROJECT_MAPPINGS = Path(__file__).resolve().parent.parent / "dab" / "mappings"


def test_a_conforming_mapping_passes():
    check_mapping(read_mapping(FIXTURES / "good.yaml"))


@pytest.mark.parametrize(
    ("fixture", "rule", "complaint"),
    [
        ("bad_reads_raw", "M1", "das__staged"),
        ("bad_two_keys", "M2", "alternate identifiers"),
        ("bad_full_strategy", "M3", "FULL_LOG"),
        ("bad_wrong_clock", "M4", "extracted_at"),
        ("bad_reaching_expression", "M5", "reaches beyond its row"),
        ("bad_no_attributes", "M7", "at least one attribute"),
    ],
)
def test_each_rule_refuses_what_it_exists_to_refuse(fixture: str, rule: str, complaint: str):
    with pytest.raises(MappingError) as refused:
        check_mapping(read_mapping(FIXTURES / f"{fixture}.yaml"))
    assert rule in str(refused.value), "a refusal names the rule so it can be looked up"
    assert complaint in str(refused.value)


def test_every_mapping_in_this_repository_conforms():
    written = sorted(PROJECT_MAPPINGS.glob("*.yaml"))
    assert written, "there are no mappings to check"
    for path in written:
        check_mapping(read_mapping(path))


@pytest.mark.parametrize(
    "expression",
    [
        "date_diff('day', a, b)",
        "cast(b - a AS INTEGER)",
        "extract(DAY FROM (b - a))",
        "round(a * b * (1 - c), 4)",
        "coalesce(a, b)",
    ],
)
def test_arithmetic_and_functions_over_one_row_are_permitted(expression: str):
    """M5 permits an expression that reads its own row, and arithmetic over that row is one.

    `extract(DAY FROM ...)` is the case that matters: it is the natural idiom for this, and the
    checker used to refuse it because the pattern matched the bare word FROM inside the
    expression -- then told the reader it reached beyond its row, which it does not. A refusal
    whose reason is wrong sends someone looking for a problem that is not there. ADR 0007.
    """
    assert not reaching(expression), f"{expression} reads its own row"


@pytest.mark.parametrize(
    "expression",
    [
        "(SELECT max(x) FROM other)",
        "sum(a)",
        "a JOIN b",
        "count(*) OVER (PARTITION BY a)",
        "max(a) FROM elsewhere",
    ],
)
def test_an_expression_that_leaves_its_row_is_still_refused(expression: str):
    assert reaching(expression), f"{expression} does not read its own row"
