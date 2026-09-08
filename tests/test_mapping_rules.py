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
        # A bracket inside a string literal is not a bracket. A scan that believed otherwise
        # would never find the call's end, and would refuse this for reaching beyond its row.
        "extract(DAY FROM concat(a, '('))",
        # The literal bracket now comes BEFORE the keyword, which is the only arrangement
        # that can push the scan off the call's own depth and lose the keyword entirely.
        "trim(BOTH '(' FROM s)",
        # And "from" inside an identifier is not the keyword. Blanking that one would leave
        # the real one standing, and refuse this for the same wrong reason.
        "substring(dfrom FROM 1 FOR 2)",
        # And "from" as the START of an earlier identifier, which is the other half of the
        # same mistake: blank that one and the real keyword is still standing.
        "substring(fromage FROM 1 FOR 2)",
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


def test_an_expression_split_by_yaml_flow_style_is_refused():
    """A flow mapping treats the commas inside a function call as its own separators.

    `{id: X, transformation_expression: f('a', b, c)}` parses to the expression `f('a'` plus
    two keys named `b` and `c)`, with no YAML error and nothing else to notice: the truncated
    expression reads its own row, so M5 accepts it, and the engine is the first thing to
    complain -- about SQL nobody wrote. It has now cost two slices, so it is refused here by
    the one signature it always leaves, which is a key the schema does not have.
    """
    with pytest.raises(MappingError) as refused:
        check_mapping(read_mapping(FIXTURES / "bad_split_expression.yaml"))
    assert "flow style" in str(refused.value)
    assert "'b'" in str(refused.value) and "'c)'" in str(refused.value), (
        "the message names the stray keys, which is what tells a reader where to look"
    )


@pytest.mark.parametrize(
    "expression",
    [
        "extract(DAY FROM (SELECT max(x) FROM other))",
        "trim(BOTH x FROM (SELECT y FROM elsewhere))",
        "substring(a FROM 1 FOR (SELECT n FROM sizes))",
        "extract(DAY FROM a) + (SELECT 1 FROM t)",
        "substring(a FROM 1 FOR 2) JOIN b",
        "extract(DAY FROM concat(a, '(') ) + (SELECT 1 FROM t)",
        "trim(a) FROM elsewhere",
        "extract(DAY FROM a) , b FROM elsewhere",
    ],
)
def test_a_reach_hidden_inside_a_from_taking_function_is_still_refused(expression: str):
    """The FROM those functions spell is syntax; everything else in them is not.

    Excusing the whole argument list would excuse the one thing M5 exists to stop -- a reach
    into another table -- by hiding it in the one place the checker had stopped looking. The
    The last two cases are why the blanking is positional. One has a bracket inside a string
    literal, which no paren-counting scan can survive; the other puts a genuine reach BEFORE
    the function, where a scanner that blanked the nearest FROM rather than the following one
    would erase the wrong token and let it through.
    """
    assert reaching(expression), f"{expression} reaches beyond its row"
