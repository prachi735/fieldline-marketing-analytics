SELECT customer_id, MIN(month_no) AS cohort, MAX(month_no) AS last_active,
       COUNT(*) AS frequency, SUM(net_cents)/100.0 AS net_sales,
       CAST(julianday('2026-01-01')-julianday(MAX(order_date)) AS INTEGER) AS recency_days
FROM orders GROUP BY customer_id;

