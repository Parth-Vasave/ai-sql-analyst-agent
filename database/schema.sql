-- AI SQL Analyst — analytical schema for Indian mandi (agricultural market) prices.
--
-- Source data: data.gov.in / AGMARKNET daily market price records.
-- One raw record = one (market, commodity, variety, grade, arrival_date) price quote.
-- Prices are in Indian Rupees per quintal (100 kg), as published by AGMARKNET.
--
-- Column comments are intentional: the schema retriever reads them as metadata.
-- This script is idempotent and is run by the database owner, never by sql_agent.

\set ON_ERROR_STOP on
SET client_min_messages = warning;

CREATE TABLE IF NOT EXISTS commodities (
    id        integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name      text NOT NULL UNIQUE,
    category  text
);

COMMENT ON TABLE commodities IS 'Agricultural commodities traded at mandis (e.g. Wheat, Onion, Tomato).';
COMMENT ON COLUMN commodities.name IS 'Commodity name as published by AGMARKNET, e.g. Wheat.';
COMMENT ON COLUMN commodities.category IS 'Commodity group (e.g. Cereals, Vegetables). NULL when not classified.';

CREATE TABLE IF NOT EXISTS markets (
    id        integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name      text NOT NULL,
    district  text NOT NULL,
    state     text NOT NULL,
    CONSTRAINT markets_state_district_name_key UNIQUE (state, district, name)
);

COMMENT ON TABLE markets IS 'Agricultural produce markets (mandis / APMCs) and their location.';
COMMENT ON COLUMN markets.name IS 'Market (mandi) name.';
COMMENT ON COLUMN markets.district IS 'District the market is located in.';
COMMENT ON COLUMN markets.state IS 'Indian state or union territory the market is located in.';

CREATE TABLE IF NOT EXISTS daily_prices (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    market_id     integer NOT NULL REFERENCES markets (id),
    commodity_id  integer NOT NULL REFERENCES commodities (id),
    variety       text NOT NULL,
    grade         text NOT NULL,
    arrival_date  date NOT NULL,
    min_price     numeric(12, 2) NOT NULL,
    max_price     numeric(12, 2) NOT NULL,
    modal_price   numeric(12, 2) NOT NULL,
    CONSTRAINT daily_prices_positive_prices CHECK (min_price > 0 AND max_price > 0 AND modal_price > 0),
    CONSTRAINT daily_prices_min_le_max CHECK (min_price <= max_price),
    CONSTRAINT daily_prices_modal_in_range CHECK (modal_price BETWEEN min_price AND max_price),
    CONSTRAINT daily_prices_record_key UNIQUE (market_id, commodity_id, variety, grade, arrival_date)
);

COMMENT ON TABLE daily_prices IS 'Daily wholesale price quotes per market, commodity, variety and grade.';
COMMENT ON COLUMN daily_prices.variety IS 'Commodity variety, e.g. Dara, Lokwan. ''Unknown'' when not reported.';
COMMENT ON COLUMN daily_prices.grade IS 'Quality grade, e.g. FAQ (Fair Average Quality). ''Unknown'' when not reported.';
COMMENT ON COLUMN daily_prices.arrival_date IS 'Date the price was recorded at the market.';
COMMENT ON COLUMN daily_prices.min_price IS 'Minimum traded price that day, INR per quintal.';
COMMENT ON COLUMN daily_prices.max_price IS 'Maximum traded price that day, INR per quintal.';
COMMENT ON COLUMN daily_prices.modal_price IS 'Most common (modal) traded price that day, INR per quintal. Default metric for "price".';

-- The UNIQUE constraint already indexes (market_id, commodity_id, ...) for market-led lookups.
-- These cover the dominant analytical access paths: by commodity over time, by date, by location.
CREATE INDEX IF NOT EXISTS daily_prices_commodity_date_idx ON daily_prices (commodity_id, arrival_date);
CREATE INDEX IF NOT EXISTS daily_prices_arrival_date_idx ON daily_prices (arrival_date);
CREATE INDEX IF NOT EXISTS markets_state_idx ON markets (state);
CREATE INDEX IF NOT EXISTS markets_district_idx ON markets (district);
