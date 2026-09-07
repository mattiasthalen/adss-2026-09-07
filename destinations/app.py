import marimo

__generated_with = "0.24.0"
app = marimo.App(width="medium", app_title="ADSS")


@app.cell
def _():
    import pathlib

    import altair as alt
    import duckdb
    import marimo as mo
    import polars as pl

    import adss.question as question_module
    from adss.model import read_model
    from adss.project import Project
    from adss.uss import definitions, read_uss

    return (
        alt,
        definitions,
        duckdb,
        mo,
        pathlib,
        pl,
        question_module,
        read_model,
        read_uss,
        Project,
    )


@app.cell
def _(Project, pathlib):
    # Anchored on this file, never on the working directory: an export or a screenshot is
    # usually run from somewhere else, and a relative path would break silently.
    project = Project.discover(pathlib.Path(__file__).parent)
    return (project,)


@app.cell
def _(duckdb, project):
    # Read-only. A destination holding a writable handle blocks the next build, and the
    # build is the thing that cannot be worked around. docs/conventions.md section 9.
    warehouse = duckdb.connect(str(project.warehouse), read_only=True)
    return (warehouse,)


@app.cell
def _(definitions, project, question_module, read_model, read_uss):
    model = read_model(project.model)
    uss = read_uss(project.uss, model)
    defined = definitions(model, uss)
    questions = question_module.read_questions(project.root / "docs" / "questions")
    return defined, questions


@app.cell
def _(mo):
    # The palette this page draws with. One hue, light to dark, because the thing being
    # encoded is magnitude. Surfaces and ink from the same reference instance.
    SURFACE = "#fcfcfb"
    INK = "#0b0b0b"
    MUTED = "#898781"
    SEQUENTIAL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

    mo.md(
        """
        # Data according to the requirements

        Every number on this page is read from `dar__uss` and from nothing else. The queries
        are the questions' own, so what you are looking at and what the build checks cannot
        disagree.
        """
    )
    return INK, MUTED, SEQUENTIAL, SURFACE


@app.cell
def _(defined, mo, questions, warehouse):
    answers = {q.id: warehouse.execute(q.uss_sql).pl() for q in questions}

    def glossary(q):
        return mo.md(
            "\n".join(
                f"- **{token}** — {defined[token]}" for token in q.defines if token in defined
            )
        )

    return answers, glossary


@app.cell
def _(answers, mo, questions):
    q1 = questions[0]
    a1 = answers[q1.id]

    total = int(a1["placed_orders_count"].sum())
    months = a1["order_month"].n_unique()
    countries = a1["destination_country"].n_unique()

    mo.md(
        f"""
        ## {q1.question}

        *Asked by the {q1.persona.lower()}.*

        ## {total:,} orders placed

        across **{months}** months and **{countries}** destination countries,
        from **{a1["order_month"].min()}** to **{a1["order_month"].max()}**.
        """
    )
    return a1, countries, months, q1, total


@app.cell
def _(INK, MUTED, SEQUENTIAL, SURFACE, a1, alt, mo, pl):
    # Countries ordered by how much they order, so the eye starts where the demand is.
    order = (
        a1.group_by("destination_country")
        .agg(pl.col("placed_orders_count").sum())
        .sort("placed_orders_count", descending=True)["destination_country"]
        .to_list()
    )

    heatmap = (
        alt.Chart(a1)
        .mark_rect(stroke=SURFACE, strokeWidth=2, cornerRadius=2)
        .encode(
            x=alt.X("order_month:O", title=None, axis=alt.Axis(labelAngle=-90, labelColor=MUTED)),
            y=alt.Y(
                "destination_country:N",
                title=None,
                sort=order,
                axis=alt.Axis(labelColor=MUTED),
            ),
            color=alt.Color(
                "placed_orders_count:Q",
                title="Orders placed",
                scale=alt.Scale(range=SEQUENTIAL),
                legend=alt.Legend(orient="top", direction="horizontal", gradientLength=180),
            ),
            tooltip=[
                alt.Tooltip("destination_country:N", title="Destination"),
                alt.Tooltip("order_month:O", title="Month"),
                alt.Tooltip("placed_orders_count:Q", title="Orders placed"),
            ],
        )
        .properties(height=alt.Step(18), width="container", background=SURFACE)
        .configure_view(stroke=None)
        .configure_axis(domainColor="#c3c2b7", tickColor="#c3c2b7", grid=False, labelFontSize=11)
        .configure_legend(labelColor=INK, titleColor=INK, titleFontSize=11, labelFontSize=11)
    )

    mo.ui.altair_chart(heatmap, chart_selection=False, legend_selection=False)
    return heatmap, order


@app.cell
def _(glossary, mo, q1):
    mo.md("### What the words mean")
    return


@app.cell
def _(glossary, q1):
    glossary(q1)
    return


@app.cell
def _(a1, mo):
    mo.md(
        f"""
        ### The answer, row by row

        {len(a1):,} rows. Sorted the way the question asks for them.
        """
    )
    return


@app.cell
def _(a1, mo):
    mo.ui.table(a1, page_size=20, selection=None, show_column_summaries=False)
    return


if __name__ == "__main__":
    app.run()
