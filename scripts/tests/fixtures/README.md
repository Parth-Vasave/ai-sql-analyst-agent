# Test fixtures

`synthetic_raw_datagovin.csv` is **synthetic** test data, written by hand to exercise the
cleaning rules (bad dates, invalid prices, duplicates, messy whitespace, ...). State, district
and market names are deliberately fake (`Test State A`, `Market A1`) so it can never be
mistaken for real AGMARKNET data. It is only used by the test suite and is never loaded
into the application database.

The header row mirrors the data.gov.in API/portal CSV layout (`Min_x0020_Price`, ...).
