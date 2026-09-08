"""An id becomes a quoted identifier, a string literal and a file name, so it is refused early.

Every one of these was found by attacking the generators rather than by reading them. A quote in
an event id closes the literal a measure check puts it in and comments out the rest, so the check
reports nothing wrong for ever -- the failure this repository cares most about, an assertion that
cannot fail. A slash in an entity id makes `adss dar generate` write a check outside `checks/`.

Neither is an escalation: whoever can edit these files can already run arbitrary SQL through the
engine, which compiles a mapping's expressions verbatim. They are refused because a name that
means one thing in a file and another in SQL is a bug waiting for an unlucky source.
"""

from pathlib import Path

import pytest

from adss.mapping import MappingError, read_mapping
from adss.model import ModelError, read_model
from adss.names import unsafe
from adss.uss import UssError, read_uss

FIXTURES = Path(__file__).parent / "fixtures"
DAB = FIXTURES / "dab"


@pytest.mark.parametrize(
    "value",
    ["ORDER", "ORDER_LINE", "a", "A1_b2", "PLACED_ORDERS_COUNT"],
)
def test_a_name_this_system_can_spell_is_accepted(value: str):
    assert not unsafe(value)


@pytest.mark.parametrize(
    "value",
    [
        "O' AND 1 = 0 --",  # closes a literal in a generated check
        '"quoted"',
        "../../../tmp/PWNED",  # leaves checks/ when written to a file
        "with space",
        "with-hyphen",  # a file name is fine; an unquoted SQL identifier is not
        "1_leading_digit",
        "",
        "ünicode",
    ],
)
def test_a_name_that_would_change_meaning_somewhere_is_refused(value: str):
    assert unsafe(value)


def test_an_entity_id_that_is_a_path_is_refused_by_the_model_reader():
    with pytest.raises(ModelError, match="not a name this system can spell"):
        read_model(DAB / "bad_unsafe_entity.yaml")


def test_an_event_id_that_closes_a_string_literal_is_refused_by_the_declarations_reader():
    model = read_model(DAB / "model.yaml")
    with pytest.raises(UssError, match="not a name this system can spell"):
        read_uss(DAB / "bad_unsafe_event.yaml", model)


def test_an_entity_id_that_is_a_path_is_refused_by_the_mapping_reader():
    with pytest.raises(MappingError, match="not a name this system can spell"):
        read_mapping(FIXTURES / "mappings" / "bad_unsafe_entity.yaml")


def test_every_id_in_this_repository_is_one_this_system_can_spell():
    """The rule is only worth having if the repository already obeys it."""
    from adss.project import Project

    project = Project.discover(Path(__file__).resolve().parent)
    model = read_model(project.model)
    for entity in model.entities:
        assert not unsafe(entity.id), entity.id
        for attribute in entity.attributes:
            assert not unsafe(attribute.id), attribute.id
    for edge in model.relationships:
        assert not unsafe(edge.name), edge.name
    for event in read_uss(project.uss, model).events:
        assert not unsafe(event.id), event.id
        for measure in event.measures:
            assert not unsafe(measure.id), measure.id
    for path in project.mapping_paths():
        assert not unsafe(read_mapping(path).entity_id), path


def test_a_relationships_ends_are_names_this_system_can_spell_too():
    """A relationship's id is composed from its source, its name and its target, and all three
    reach generated SQL. Validating only the name left the rule with a hole: it produced an
    unreadable KeyError further down rather than an injection, because an entity id with
    metacharacters is refused where the entity is declared -- but a rule about ids should
    cover the ids."""
    import yaml

    document = yaml.safe_load((DAB / "model.yaml").read_text())
    document["model"]["relationships"][0]["source_entity_id"] = "CHILD' AND 1 = 0 --"
    broken = DAB.parent / "unsafe_edge_end.yaml"
    broken.write_text(yaml.safe_dump(document))
    try:
        with pytest.raises(ModelError, match="not a name this system can spell"):
            read_model(broken)
    finally:
        broken.unlink()
