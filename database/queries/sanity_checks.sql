-- Manual analytical queries used to verify the loaded dataset (Milestone 1).
-- Run as the read-only agent to prove it can answer the questions the app targets:
--
--   psql "$DATABASE_URL" -f database/queries/sanity_checks.sql
--   psql "$DATABASE_URL" -v commodity=Onion -v year=2023 -f database/queries/sanity_checks.sql
--
-- These double as reference SQL for the evaluation ground truth later.

\if :{?commodity} \else \set commodity Wheat \endif
\if :{?year} \else \set year 2024 \endif
\pset footer off
\echo 'Parameters: commodity =' :commodity ', year =' :year

\echo '\n== 1. Dataset coverage'
SELECT count(*)                           AS price_records,
       min(arrival_date)                  AS first_date,
       max(arrival_date)                  AS last_date,
       (SELECT count(DISTINCT state) FROM markets) AS states,
       (SELECT count(*) FROM markets)     AS markets,
       (SELECT count(*) FROM commodities) AS commodities
FROM daily_prices;

\echo '\n== 2. Average modal price by state (commodity, year)'
SELECT m.state,
       round(avg(p.modal_price), 2) AS avg_modal_price,
       count(*)                     AS records
FROM daily_prices p
JOIN markets m     ON m.id = p.market_id
JOIN commodities c ON c.id = p.commodity_id
WHERE c.name = :'commodity'
  AND p.arrival_date >= make_date(:year, 1, 1)
  AND p.arrival_date <  make_date(:year + 1, 1, 1)
GROUP BY m.state
ORDER BY avg_modal_price DESC
LIMIT 10;

\echo '\n== 3. Top 5 commodities by average modal price (all data)'
SELECT c.name AS commodity,
       round(avg(p.modal_price), 2) AS avg_modal_price,
       count(*) AS records
FROM daily_prices p
JOIN commodities c ON c.id = p.commodity_id
GROUP BY c.name
ORDER BY avg_modal_price DESC
LIMIT 5;

\echo '\n== 4. Monthly average modal price trend (commodity)'
SELECT date_trunc('month', p.arrival_date)::date AS month,
       round(avg(p.modal_price), 2) AS avg_modal_price,
       count(*) AS records
FROM daily_prices p
JOIN commodities c ON c.id = p.commodity_id
WHERE c.name = :'commodity'
GROUP BY month
ORDER BY month
LIMIT 120;

\echo '\n== 5. Year-over-year change in average modal price by state (commodity, year vs year-1)'
WITH yearly AS (
    SELECT m.state,
           extract(year FROM p.arrival_date)::int AS yr,
           avg(p.modal_price) AS avg_price
    FROM daily_prices p
    JOIN markets m     ON m.id = p.market_id
    JOIN commodities c ON c.id = p.commodity_id
    WHERE c.name = :'commodity'
      AND p.arrival_date >= make_date(:year - 1, 1, 1)
      AND p.arrival_date <  make_date(:year + 1, 1, 1)
    GROUP BY m.state, yr
)
SELECT cur.state,
       round(prev.avg_price, 2) AS avg_price_previous_year,
       round(cur.avg_price, 2)  AS avg_price_year,
       round(100 * (cur.avg_price - prev.avg_price) / prev.avg_price, 2) AS pct_change
FROM yearly cur
JOIN yearly prev ON prev.state = cur.state AND prev.yr = cur.yr - 1
WHERE cur.yr = :year
ORDER BY pct_change DESC
LIMIT 10;

\echo '\n== 6. Commodities with the largest average daily price spread (max - min)'
SELECT c.name AS commodity,
       round(avg(p.max_price - p.min_price), 2) AS avg_daily_spread,
       round(stddev_samp(p.modal_price), 2)     AS modal_price_stddev
FROM daily_prices p
JOIN commodities c ON c.id = p.commodity_id
GROUP BY c.name
HAVING count(*) > 1
ORDER BY avg_daily_spread DESC
LIMIT 10;

\echo '\n== 7. Markets with the highest average modal price (commodity, year)'
SELECT m.state, m.district, m.name AS market,
       round(avg(p.modal_price), 2) AS avg_modal_price
FROM daily_prices p
JOIN markets m     ON m.id = p.market_id
JOIN commodities c ON c.id = p.commodity_id
WHERE c.name = :'commodity'
  AND p.arrival_date >= make_date(:year, 1, 1)
  AND p.arrival_date <  make_date(:year + 1, 1, 1)
GROUP BY m.state, m.district, m.name
ORDER BY avg_modal_price DESC
LIMIT 10;
