"""Download mandi price records from the data.gov.in Open Government Data API.

This is one of two ways to get raw data into ``data/raw/``:

1. This script (needs a free data.gov.in API key), or
2. A CSV downloaded manually from data.gov.in / AGMARKNET and copied into ``data/raw/``.

Either way, ``clean_data.py`` does the rest. Every download writes a manifest next to the
CSV recording where and when the data came from, so the dataset stays traceable.

Usage:
    DATA_GOV_IN_API_KEY=... python -m scripts.ingest_data --dataset historical \\
        --filter Commodity=Wheat --filter State=Maharashtra --max-records 50000
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

API_BASE = "https://api.data.gov.in/resource"
PAGE_SIZE = 1000

# data.gov.in resource IDs. Verify on the portal before a large download: the portal
# occasionally re-publishes resources under new IDs.
DATASETS: dict[str, dict[str, str]] = {
    "current": {
        "resource_id": "9ef84268-d588-465a-a308-a864a43d0070",
        "title": "Current Daily Price of Various Commodities from Various Markets (Mandi)",
    },
    "historical": {
        "resource_id": "35985678-0d79-46b4-9ed6-6f13308a1d24",
        "title": "Variety-wise Daily Market Prices Data of Commodity",
    },
}

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def build_url(resource_id: str, api_key: str, offset: int, filters: dict[str, str]) -> str:
    params: dict[str, str | int] = {
        "api-key": api_key,
        "format": "json",
        "offset": offset,
        "limit": PAGE_SIZE,
    }
    for field, value in filters.items():
        params[f"filters[{field}]"] = value
    return f"{API_BASE}/{resource_id}?{urllib.parse.urlencode(params)}"


def redact(url: str) -> str:
    """Remove the API key from a URL before it is logged or written to disk."""
    parts = urllib.parse.urlsplit(url)
    query = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query) if k != "api-key"]
    return urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(query)))


def fetch_page(url: str, retries: int = 3) -> dict[str, Any]:
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                return json.load(response)
        except (OSError, json.JSONDecodeError) as exc:
            if attempt == retries:
                raise RuntimeError(f"data.gov.in request failed after {retries} attempts: {exc}") from exc
            time.sleep(2**attempt)
    raise AssertionError("unreachable")


def download(
    resource_id: str, api_key: str, filters: dict[str, str], max_records: int
) -> tuple[list[dict[str, Any]], int]:
    records: list[dict[str, Any]] = []
    total = 0
    offset = 0
    while len(records) < max_records:
        payload = fetch_page(build_url(resource_id, api_key, offset, filters))
        if payload.get("status") == "error":
            raise RuntimeError(f"data.gov.in returned an error: {payload.get('message')}")
        page = payload.get("records") or []
        total = int(payload.get("total") or 0)
        if not page:
            break
        records.extend(page)
        offset += len(page)
        print(f"  fetched {len(records):,} / {min(total, max_records):,}", file=sys.stderr)
        if offset >= total:
            break
    return records[:max_records], total


def write_outputs(
    records: list[dict[str, Any]], dataset: str, resource_id: str, filters: dict[str, str], total: int
) -> Path:
    if not records:
        raise RuntimeError("No records returned; check the filters and the resource ID.")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    csv_path = RAW_DIR / f"datagovin_{dataset}_{stamp}.csv"

    fieldnames = list(records[0].keys())
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)

    manifest = {
        "source": "data.gov.in Open Government Data Platform (AGMARKNET)",
        "dataset_title": DATASETS.get(dataset, {}).get("title", dataset),
        "resource_id": resource_id,
        "resource_url": f"https://data.gov.in/resource/{resource_id}",
        "api_request": redact(build_url(resource_id, "REDACTED", 0, filters)),
        "filters": filters,
        "downloaded_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "records_available": total,
        "records_downloaded": len(records),
        "columns": fieldnames,
        "sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
    }
    csv_path.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return csv_path


def parse_filters(values: list[str]) -> dict[str, str]:
    filters: dict[str, str] = {}
    for item in values:
        field, sep, value = item.partition("=")
        if not sep or not field or not value:
            raise SystemExit(f"Invalid --filter {item!r}; expected Field=Value")
        filters[field] = value
    return filters


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--dataset", choices=sorted(DATASETS), default="historical")
    parser.add_argument("--resource-id", help="Override the resource ID of --dataset.")
    parser.add_argument("--filter", action="append", default=[], metavar="Field=Value")
    parser.add_argument("--max-records", type=int, default=100_000)
    args = parser.parse_args(argv)

    api_key = os.environ.get("DATA_GOV_IN_API_KEY")
    if not api_key:
        print("DATA_GOV_IN_API_KEY is not set. Register at https://data.gov.in to get one.", file=sys.stderr)
        return 2

    resource_id = args.resource_id or DATASETS[args.dataset]["resource_id"]
    filters = parse_filters(args.filter)
    print(f"Downloading resource {resource_id} with filters {filters or '{}'}", file=sys.stderr)
    records, total = download(resource_id, api_key, filters, args.max_records)
    path = write_outputs(records, args.dataset, resource_id, filters, total)
    print(f"Wrote {len(records):,} records to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
