---
id: qn1
slice: 0
status: green
persona: A reader
question: How many parents happened per month?
aggregation: count
measure: PARENT.HAPPENED_PARENTS_COUNT
dimensions: [_calendar.month_label]
time_grain: month
defines: [PARENT, PARENT.HAPPENED_ON]
order_by: [month]
---

## Story

As a reader, I want a question that names nothing from any business.

## Definitions

- {{PARENT}}
- {{PARENT.HAPPENED_ON}}
