SELECT
    strftime(p.parent_on, '%Y-%m') AS month_label,
    count(p.parent_id) AS happened_parents_count
FROM das__staged.parent__current AS p
GROUP BY strftime(p.parent_on, '%Y-%m')
ORDER BY month_label
