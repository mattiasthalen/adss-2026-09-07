"""A question is a data file. The runner asserts over it and names nothing. ADR 0005."""

from pathlib import Path

import pytest

from adss.model import read_model
from adss.project import Project
from adss.question import QuestionError, check_question, read_question, read_questions
from adss.uss import definitions, read_uss

FIXTURES = Path(__file__).parent / "fixtures"
NEUTRAL = FIXTURES / "questions" / "01-a-neutral-question"
PROJECT = Project.discover(Path(__file__).resolve().parent)


def neutral_definitions() -> dict[str, str]:
    model = read_model(FIXTURES / "dab" / "model.yaml")
    return definitions(model, read_uss(FIXTURES / "dab" / "uss.yaml", model))


def project_definitions() -> dict[str, str]:
    model = read_model(PROJECT.model)
    return definitions(model, read_uss(PROJECT.uss, model))


def test_a_question_carries_what_is_needed_to_answer_it_without_asking_anyone():
    question = read_question(NEUTRAL)
    assert question.persona and question.question.endswith("?")
    assert question.dimensions and question.staged_sql and question.uss_sql


def test_a_token_with_no_definition_behind_it_is_refused(tmp_path: Path):
    directory = tmp_path / "01-broken"
    directory.mkdir()
    text = (NEUTRAL / "question.md").read_text().replace("{{PARENT}}", "{{PARENT.ABSENT}}")
    (directory / "question.md").write_text(text)
    (directory / "staged.sql").write_text((NEUTRAL / "staged.sql").read_text())
    (directory / "uss.sql").write_text((NEUTRAL / "uss.sql").read_text())
    with pytest.raises(QuestionError, match="gap in the model"):
        check_question(read_question(directory), neutral_definitions())


def test_a_control_query_that_consults_the_layers_it_checks_is_refused(tmp_path: Path):
    directory = tmp_path / "01-cheating"
    directory.mkdir()
    (directory / "question.md").write_text((NEUTRAL / "question.md").read_text())
    (directory / "staged.sql").write_text("SELECT count(*) AS n FROM dar__uss._bridge AS b")
    (directory / "uss.sql").write_text((NEUTRAL / "uss.sql").read_text())
    with pytest.raises(QuestionError, match="independently"):
        check_question(read_question(directory), neutral_definitions())


def test_a_comment_naming_a_forbidden_layer_is_not_a_violation(tmp_path: Path):
    directory = tmp_path / "01-commented"
    directory.mkdir()
    (directory / "question.md").write_text((NEUTRAL / "question.md").read_text())
    (directory / "staged.sql").write_text(
        "-- deliberately does not read dar__uss\n" + (NEUTRAL / "staged.sql").read_text()
    )
    (directory / "uss.sql").write_text((NEUTRAL / "uss.sql").read_text())
    check_question(read_question(directory), neutral_definitions())


def test_every_question_in_this_repository_is_answerable():
    questions = read_questions(PROJECT.questions)
    assert questions, "a slice is accepted on a question; there are none"
    defined = project_definitions()
    for question in questions:
        check_question(question, defined)


def test_a_query_without_an_order_by_is_refused(tmp_path: Path):
    """The two answers are compared row by row, so an unordered pair can differ by luck."""
    directory = tmp_path / "01-unordered"
    directory.mkdir()
    (directory / "question.md").write_text((NEUTRAL / "question.md").read_text())
    (directory / "uss.sql").write_text((NEUTRAL / "uss.sql").read_text())
    (directory / "staged.sql").write_text(
        (NEUTRAL / "staged.sql").read_text().replace("ORDER BY month_label", "")
    )
    with pytest.raises(QuestionError, match="no ORDER BY"):
        check_question(read_question(directory), neutral_definitions())


def test_an_answer_query_that_reaches_past_the_star_schema_is_refused(tmp_path: Path):
    directory = tmp_path / "01-reaching"
    directory.mkdir()
    (directory / "question.md").write_text((NEUTRAL / "question.md").read_text())
    (directory / "staged.sql").write_text((NEUTRAL / "staged.sql").read_text())
    (directory / "uss.sql").write_text(
        "SELECT b.x AS month_label FROM dar__uss._bridge AS b, das__staged.parent AS p "
        "ORDER BY month_label"
    )
    with pytest.raises(QuestionError, match="reads the star schema and nothing else"):
        check_question(read_question(directory), neutral_definitions())


def test_a_control_query_that_skips_the_contract_is_refused(tmp_path: Path):
    directory = tmp_path / "01-raw"
    directory.mkdir()
    (directory / "question.md").write_text((NEUTRAL / "question.md").read_text())
    (directory / "uss.sql").write_text((NEUTRAL / "uss.sql").read_text())
    (directory / "staged.sql").write_text(
        "SELECT count(*) AS month_label FROM das__raw.parent AS p ORDER BY month_label"
    )
    with pytest.raises(QuestionError, match="__current"):
        check_question(read_question(directory), neutral_definitions())


def test_a_declared_dimension_the_answer_never_mentions_is_refused(tmp_path: Path):
    directory = tmp_path / "01-undelivered"
    directory.mkdir()
    (directory / "question.md").write_text(
        (NEUTRAL / "question.md")
        .read_text()
        .replace("dimensions: [_calendar.month_label]", "dimensions: [_calendar.year_number]")
    )
    (directory / "staged.sql").write_text((NEUTRAL / "staged.sql").read_text())
    (directory / "uss.sql").write_text((NEUTRAL / "uss.sql").read_text())
    with pytest.raises(QuestionError, match="front matter is what a reader trusts"):
        check_question(read_question(directory), neutral_definitions())
