import marimo

__generated_with = "0.24.0"
app = marimo.App(width="medium", app_title="ADSS")


@app.cell
def _():
    import os
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
        os,
        pathlib,
        pl,
        question_module,
        read_model,
        read_uss,
        Project,
    )


@app.cell
def _(os):
    # Which question this render is for. A slice is accepted on a picture of its question,
    # and by slice six one picture of everything would be neither readable nor attachable --
    # so the shot is taken once per question. Unset shows all of them, which is how a person
    # runs it.
    only = os.environ.get("ADSS_QUESTION", "").strip()

    def shown(q, element):
        """The element, or nothing at all, when this render is for another question.

        None rather than empty markdown: an empty cell still takes its vertical padding, and
        five of them leave a band of white above the question the picture is meant to be of.
        """
        return element if (not only or q.id == only) else None

    return only, shown


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
    questions = question_module.read_questions(project.questions)
    return defined, questions


@app.cell
def _(mo):
    # The palette this page draws with. One hue, light to dark, because the thing being
    # encoded is magnitude. Surfaces and ink from the same reference instance.
    SURFACE = "#fcfcfb"
    INK = "#0b0b0b"
    MUTED = "#898781"
    GRID = "#eceae4"
    SEQUENTIAL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

    mo.md(
        """
        # Data according to the requirements

        Every number on this page is read from `dar__uss` and from nothing else. The queries
        are the questions' own, so what you are looking at and what the build checks cannot
        disagree.
        """
    )
    return GRID, INK, MUTED, SEQUENTIAL, SURFACE


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
def _(answers, mo, questions, shown):
    q1 = questions[0]
    a1 = answers[q1.id]

    total = int(a1["placed_orders_count"].sum())
    months = a1["order_month"].n_unique()
    countries = a1["destination_country"].n_unique()

    shown(
        q1,
        mo.md(
            f"""
            ## {q1.question}

            *Asked by the {q1.persona.lower()}.*

            ## {total:,} orders placed

            across **{months}** months and **{countries}** destination countries,
            from **{a1["order_month"].min()}** to **{a1["order_month"].max()}**.
            """
        ),
    )
    return a1, countries, months, q1, total


@app.cell
def _(INK, MUTED, SEQUENTIAL, SURFACE, a1, alt, mo, pl, q1, shown):
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

    shown(q1, mo.ui.altair_chart(heatmap, chart_selection=False, legend_selection=False))
    return heatmap, order


@app.cell
def _(mo, q1, shown):
    shown(q1, mo.md("### What the words mean"))
    return


@app.cell
def _(glossary, q1, shown):
    shown(q1, glossary(q1))
    return


@app.cell
def _(a1, mo, q1, shown):
    shown(
        q1,
        mo.md(
            f"""
            ### The answer, row by row

            {len(a1):,} rows. Sorted the way the question asks for them.
            """
        ),
    )
    return


@app.cell
def _(a1, mo, q1, shown):
    shown(q1, mo.ui.table(a1, page_size=20, selection=None, show_column_summaries=False))
    return


@app.cell
def _(answers, mo, pl, questions, shown):
    q2 = questions[1]
    # altair cannot encode a DuckDB DECIMAL, and the measure is one by design -- freight is
    # money, so the star schema keeps it exact and the chart is where it becomes a float.
    a2 = answers[q2.id].with_columns(pl.col("freight_orders_amount").cast(pl.Float64))

    freight = a2["freight_orders_amount"].sum()
    quarters = a2["order_quarter"].n_unique()
    homes = a2["customer_country"].n_unique()

    shown(
        q2,
        mo.md(
            f"""
            ## {q2.question}

            *Asked by the {q2.persona.lower()}.*

            ## {freight:,.0f} paid in freight

            across **{quarters}** quarters and **{homes}** customer countries, from
            **{a2["order_quarter"].min()}** to **{a2["order_quarter"].max()}**. The
            customer's own country, which is not where the goods went.
            """
        ),
    )
    return a2, freight, homes, q2, quarters


@app.cell
def _(GRID, MUTED, SEQUENTIAL, SURFACE, a2, alt, mo, pl, q2, shown):
    # Where the money goes. One series, so length carries it and one colour is enough: a ramp
    # here would encode magnitude twice and say nothing the bar does not.
    by_country = (
        a2.group_by("customer_country")
        .agg(pl.col("freight_orders_amount").sum())
        .sort("freight_orders_amount", descending=True)
    )

    bars = (
        alt.Chart(by_country)
        .mark_bar(color=SEQUENTIAL[4], cornerRadiusEnd=4)
        .encode(
            x=alt.X(
                "freight_orders_amount:Q",
                title=None,
                axis=alt.Axis(labelColor=MUTED, format=",.0f", gridColor=GRID),
            ),
            y=alt.Y("customer_country:N", title=None, sort="-x", axis=alt.Axis(labelColor=MUTED)),
            tooltip=[
                alt.Tooltip("customer_country:N", title="Customer country"),
                alt.Tooltip("freight_orders_amount:Q", title="Freight", format=",.2f"),
            ],
        )
        .properties(height=alt.Step(17), width="container", background=SURFACE)
        .configure_view(stroke=None)
        .configure_axis(domainColor="#c3c2b7", tickColor="#c3c2b7", labelFontSize=11)
    )

    shown(q2, mo.ui.altair_chart(bars, chart_selection=False, legend_selection=False))
    return bars, by_country


@app.cell
def _(mo, q2, shown):
    shown(
        q2,
        mo.md(
            """
            ### And whether it is moving

            The six countries with the most freight, quarter by quarter. Small multiples
            rather than six lines on one axis: six colours would have to be told apart before
            the shapes could be compared, and the shapes are the question.
            """
        ),
    )
    return


@app.cell
def _(GRID, MUTED, SEQUENTIAL, SURFACE, a2, alt, by_country, mo, pl, q2, shown):
    top = by_country["customer_country"].head(6).to_list()
    trend = a2.filter(pl.col("customer_country").is_in(top))

    lines = (
        alt.Chart(trend)
        .mark_line(color=SEQUENTIAL[4], strokeWidth=2, point=alt.OverlayMarkDef(size=26))
        .encode(
            x=alt.X("order_quarter:O", title=None, axis=alt.Axis(labelAngle=-90, labelColor=MUTED)),
            y=alt.Y(
                "freight_orders_amount:Q",
                title=None,
                axis=alt.Axis(labelColor=MUTED, format=",.0f", gridColor=GRID),
            ),
            facet=alt.Facet(
                "customer_country:N",
                columns=3,
                title=None,
                sort=top,
                header=alt.Header(labelColor=MUTED, labelFontSize=12, labelAnchor="start"),
            ),
            tooltip=[
                alt.Tooltip("customer_country:N", title="Customer country"),
                alt.Tooltip("order_quarter:O", title="Quarter"),
                alt.Tooltip("freight_orders_amount:Q", title="Freight", format=",.2f"),
            ],
        )
        .properties(width=200, height=105, background=SURFACE)
        .configure_view(stroke=None)
        .configure_axis(domainColor="#c3c2b7", tickColor="#c3c2b7", labelFontSize=10)
    )

    shown(q2, mo.ui.altair_chart(lines, chart_selection=False, legend_selection=False))
    return lines, top, trend


@app.cell
def _(mo, q2, shown):
    shown(q2, mo.md("### What the words mean"))
    return


@app.cell
def _(glossary, q2, shown):
    shown(q2, glossary(q2))
    return


@app.cell
def _(a2, mo, q2, shown):
    shown(
        q2,
        mo.md(
            f"""
            ### The answer, row by row

            {len(a2):,} rows. Sorted the way the question asks for them.
            """
        ),
    )
    return


@app.cell
def _(a2, mo, q2, shown):
    shown(q2, mo.ui.table(a2, page_size=20, selection=None, show_column_summaries=False))
    return


if __name__ == "__main__":
    app.run()
