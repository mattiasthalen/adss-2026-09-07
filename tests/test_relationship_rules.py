"""M6, which the engine enforces not at all and whose three failures are all silent.

A mis-spelled `source_table` is skipped without a word; a differently shaped target expression
produces pairs that join to nothing; and a relationship declared in the model but in no mapping
produces no pairs at all. None of the three is reported at deploy, at execute, or by either of a
question's acceptance queries -- the inherited key is simply null everywhere, which looks like
data rather than like a defect. Conventions section 1.4, ADR 0006.
"""

from dataclasses import replace
from pathlib import Path

import pytest

from adss.mapping import Mapping, MappingError, check_relationships, key_shape, read_mapping
from adss.model import read_model

FIXTURES = Path(__file__).parent / "fixtures" / "mappings"
NEUTRAL = Path(__file__).parent / "fixtures" / "dab" / "model.yaml"
ROOT = Path(__file__).resolve().parent.parent

GOOD = ("good", "good_child", "good_neighbour")


def _set(*names: str) -> list[Mapping]:
    return [read_mapping(FIXTURES / f"{name}.yaml") for name in names]


def test_a_conforming_set_of_mappings_passes():
    check_relationships(_set(*GOOD), read_model(NEUTRAL))


@pytest.mark.parametrize(
    ("broken", "complaint"),
    [
        ("bad_relationship_id", "CHILD_POINTS_AT_PARENT"),
        ("bad_relationship_table", "byte-identical"),
        ("bad_relationship_target", "shaped"),
    ],
)
def test_each_way_a_relationship_goes_wrong_in_silence_is_refused(broken: str, complaint: str):
    mappings = _set("good", broken, "good_neighbour")
    with pytest.raises(MappingError) as refused:
        check_relationships(mappings, read_model(NEUTRAL))
    assert "M6" in str(refused.value), "a refusal names the rule so it can be looked up"
    assert complaint in str(refused.value)


def test_a_relationship_the_model_declares_and_no_mapping_loads_is_refused():
    # The model says the edge exists and nothing produces a single pair for it. Every join
    # along it returns null, which reads as "these rows have no parent" rather than as a gap.
    with pytest.raises(MappingError) as refused:
        check_relationships(_set("good", "good_neighbour"), read_model(NEUTRAL))
    assert "M6" in str(refused.value)
    assert "CHILD_POINTS_AT_PARENT" in str(refused.value)


def test_a_relationship_no_model_declares_is_refused():
    # The reverse gap. The engine builds the pair object from the mapping alone, so this one
    # works -- and is an edge nothing explains, which B8 forbids more firmly than it forbids
    # a broken one.
    model = read_model(NEUTRAL)
    without = replace(
        model,
        relationships=tuple(r for r in model.relationships if r.name != "POINTS_AT"),
    )
    with pytest.raises(MappingError) as refused:
        check_relationships(_set(*GOOD), without)
    assert "M6" in str(refused.value)
    assert "CHILD_POINTS_AT_PARENT" in str(refused.value)


def test_the_key_shape_is_compared_and_not_the_column_name():
    # M6 is about the shape of the expression, not the spelling of the column. A foreign key
    # is routinely named differently from the primary key it points at, and refusing that
    # would make the rule unusable. What is refused is one side casting and the other not,
    # because then the two VARCHARs genuinely differ.
    check_relationships(
        _set("good", "good_child_renamed_key", "good_neighbour"), read_model(NEUTRAL)
    )


def test_every_relationship_in_this_repository_conforms():
    mappings = [read_mapping(path) for path in sorted((ROOT / "dab" / "mappings").glob("*.yaml"))]
    assert mappings, "there are no mappings to check"
    check_relationships(mappings, read_model(ROOT / "dab" / "model.yaml"))


def test_every_mapping_that_declares_an_edge_is_checked_and_not_only_the_last():
    """An entity loaded from a second source declares the same edge in a second mapping.

    Keying the check on the edge id alone would validate whichever mapping came last and let
    the other's silent-skip through -- which is the whole failure M6 exists to catch, arriving
    by way of the check that was supposed to catch it.
    """
    good, broken = _set("good_child")[0], _set("bad_relationship_table")[0]
    for order in ((good, broken), (broken, good)):
        with pytest.raises(MappingError) as refused:
            check_relationships([*_set("good", "good_neighbour"), *order], read_model(NEUTRAL))
        assert "byte-identical" in str(refused.value)


def test_a_function_is_part_of_a_key_expression_shape_and_not_a_name_to_be_stripped():
    """lpad(x, 5, '0') and a bare x produce different keys, so they are different shapes.

    The rule exists to stop pairs that join to nothing, and a function changes the value as
    surely as a cast does -- so anonymising its name would be exactly the wrong half to drop.
    """
    assert key_shape("customer_id") != key_shape("lpad(customer_id, 5, '0')")
    assert key_shape("lpad(a, 5, '0')") == key_shape("lpad(b, 5, '0')"), "the column may differ"
    assert key_shape("lpad(a, 5, '0')") != key_shape("rpad(a, 5, '0')"), "the function may not"
    assert key_shape("cast(a AS VARCHAR)") != key_shape("a"), "and neither may the cast"
