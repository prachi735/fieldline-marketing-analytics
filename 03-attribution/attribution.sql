WITH ordered AS (
    SELECT t.*, COUNT(*) OVER (PARTITION BY lead_id) AS touch_count,
           ROW_NUMBER() OVER (PARTITION BY lead_id ORDER BY touch_no) AS first_rank,
           ROW_NUMBER() OVER (PARTITION BY lead_id ORDER BY touch_no DESC) AS last_rank
    FROM touches t
), credit AS (
    SELECT o.*, m.model,
       CASE m.model WHEN 'First touch' THEN CAST(first_rank=1 AS REAL)
                    WHEN 'Last touch' THEN CAST(last_rank=1 AS REAL)
                    ELSE 1.0/touch_count END AS weight
    FROM ordered o CROSS JOIN models m
), outcomes AS (
    SELECT model, channel, SUM(weight) AS leads, SUM(weight*qualified) AS qualified,
           SUM(weight*opportunity) AS opportunities, SUM(weight*won) AS wins,
           SUM(weight*pipeline) AS pipeline_usd, SUM(weight*revenue) AS revenue_usd
    FROM credit JOIN leads USING(lead_id)
    GROUP BY model, channel
)
SELECT o.*, spend_usd, spend_usd/NULLIF(wins,0) AS media_cac,
       (revenue_usd*0.72-spend_usd)/spend_usd AS gross_profit_roi
FROM outcomes o JOIN spend USING(channel) ORDER BY model, revenue_usd DESC;

