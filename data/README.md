# Dataset

## Source

Indian agricultural mandi (wholesale market) prices published by **AGMARKNET**
(Directorate of Marketing & Inspection, Ministry of Agriculture & Farmers Welfare) on the
**Open Government Data Platform India — [data.gov.in](https://data.gov.in)**.

| Resource | data.gov.in resource ID | Coverage |
|---|---|---|
| Variety-wise Daily Market Prices Data of Commodity | `35985678-0d79-46b4-9ed6-6f13308a1d24` | Historical daily prices (used for multi-year analysis) |
| Current Daily Price of Various Commodities from Various Markets (Mandi) | `9ef84268-d588-465a-a308-a864a43d0070` | Latest day only |

Resource IDs should be confirmed on the portal before a large download.
Licence: [Government Open Data License – India](https://data.gov.in/government-open-data-license-india).

**Download date:** _not yet downloaded_. Every download writes a `*.manifest.json` next to
the raw CSV with the resource ID, filters, UTC timestamp, row count and SHA-256, and
`data/processed/cleaning_report.json` copies those manifests. This table will be
filled in from the manifest of the dataset actually used.

## Getting the raw data

Either:

```bash
# A. API (free key from https://data.gov.in → My Account → API key)
DATA_GOV_IN_API_KEY=... python -m scripts.ingest_data --dataset historical \
    --filter Commodity=Wheat --max-records 100000
```

or **B.** download a CSV from the data.gov.in resource page (or AGMARKNET) and put it in
`data/raw/`. Add a small `<file>.manifest.json` by hand recording the source URL and the
download date so provenance is not lost.

`data/raw/` and `data/processed/` are git-ignored; raw government data is not committed.

## Columns used

| Source column (data.gov.in) | Canonical | Notes |
|---|---|---|
| `State` | `state` | |
| `District` | `district` | |
| `Market` | `market` | Mandi / APMC name |
| `Commodity` | `commodity` | |
| `Variety` | `variety` | `Unknown` if blank |
| `Grade` | `grade` | e.g. FAQ; `Unknown` if blank |
| `Arrival_Date` | `arrival_date` | `dd/mm/yyyy` in source → ISO date |
| `Min_x0020_Price` / `Min Price (Rs./Quintal)` | `min_price` | INR per quintal |
| `Max_x0020_Price` / `Max Price (Rs./Quintal)` | `max_price` | INR per quintal |
| `Modal_x0020_Price` / `Modal Price (Rs./Quintal)` | `modal_price` | INR per quintal; most common price that day |

Other columns (e.g. `Commodity_Code`) are ignored.

## Cleaning

`python -m scripts.clean_data data/raw/*.csv` applies these rules and counts every dropped
row in `data/processed/cleaning_report.json`:

1. Column names are normalized and mapped to the canonical names above; a file missing a required column is rejected.
2. Text is trimmed and repeated whitespace collapsed. Casing is kept as published.
3. Blank `variety` / `grade` → `Unknown`.
4. Rows without state, district, market or commodity are dropped.
5. Dates are parsed day-first (`dd/mm/yyyy`) or ISO; anything else (including impossible dates such as 31/02) is dropped. Month-first is never guessed.
6. Prices must be numeric and > 0, with `min_price <= modal_price <= max_price`; otherwise the row is dropped.
7. Optional `--start-date`, `--end-date`, `--commodity` filters (reported separately from errors).
8. Exact duplicate rows are collapsed.
9. Rows that share the natural key (state, district, market, commodity, variety, grade, date) but disagree on prices are **all** dropped, since the correct one cannot be determined.

## Assumptions

- Prices are INR per quintal (100 kg), as AGMARKNET publishes them.
- "Price" in a question means the **modal price** unless the user names min/max.
- Market identity is (state, district, market name). Spelling variants of the same place across source files are not merged.
- `commodities.category` is left empty; the source does not provide a commodity group.

## Database schema

See [`database/schema.sql`](../database/schema.sql). Normalized into `commodities`,
`markets` and `daily_prices`, with CHECK constraints mirroring the cleaning rules and indexes on
`(commodity_id, arrival_date)`, `arrival_date`, `markets.state` and `markets.district`.
