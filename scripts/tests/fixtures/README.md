# Test fixtures

`owid_co2_subset.csv` is an unmodified extract of the real Our World in Data CO2 dataset
(commit `382ee6c662b0ece26e111f263b44c029afad7787` of https://github.com/owid/co2-data,
CC BY 4.0): all 79 columns, years 2019–2024, for these entities:

India, China, United States, Germany, Kosovo (country without ISO code), World, Asia
(region), Asia (GCP) (excluded duplicate region), High-income countries (income group),
International shipping (other).

Tests that need malformed input (negative values, unknown entities, duplicates) modify a
copy of this extract in memory; the file itself is never edited.
