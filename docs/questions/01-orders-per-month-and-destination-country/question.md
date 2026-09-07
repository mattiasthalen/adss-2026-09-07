---
id: q01
slice: 1
status: green
persona: Sales director
question: How many orders were placed per order month and destination country?
aggregation: count
measure: ORDER.PLACED_ORDERS_COUNT
dimensions: [_calendar.month_label, order.destination_country]
time_grain: month
defines:
  - ORDER
  - ORDER.PLACED_ON
  - ORDER.DESTINATION_COUNTRY
  - ORDER.events.PLACED
  - ORDER.measures.PLACED_ORDERS_COUNT
order_by: [order_month, destination_country]
---

## Story

As the **sales director**, I want to see how many orders were placed per order month and
destination country, so that I can put sales effort where demand is moving.

## Definitions

Every term below is defined in `dab/model.yaml` or `dab/uss.yaml` and nowhere else. This
question references them; it does not restate them.

- {{ORDER}}
- {{ORDER.PLACED_ON}}
- {{ORDER.DESTINATION_COUNTRY}}
- {{ORDER.events.PLACED}}
- {{ORDER.measures.PLACED_ORDERS_COUNT}}

## The W's

- **Why**: demand moves between countries and between seasons, and sales effort should
  follow it rather than lag it by a year.
- **What**: the count of orders placed. Not their value, not their contents, not whether
  they were ever delivered.
- **Who**: customers place them; the sales director is the one who acts on the answer.
- **How**: one `placed` event per order, counted at the month of the day it was placed.
- **Where**: the country the order is to be delivered to, which is not necessarily where
  the customer is.
- **When**: all history, at calendar month (`_calendar.month_label`, `YYYY-MM`).
- **What will you do with it**: move sales effort toward the countries whose monthly counts
  are rising, and ask why for the ones that are falling.

## Nulls

Both dimensions are nullable in the source metadata. Neither is null in the recording, so
this question takes no position on them yet; the first question where one is null must say
what it wants, in its own file, because that is a property of the question rather than of
the model.

## Answers

Two queries, in `staged.sql` and `uss.sql`. The first computes the answer straight from what
the source sent, bypassing the business model and the star schema entirely. The second
computes it from the star schema. They must agree row for row.

That check does not prove the answer is *right* -- a wrong definition would make both wrong
together. It proves that routing the number through integration and generation did not
change it, which is the failure this architecture is most exposed to and least able to see.
