"""A question is a data file. The runner asserts over it and names nothing. ADR 0005."""

from pathlib import Path

import pytest

from adss.model import read_model
from adss.project import Project
from adss.question import MEASURE, QuestionError, check_question, read_question, read_questions
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


def test_an_id_that_would_not_survive_being_a_file_name_is_refused(tmp_path: Path):
    """The id names a screenshot and an environment variable, not just a row in a table.

    The empty one is the dangerous case rather than the obviously-broken one: the page reads
    an empty selection as "show everything", so the record of what was delivered for this
    question would be a picture of every question, and nothing would look wrong.
    """
    for bad in ("", "../escape", "q 1", "Q01/answer"):
        directory = tmp_path / "01-a-question"
        directory.mkdir(exist_ok=True)
        source = FIXTURES / "questions" / "01-a-neutral-question"
        (directory / "staged.sql").write_text((source / "staged.sql").read_text())
        (directory / "uss.sql").write_text((source / "uss.sql").read_text())
        (directory / "question.md").write_text(
            (source / "question.md").read_text().replace("id: qn1", f"id: '{bad}'", 1)
        )
        with pytest.raises(QuestionError, match="usable question id"):
            read_question(directory)


def variant(tmp_path: Path, name: str, **files: str) -> Path:
    """The neutral question with some of its files replaced. Every refusal below needs one."""
    directory = tmp_path / name
    directory.mkdir()
    for stem in ("question.md", "staged.sql", "uss.sql"):
        (directory / stem).write_text(
            files.get(stem.replace(".", "_"), (NEUTRAL / stem).read_text())
        )
    return directory


def answering(sql: str) -> str:
    return f"SELECT cal.month_label AS month_label, {sql} FROM dar__uss._bridge AS b ORDER BY 1"


def test_an_answer_query_that_aggregates_a_peripherals_column_is_refused(tmp_path: Path):
    """ADR 0012. The bridge protects the measure column and not the attribute beside it.

    One join and one sum, which is the shape every question here already writes -- and over a
    bridge with two rows per order it returns twice the truth with nothing to show for it.
    """
    directory = variant(tmp_path, "01-trapped", uss_sql=answering("sum(p.parent_size) AS n"))
    with pytest.raises(QuestionError, match="parent_size"):
        check_question(read_question(directory), neutral_definitions())


def test_the_same_aggregate_over_a_measure_column_is_accepted(tmp_path: Path):
    """The rule has to leave the good query alone, or it is a rule against answering."""
    directory = variant(
        tmp_path, "01-fine", uss_sql=answering("sum(b._measure__parent__size_parents_units) AS n")
    )
    check_question(read_question(directory), neutral_definitions())


def test_a_cast_around_the_aggregate_does_not_hide_it(tmp_path: Path):
    """Every answer query in this repository wraps its sum in a cast, so a check that reads
    only the top of the expression would pass all of them and catch none."""
    directory = variant(
        tmp_path, "01-cast", uss_sql=answering("cast(sum(p.parent_size) AS DOUBLE) AS n")
    )
    with pytest.raises(QuestionError, match="parent_size"):
        check_question(read_question(directory), neutral_definitions())


def test_a_windowed_aggregate_over_a_peripherals_column_is_refused(tmp_path: Path):
    """A sum over a window multiplies exactly as a grouped one does."""
    directory = variant(tmp_path, "01-window", uss_sql=answering("sum(p.parent_size) OVER () AS n"))
    with pytest.raises(QuestionError, match="parent_size"):
        check_question(read_question(directory), neutral_definitions())


def test_counting_the_bridges_rows_is_refused(tmp_path: Path):
    """count(*) counts measurement events, which is not the number anybody meant to ask for.

    Two events on one entity and the count doubles; a finer stage and it changes grain. The
    measure exists so the question does not have to know which.
    """
    directory = variant(tmp_path, "01-counting", uss_sql=answering("count(*) AS n"))
    with pytest.raises(QuestionError, match="counts measurement events"):
        check_question(read_question(directory), neutral_definitions())


def test_the_control_query_may_aggregate_whatever_it_likes(tmp_path: Path):
    """It reads the source, where there is no bridge and no measure to aggregate instead."""
    directory = variant(
        tmp_path,
        "01-source",
        staged_sql=(
            "SELECT strftime(p.parent_on, '%Y-%m') AS month_label, sum(p.parent_size) AS n "
            "FROM das__staged.parent__current AS p GROUP BY 1 ORDER BY month_label"
        ),
    )
    check_question(read_question(directory), neutral_definitions())


def test_an_answer_query_the_engine_cannot_parse_is_refused(tmp_path: Path):
    """Otherwise it is refused at build time, after the page has been written against it."""
    directory = variant(tmp_path, "01-garbled", uss_sql="SELECT FROM dar__uss ORDER BY )(")
    with pytest.raises(QuestionError, match="does not parse"):
        check_question(read_question(directory), neutral_definitions())


def test_every_measure_column_starts_with_the_prefix_the_refusal_looks_for():
    """The refusal carries the prefix as a literal, beside the layer names it already carries.

    A rename in the generator would otherwise leave it refusing every answer in the repository,
    or -- worse -- accepting an aggregate over anything at all.
    """
    model = read_model(PROJECT.model)
    for _, _, column in read_uss(PROJECT.uss, model).measure_columns():
        assert column.startswith(MEASURE), column


def joining(sql: str, alias: str) -> str:
    return (
        f"SELECT cal.month_label AS month_label, {sql} FROM dar__uss._bridge AS b "
        f"INNER JOIN dar__uss.parent AS {alias} ON b.parent_key = {alias}.parent_key ORDER BY 1"
    )


def test_a_table_aliased_like_a_measure_does_not_launder_a_peripherals_column(tmp_path: Path):
    """The bridge protects a COLUMN, so only the last part of a reference decides.

    An alias is the one part of a reference its author picks freely, so testing the whole
    dotted name let `sum(_measure__x.parent_size)` through -- the exact aggregate the rule
    exists to refuse, wearing a name it chose for itself.
    """
    directory = variant(
        tmp_path,
        "01-laundered",
        uss_sql=joining("sum(_measure__x.parent_size) AS n", "_measure__x"),
    )
    with pytest.raises(QuestionError, match="parent_size"):
        check_question(read_question(directory), neutral_definitions())


def test_a_measure_column_is_still_accepted_however_its_table_is_aliased(tmp_path: Path):
    directory = variant(
        tmp_path,
        "01-qualified",
        uss_sql=joining("sum(b._measure__parent__size_parents_units) AS n", "p"),
    )
    check_question(read_question(directory), neutral_definitions())


def test_an_unqualified_measure_column_is_accepted(tmp_path: Path):
    """One name part and no qualifier at all, which is the same code path with nothing to trim."""
    directory = variant(
        tmp_path,
        "01-bare",
        uss_sql=answering("sum(_measure__parent__size_parents_units) AS n"),
    )
    check_question(read_question(directory), neutral_definitions())


def test_an_answer_query_nested_beyond_what_python_can_walk_is_refused_not_crashed(tmp_path: Path):
    """700 nested calls parse and used to raise RecursionError out of the checker.

    Nobody writes this. It is here because the walk is over a tree whose depth is the engine's
    business rather than ours, and an unhandled RecursionError is a refusal nobody can read.
    """
    nested = "abs(" * 700 + "1" + ")" * 700
    directory = variant(tmp_path, "01-deep", uss_sql=answering(f"{nested} AS month_label"))
    check_question(read_question(directory), neutral_definitions())


def test_a_question_the_build_would_refuse_is_a_finding_and_not_a_traceback(tmp_path: Path):
    """`adss check` runs the refusals now, so one has to arrive as a finding like any other.

    The refusals were reachable from this suite alone, which meant `adss check` executed SQL
    nothing had refused -- and a question can be added to a working tree without pytest running.
    """
    from adss.checks import answerable_finding

    good = answerable_finding(read_question(NEUTRAL), neutral_definitions())
    assert good.passed and good.check == "qn1: answerable as written"

    directory = variant(tmp_path, "01-trapped-again", uss_sql=answering("sum(p.parent_size) AS n"))
    bad = answerable_finding(read_question(directory), neutral_definitions())
    assert not bad.passed
    assert "parent_size" in bad.detail, "the finding says what was wrong, not that something was"


def test_every_question_in_this_repository_is_answerable_at_build_time_too():
    """The same assertion the build makes, so a regression fails here rather than in CI."""
    from adss.checks import answerable_finding

    defined = project_definitions()
    for question in read_questions(PROJECT.questions):
        finding = answerable_finding(question, defined)
        assert finding.passed, finding.detail


def test_a_ranking_window_is_not_an_aggregate(tmp_path: Path):
    """`row_number`, `rank`, `ntile` and `lag` are all in the engine's aggregate list, so
    reading that list alone refused "rank the months" -- an ordinary shape for an answer -- and
    told its author to look for a fan-out that is not there. A ranking window multiplies
    nothing; only a windowed AGGREGATE does, and the engine's own node type says which."""
    directory = variant(
        tmp_path,
        "01-ranked",
        uss_sql=answering(
            "row_number() OVER (ORDER BY b._measure__parent__size_parents_units) AS month_label"
        ),
    )
    check_question(read_question(directory), neutral_definitions())


def test_a_windowed_aggregate_over_a_peripherals_column_is_still_refused(tmp_path: Path):
    directory = variant(
        tmp_path, "01-windowed", uss_sql=joining("sum(p.parent_size) OVER () AS n", "p")
    )
    with pytest.raises(QuestionError, match="parent_size"):
        check_question(read_question(directory), neutral_definitions())


@pytest.mark.parametrize(
    "expression",
    [
        "sum(p.parent_size * b._measure__parent__size_parents_units) AS n",
        "sum(b._measure__parent__size_parents_units * p.parent_size) AS n",
    ],
)
def test_a_peripherals_column_multiplied_into_a_measure_is_refused(tmp_path: Path, expression: str):
    """Both spellings, because the walk's column order is not the source order and the refusal
    must not depend on which operand it happens to reach first."""
    directory = variant(tmp_path, "01-mixed", uss_sql=joining(expression, "p"))
    with pytest.raises(QuestionError, match="parent_size"):
        check_question(read_question(directory), neutral_definitions())
