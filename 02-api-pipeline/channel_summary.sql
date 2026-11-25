SELECT channel, COUNT(*) AS campaign_days, SUM(spend_cents)/100.0 AS spend_usd,
       SUM(clicks) AS clicks, ROUND(SUM(spend_cents)*1.0/NULLIF(SUM(clicks)*100,0),2) AS cost_per_click
FROM campaign_day GROUP BY channel ORDER BY spend_usd DESC;

