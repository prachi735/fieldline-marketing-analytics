CREATE TABLE fx(currency TEXT PRIMARY KEY, rate REAL);
INSERT INTO fx VALUES ('USD',1),('EUR',1.08),('GBP',1.27);
CREATE TABLE rules(rule TEXT PRIMARY KEY,owner TEXT,action TEXT);
INSERT INTO rules VALUES
('Duplicate key','Data engineering','Deduplicate by campaign-day before loading.'),
('Missing field','Data engineering','Restore the source channel before publication.'),
('Currency','Finance analytics','Quarantine the unmapped currency and confirm its ISO code.'),
('Taxonomy','Marketing ops','Map the source label to the approved channel list.'),
('Late load','Data engineering','Investigate ingestion latency and backfill the partition.'),
('Missing key','Data engineering','Replay the missing source key.'),
('Extra key','Data engineering','Trace the unexpected account and quarantine its row.'),
('Spend mismatch','Finance analytics','Compare native amounts against the source ledger.'),
('Clicks mismatch','Marketing ops','Re-export click totals for this campaign-day.'),
('CPC mismatch','Analytics','Recompute cost per click after upstream corrections.');
CREATE VIEW exceptions AS
SELECT day,account,campaign,'Duplicate key' AS rule,'High' AS severity,printf('%d rows per key',count(*)) AS evidence FROM extract GROUP BY day,account,campaign HAVING count(*)>1
UNION ALL SELECT day,account,campaign,'Missing field','High','Channel is empty' FROM extract WHERE channel=''
UNION ALL SELECT day,account,campaign,'Currency','High',currency FROM extract LEFT JOIN fx USING(currency) WHERE rate IS NULL
UNION ALL SELECT day,account,campaign,'Taxonomy','Medium',channel FROM extract WHERE channel<>'' AND channel NOT IN ('Search','LinkedIn','Display','Review')
UNION ALL SELECT day,account,campaign,'Late load','Medium','Arrived on '||loaded_on FROM extract WHERE julianday(loaded_on)-julianday(day)>2
UNION ALL SELECT s.day,s.account,s.campaign,'Missing key','High','Source key absent in extract' FROM source s LEFT JOIN extract e USING(day,account,campaign) WHERE e.account IS NULL
UNION ALL SELECT e.day,e.account,e.campaign,'Extra key','High','Extract key absent in source' FROM extract e LEFT JOIN source s USING(day,account,campaign) WHERE s.account IS NULL
UNION ALL SELECT s.day,s.account,s.campaign,'Spend mismatch','High',printf('Extract %s %d vs source %s %d (minor units)',e.currency,e.minor_units,s.currency,s.minor_units) FROM source s JOIN extract e USING(day,account,campaign) WHERE e.minor_units<>s.minor_units OR (e.currency<>s.currency)
UNION ALL SELECT s.day,s.account,s.campaign,'Clicks mismatch','Medium',printf('%d clicks vs source %d',e.clicks,s.clicks) FROM source s JOIN extract e USING(day,account,campaign) WHERE e.clicks<>s.clicks
UNION ALL SELECT day,account,campaign,'CPC mismatch','Medium',printf('Reported %.2f vs computed %.2f',reported_cpc_usd,minor_units*rate/(100*clicks)) FROM extract JOIN fx USING(currency) WHERE clicks>0 AND ABS(reported_cpc_usd-ROUND(minor_units*rate/(100*clicks),2))>0.011;
CREATE VIEW daily AS
WITH s AS (SELECT day,SUM(ROUND(minor_units*rate))/100.0 AS ledger_usd FROM source JOIN fx USING(currency) GROUP BY day),
e AS (SELECT day,SUM(ROUND(minor_units*rate))/100.0 AS convertible_extract_usd, SUM(CASE WHEN rate IS NULL THEN 1 ELSE 0 END) AS unpriced_rows FROM extract LEFT JOIN fx USING(currency) GROUP BY day)
SELECT day,ledger_usd,convertible_extract_usd,ROUND(convertible_extract_usd-ledger_usd,2) AS variance_usd,unpriced_rows FROM s JOIN e USING(day);
