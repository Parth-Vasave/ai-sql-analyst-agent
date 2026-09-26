-- Read-only role used by the AI agent.
--
-- These grants are the security boundary: even if the SQL validator were bypassed,
-- sql_agent cannot modify data or schema. Run as the database owner with psql variables:
--
--   psql -v agent_password=... -v statement_timeout=5s -f database/permissions.sql
--
-- Idempotent: safe to re-run (e.g. to rotate the password or change the timeout).

\set ON_ERROR_STOP on

SELECT 'CREATE ROLE sql_agent'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sql_agent')
\gexec

-- SUPERUSER, CREATEDB, CREATEROLE, REPLICATION and BYPASSRLS are off by default for a
-- new role. They are not spelled out because a non-superuser owner (e.g. on managed
-- Postgres) may not even mention them. scripts/tests/test_permissions.py asserts they are off.
ALTER ROLE sql_agent WITH
    LOGIN NOINHERIT
    CONNECTION LIMIT 20
    PASSWORD :'agent_password';

-- Defense in depth. default_transaction_read_only can be overridden by the session,
-- so it is NOT the primary guard; the missing privileges below are.
ALTER ROLE sql_agent SET default_transaction_read_only = on;
ALTER ROLE sql_agent SET statement_timeout = :'statement_timeout';
ALTER ROLE sql_agent SET idle_in_transaction_session_timeout = '30s';
ALTER ROLE sql_agent SET search_path = public;

-- Database level: no TEMP tables, only CONNECT.
SELECT format('REVOKE ALL ON DATABASE %I FROM PUBLIC', current_database()) \gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO sql_agent', current_database()) \gexec

-- Schema level: nobody but the owner may create objects in public.
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO sql_agent;

-- Table level: explicit allow-list, SELECT only. New tables are NOT granted automatically.
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM sql_agent;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM sql_agent;
GRANT SELECT ON countries, country_indicators, co2_emissions, ghg_emissions TO sql_agent;
