SELECT
    cal.month_label AS month_label,
    sum(b._measure__parent__happened_parents_count) AS happened_parents_count
FROM dar__uss._bridge AS b
INNER JOIN dar__uss._calendar AS cal ON b._event_date = cal.date_key
GROUP BY cal.month_label
ORDER BY month_label
