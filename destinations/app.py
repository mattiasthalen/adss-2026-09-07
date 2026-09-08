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
    # The ones actually being asked, in the order they were asked. A draft is unfinished and a
    # superseded question is not asked any more; `adss check` skips both, and a page that
    # rendered them would be answering something nobody is asking. Indexed positionally below,
    # so this also keeps a new draft directory from renumbering every page.
    asked = tuple(
        q
        for q in question_module.read_questions(project.questions)
        if q.status not in (question_module.Status.DRAFT, question_module.Status.SUPERSEDED)
    )
    return defined, asked


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
def _(asked, defined, mo, warehouse):
    answers = {q.id: warehouse.execute(q.uss_sql).pl() for q in asked}

    def glossary(q):
        return mo.md(
            "\n".join(
                f"- **{token}** — {defined[token]}" for token in q.defines if token in defined
            )
        )

    return answers, glossary


@app.cell
def _(answers, asked, mo, shown):
    q1 = asked[0]
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
        # Ties broken by name. Without it the order is whatever the sort happened to
        # produce, so the picture a slice was accepted on changes between runs from identical
        # data -- and a reviewer diffing the PNG cannot tell a re-sorted tie from a new answer.
        .sort(["placed_orders_count", "destination_country"], descending=[True, False])[
            "destination_country"
        ]
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
def _(answers, asked, mo, pl, shown):
    q2 = asked[1]
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


@app.cell
def _(a1, answers, asked, mo, pl, shown):
    q3_placed = int(a1["placed_orders_count"].sum())
    q3 = asked[2] if len(asked) > 2 else asked[-1]
    a3 = answers[q3.id].with_columns(
        pl.col("ship_lag_orders_days").cast(pl.Float64),
        # The division the question deliberately does not store. Conventions section 2: an
        # average of averages is wrong at every grain but the one it was computed at, so the
        # answer carries two additive measures and the arithmetic happens once, here.
        (pl.col("ship_lag_orders_days") / pl.col("shipped_orders_count"))
        .cast(pl.Float64)
        .alias("days_per_order"),
    )

    shipped = int(a3["shipped_orders_count"].sum())
    waited = float(a3["ship_lag_orders_days"].sum())
    # Read from the data, so it can be zero, and a page that divides by it would take the
    # whole render down rather than this one question.
    each = f"{waited / shipped:.1f} days each" if shipped else "nothing shipped"
    # Counted rather than asserted. Every other number on this page is computed, and a
    # hardcoded one on the artefact a slice is accepted on goes quietly wrong on the next load.
    unshipped = int(q3_placed - shipped) if q3_placed else 0

    shown(
        q3,
        mo.md(
            f"""
            ## {q3.question}

            *Asked by the {q3.persona.lower()}.*

            ## {shipped:,} orders out, {each}

            on average across **{len(a3)}** months. **{unshipped}** orders are missing from
            this entirely, because they have never shipped -- they are absent rather than
            counted as having taken no time.
            """
        ),
    )
    return a3, each, q3, q3_placed, shipped, unshipped, waited


@app.cell
def _(GRID, MUTED, SEQUENTIAL, SURFACE, a3, alt, mo, q3, shown):
    # Two measures, two charts, one shared x. Never two y-scales on one chart: a dual axis
    # invents a correlation by choosing where the two lines cross, and the whole point here is
    # to see whether volume and speed actually move together.
    #
    # Two separate charts rather than one vconcat, because mo.ui.altair_chart renders a
    # concatenated spec as nothing at all -- the spec builds, the widget builds, and the page
    # comes back with a gap. A facet works; a concat does not.
    volume = (
        alt.Chart(a3)
        .mark_bar(color=SEQUENTIAL[2], cornerRadiusEnd=3)
        .encode(
            x=alt.X(
                "shipping_month:O", title=None, axis=alt.Axis(labelAngle=-90, labelColor=MUTED)
            ),
            y=alt.Y(
                "shipped_orders_count:Q",
                title="orders shipped",
                axis=alt.Axis(labelColor=MUTED, titleColor=MUTED, gridColor=GRID),
            ),
            tooltip=[
                alt.Tooltip("shipping_month:O", title="Shipped in"),
                alt.Tooltip("shipped_orders_count:Q", title="Orders shipped"),
                alt.Tooltip("days_per_order:Q", title="Days per order", format=".2f"),
            ],
        )
        .properties(height=150, width="container", background=SURFACE)
        .configure_view(stroke=None)
        .configure_axis(domainColor="#c3c2b7", tickColor="#c3c2b7", labelFontSize=11)
    )

    shown(q3, mo.ui.altair_chart(volume, chart_selection=False, legend_selection=False))
    return (volume,)


@app.cell
def _(MUTED, GRID, SEQUENTIAL, SURFACE, a3, alt, mo, q3, shown):
    speed = (
        alt.Chart(a3)
        .mark_line(color=SEQUENTIAL[5], strokeWidth=2, point=alt.OverlayMarkDef(size=28))
        .encode(
            x=alt.X(
                "shipping_month:O", title=None, axis=alt.Axis(labelAngle=-90, labelColor=MUTED)
            ),
            y=alt.Y(
                "days_per_order:Q",
                title="days per order",
                scale=alt.Scale(zero=True),
                axis=alt.Axis(labelColor=MUTED, titleColor=MUTED, gridColor=GRID),
            ),
            tooltip=[
                alt.Tooltip("shipping_month:O", title="Shipped in"),
                alt.Tooltip("days_per_order:Q", title="Days per order", format=".2f"),
                alt.Tooltip("ship_lag_orders_days:Q", title="Days in total", format=",.0f"),
            ],
        )
        .properties(height=150, width="container", background=SURFACE)
        .configure_view(stroke=None)
        .configure_axis(domainColor="#c3c2b7", tickColor="#c3c2b7", labelFontSize=11)
    )

    shown(q3, mo.ui.altair_chart(speed, chart_selection=False, legend_selection=False))
    return (speed,)


@app.cell
def _(mo, q3, shown):
    shown(q3, mo.md("### What the words mean"))
    return


@app.cell
def _(glossary, q3, shown):
    shown(q3, glossary(q3))
    return


@app.cell
def _(a3, mo, q3, shown):
    shown(
        q3,
        mo.md(
            f"""
            ### The answer, row by row

            {len(a3):,} rows. The first two columns are what the question returns; the third is
            the division, done here rather than stored.
            """
        ),
    )
    return


@app.cell
def _(a3, mo, q3, shown):
    shown(q3, mo.ui.table(a3, page_size=25, selection=None, show_column_summaries=False))
    return


@app.cell
def _(answers, asked, mo, pl, shown):
    q4 = asked[3] if len(asked) > 3 else asked[-1]
    # Decimal is exact and altair cannot encode it. The cast is here, on the way to the
    # picture, rather than in the query -- which stays exact so the two answers can be
    # compared as values.
    a4 = answers[q4.id].with_columns(pl.col("revenue_order_lines_amount").cast(pl.Float64))
    # A series has to stop somewhere, and the period it stops in is short rather than small.
    # Drawn at full strength beside twenty-two whole months, the last bar reads as a collapse
    # in demand -- so it is marked, here, from the answer alone.
    a4 = a4.with_columns((pl.col("order_month") != a4["order_month"].max()).alias("complete"))

    taken = float(a4["revenue_order_lines_amount"].sum())
    # A month can only be the best whole one if a whole one was recorded. On an answer of one
    # row -- or none -- there is no such month, and a page that indexed row 0 anyway would take
    # the whole render down rather than showing the emptiness, which is the actual news.
    whole = a4.filter(pl.col("complete"))
    best = (
        whole.sort("revenue_order_lines_amount", descending=True).row(0, named=True)
        if whole.height
        else None
    )
    superlative = (
        f"The best whole month was **{best['order_month']}**, "
        f"at **{best['revenue_order_lines_amount']:,.0f}**."
        if best
        else "No whole month was recorded."
    )

    # No currency symbol anywhere on this page. The model says nothing records which currency
    # this is, and a symbol would be the page inventing a fact -- which is the one thing a
    # destination is never allowed to do.
    shown(
        q4,
        mo.md(
            f"""
            ## {q4.question}

            *Asked by the {q4.persona.lower()}.*

            ## {taken:,.0f} taken

            across **{len(a4)}** months, from **{a4["order_month"].min()}** to
            **{a4["order_month"].max()}**. {superlative} No currency is shown because nothing
            in the source records one.
            """
        ),
    )
    return a4, best, q4, superlative, taken


@app.cell
def _(GRID, MUTED, SEQUENTIAL, SURFACE, a4, alt, mo, q4, shown):
    # Magnitude per month, so bars rather than a line: the question is how much was taken in
    # each month, not the shape of a trajectory between them. One series, so no legend -- the
    # title above names it.
    revenue = (
        alt.Chart(a4)
        .mark_bar(color=SEQUENTIAL[4], cornerRadiusEnd=3)
        .encode(
            x=alt.X("order_month:O", title=None, axis=alt.Axis(labelAngle=-90, labelColor=MUTED)),
            y=alt.Y(
                "revenue_order_lines_amount:Q",
                title="revenue",
                axis=alt.Axis(labelColor=MUTED, titleColor=MUTED, gridColor=GRID, format=",.0f"),
            ),
            # Never on colour alone: the caption below says what the faded bar is, and the
            # tooltip says it again for anyone who reads a bar rather than a page.
            opacity=alt.Opacity(
                "complete:N",
                scale=alt.Scale(domain=[True, False], range=[1.0, 0.35]),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("order_month:O", title="Ordered in"),
                alt.Tooltip("revenue_order_lines_amount:Q", title="Revenue", format=",.2f"),
                alt.Tooltip("complete:N", title="Whole month"),
            ],
        )
        .properties(height=190, width="container", background=SURFACE)
        .configure_view(stroke=None)
        .configure_axis(domainColor="#c3c2b7", tickColor="#c3c2b7", labelFontSize=11)
    )

    shown(q4, mo.ui.altair_chart(revenue, chart_selection=False, legend_selection=False))
    return (revenue,)


@app.cell
def _(MUTED, a4, mo, q4, shown):
    shown(
        q4,
        mo.md(
            f"""
            <span style="color:{MUTED}">The last bar, **{a4["order_month"].max()}**, is faded
            because the recording stops inside that month. It is shorter than the others, not
            smaller, and reading it as a fall in demand is reading the edge of the recording.
            The question says where it ends.</span>
            """
        ),
    )
    return


@app.cell
def _(mo, q4, shown):
    shown(q4, mo.md("### What the words mean"))
    return


@app.cell
def _(glossary, q4, shown):
    shown(q4, glossary(q4))
    return


@app.cell
def _(a4, mo, q4, shown):
    shown(
        q4,
        mo.md(
            f"""
            ### The answer, row by row

            {len(a4):,} rows, at the grain of the order line rather than the order. Every other
            question on this page is per order, and they can be read side by side because a
            measure stays on the stage that owns it.
            """
        ),
    )
    return


@app.cell
def _(a4, mo, q4, shown):
    shown(q4, mo.ui.table(a4, page_size=25, selection=None, show_column_summaries=False))
    return


@app.cell
def _(answers, asked, mo, pl, shown):
    q5 = asked[4] if len(asked) > 4 else asked[-1]
    a5 = answers[q5.id].with_columns(pl.col("revenue_order_lines_amount").cast(pl.Float64))
    # The recording stops inside the last quarter, so every panel falls off the same cliff at
    # the same point and none of them did. Derived from the answer, never from a date the page
    # was told. Same rule as q04's last month, and louder here: five weeks of a thirteen-week
    # quarter rather than six days of a month.
    a5 = a5.with_columns((pl.col("order_quarter") != a5["order_quarter"].max()).alias("complete"))

    # Panels ordered by what each category took, so the eye starts with the biggest business.
    # Ties broken by name: an unstable sort changes the delivered picture with no change to the
    # answer, and a reviewer diffing the PNG cannot tell that from a new number.
    category_ranked = (
        a5.group_by("product_category")
        .agg(pl.col("revenue_order_lines_amount").sum())
        .sort(["revenue_order_lines_amount", "product_category"], descending=[True, False])
    )
    category_order = category_ranked["product_category"].to_list()
    category_taken = float(a5["revenue_order_lines_amount"].sum())
    category_biggest = category_ranked.row(0, named=True)

    shown(
        q5,
        mo.md(
            f"""
            ## {q5.question}

            *Asked by the {q5.persona.lower()}.*

            ## {category_taken:,.0f} taken across {len(category_order)} categories

            over **{a5["order_quarter"].n_unique()}** quarters, from
            **{a5["order_quarter"].min()}** to **{a5["order_quarter"].max()}**. The largest is
            **{category_biggest["product_category"]}** at
            **{category_biggest["revenue_order_lines_amount"]:,.0f}**, which is a fact about
            size and not about which one to buy more of -- for that, read the shapes below
            rather than the heights. No currency is shown because nothing in the source
            records one.
            """
        ),
    )
    return a5, category_biggest, category_order, q5, category_ranked, category_taken


@app.cell
def _(GRID, MUTED, SEQUENTIAL, SURFACE, a5, alt, mo, category_order, q5, shown):
    # Small multiples rather than eight lines on one chart. Eight is exactly where categorical
    # colour stops working, and the question is the SHAPE of each category over time -- which a
    # reader gets from eight small panels on one shared scale and cannot get from eight hues.
    # One hue throughout, so colour carries nothing and the panel title carries identity.
    category_trend = (
        alt.Chart(a5)
        .mark_area(
            color=SEQUENTIAL[3],
            opacity=0.9,
            line=alt.OverlayMarkDef(color=SEQUENTIAL[6], strokeWidth=1.5),
        )
        .encode(
            x=alt.X(
                "order_quarter:O",
                title=None,
                axis=alt.Axis(labelAngle=-90, labelColor=MUTED, labelFontSize=9),
            ),
            y=alt.Y(
                "revenue_order_lines_amount:Q",
                title=None,
                axis=alt.Axis(labelColor=MUTED, gridColor=GRID, format="~s"),
            ),
            opacity=alt.Opacity(
                "complete:N",
                scale=alt.Scale(domain=[True, False], range=[0.9, 0.3]),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("product_category:N", title="Category"),
                alt.Tooltip("order_quarter:O", title="Ordered in"),
                alt.Tooltip("revenue_order_lines_amount:Q", title="Revenue", format=",.2f"),
                alt.Tooltip("complete:N", title="Whole quarter"),
            ],
        )
        # The background belongs to the FacetChart, not to each panel: altair refuses a
        # `background` on a chart that is about to be facetted, and says so.
        .properties(width=150, height=95)
        .facet(
            facet=alt.Facet(
                "product_category:N",
                title=None,
                sort=category_order,
                header=alt.Header(labelFontSize=11),
            ),
            columns=4,
        )
        .properties(background=SURFACE)
        .configure_view(stroke=None)
        .configure_axis(domainColor="#c3c2b7", tickColor="#c3c2b7", labelFontSize=10)
    )

    shown(q5, mo.ui.altair_chart(category_trend, chart_selection=False, legend_selection=False))
    return (category_trend,)


@app.cell
def _(MUTED, a5, mo, q5, shown):
    shown(
        q5,
        mo.md(
            f"""
            <span style="color:{MUTED}">One panel per category on a shared scale, largest
            first, so the heights compare and the shapes are what you read. The last quarter,
            **{a5["order_quarter"].max()}**, is faded on every panel because the recording stops
            inside it -- five weeks of thirteen. It is shorter than the others, not smaller: the
            business was taking orders faster in those five weeks than in the whole quarter
            before.</span>
            """
        ),
    )
    return


@app.cell
def _(mo, q5, shown):
    shown(q5, mo.md("### What the words mean"))
    return


@app.cell
def _(glossary, q5, shown):
    shown(q5, glossary(q5))
    return


@app.cell
def _(a5, mo, q5, shown):
    shown(
        q5,
        mo.md(
            f"""
            ### The answer, row by row

            {len(a5):,} rows -- every category sold something in every quarter, so the grid is
            full and no cell here is an invented zero. The category is reached through the
            product the line was for, which is two edges from the line and the first question
            here that needed more than one.
            """
        ),
    )
    return


@app.cell
def _(a5, mo, q5, shown):
    shown(q5, mo.ui.table(a5, page_size=16, selection=None, show_column_summaries=False))
    return


if __name__ == "__main__":
    app.run()
