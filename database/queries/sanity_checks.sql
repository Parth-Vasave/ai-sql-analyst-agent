-- Manual analytical queries used to verify the loaded dataset (Milestone 1).
-- Run as the read-only agent to prove it can answer the questions the app targets:
--
--   psql "$DATABASE_URL" -f database/queries/sanity_checks.sql
--   psql "$DATABASE_URL" -v country=Germany -v year=2023 -f database/queries/sanity_checks.sql
--
-- These double as reference SQL for the evaluation ground truth later.

\if :{?country} \else \set country India \endif
\if :{?year} \else \set year 2024 \endif
\pset footer off
\echo 'Parameters: country =' :country ', year =' :year

\echo '\n== 1. Dataset coverage'
SELECT c.entity_type,
       count(DISTINCT c.id) AS entities,
       min(e.year)          AS first_year,
       max(e.year)          AS last_year,
       count(*)             AS co2_rows
FROM countries c
JOIN co2_emissions e ON e.country_id = c.id
GROUP BY c.entity_type
ORDER BY c.entity_type;

\echo '\n== 2. Top 10 countries by annual CO2 emissions (aggregates excluded)'
SELECT c.name, round(e.co2, 1) AS co2_mt, round(e.share_global_co2, 2) AS share_global_pct
FROM co2_emissions e
JOIN countries c ON c.id = e.country_id
WHERE c.entity_type = 'country' AND e.year = :year AND e.co2 IS NOT NULL
ORDER BY e.co2 DESC
LIMIT 10;

\echo '\n== 3. Highest CO2 per capita among countries with more than 10 million people'
SELECT c.name, round(e.co2_per_capita, 2) AS co2_t_per_person,
       round(i.population / 1e6, 1) AS population_millions
FROM co2_emissions e
JOIN countries c          ON c.id = e.country_id
JOIN country_indicators i ON i.country_id = e.country_id AND i.year = e.year
WHERE c.entity_type = 'country' AND e.year = :year AND i.population > 10000000
  AND e.co2_per_capita IS NOT NULL
ORDER BY e.co2_per_capita DESC
LIMIT 10;

\echo '\n== 4. CO2 per capita trend for the selected country (every 4 years since 2000)'
SELECT e.year, round(e.co2, 1) AS co2_mt, round(e.co2_per_capita, 2) AS co2_t_per_person
FROM co2_emissions e
JOIN countries c ON c.id = e.country_id
WHERE c.name = :'country' AND e.year >= 2000 AND (e.year % 4 = 0 OR e.year = :year)
ORDER BY e.year
LIMIT 50;

\echo '\n== 5. Fossil fuel mix of CO2 emissions for the selected country and year'
SELECT round(100 * e.coal_co2 / e.co2, 1) AS coal_pct,
       round(100 * e.oil_co2 / e.co2, 1)  AS oil_pct,
       round(100 * e.gas_co2 / e.co2, 1)  AS gas_pct,
       round(100 * e.cement_co2 / e.co2, 1) AS cement_pct
FROM co2_emissions e
JOIN countries c ON c.id = e.country_id
WHERE c.name = :'country' AND e.year = :year
LIMIT 1;

\echo '\n== 6. Largest percentage increase in CO2 over the last 10 years (countries emitting > 50 Mt)'
SELECT c.name,
       round(past.co2, 1) AS co2_10_years_earlier,
       round(now_.co2, 1) AS co2_year,
       round(100 * (now_.co2 - past.co2) / past.co2, 1) AS pct_change
FROM co2_emissions now_
JOIN co2_emissions past ON past.country_id = now_.country_id AND past.year = now_.year - 10
JOIN countries c ON c.id = now_.country_id
WHERE c.entity_type = 'country' AND now_.year = :year AND now_.co2 > 50 AND past.co2 > 0
ORDER BY pct_change DESC
LIMIT 10;

\echo '\n== 7. World and income-group emissions and population (aggregates)'
SELECT c.name, round(e.co2, 0) AS co2_mt, round(e.co2_per_capita, 2) AS co2_t_per_person,
       round(g.total_ghg, 0) AS total_ghg_mt_co2e
FROM countries c
JOIN co2_emissions e ON e.country_id = c.id AND e.year = :year
LEFT JOIN ghg_emissions g ON g.country_id = c.id AND g.year = :year
WHERE c.name = 'World' OR c.entity_type = 'income_group'
ORDER BY e.co2 DESC
LIMIT 10;

\echo '\n== 8. Cumulative CO2 since records began: top 5 countries (historical responsibility)'
SELECT c.name, round(e.cumulative_co2 / 1000, 1) AS cumulative_co2_gt,
       round(e.share_global_cumulative_co2, 1) AS share_pct
FROM co2_emissions e
JOIN countries c ON c.id = e.country_id
WHERE c.entity_type = 'country' AND e.year = :year AND e.cumulative_co2 IS NOT NULL
ORDER BY e.cumulative_co2 DESC
LIMIT 5;
