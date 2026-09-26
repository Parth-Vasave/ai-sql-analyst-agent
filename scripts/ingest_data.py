"""Download the Our World in Data CO2 dataset and codebook into data/raw/.

The files are fetched from a pinned commit of https://github.com/owid/co2-data and
verified against known SHA-256 hashes, so every build uses exactly the same data.
A manifest recording the source, commit, download time and hashes is written alongside.

Usage:
    python -m scripts.ingest_data                     # pinned commit (reproducible)
    python -m scripts.ingest_data --commit master --no-verify   # latest data, unverified
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

REPO = "owid/co2-data"
# OWID co2-data HEAD on 2026-09-26. Update commit and hashes together.
PINNED_COMMIT = "382ee6c662b0ece26e111f263b44c029afad7787"
FILES: dict[str, str] = {
    "owid-co2-data.csv": "7f78e2b218ce4bb8c538bbec04fdc9a7982e8d40bff972e650df603899edd5f6",
    "owid-co2-codebook.csv": "33b4f5e00efd58c7b83863f736beba1af4df946b43642b0400c3ec38648e0e8e",
}
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
MANIFEST_NAME = "owid-co2.manifest.json"


class IntegrityError(RuntimeError):
    """Raised when a downloaded file does not match its expected hash."""


def raw_url(commit: str, filename: str) -> str:
    return f"https://raw.githubusercontent.com/{REPO}/{commit}/{filename}"


def fetch(url: str, retries: int = 3) -> bytes:
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=120) as response:
                return response.read()
        except OSError as exc:
            if attempt == retries:
                raise RuntimeError(f"Download failed after {retries} attempts: {url}: {exc}") from exc
            time.sleep(2**attempt)
    raise AssertionError("unreachable")


def download(commit: str, verify: bool, raw_dir: Path = RAW_DIR) -> dict:
    raw_dir.mkdir(parents=True, exist_ok=True)
    files = []
    for filename, expected in FILES.items():
        url = raw_url(commit, filename)
        print(f"Downloading {url}", file=sys.stderr)
        content = fetch(url)
        digest = hashlib.sha256(content).hexdigest()
        if verify and digest != expected:
            raise IntegrityError(
                f"{filename}: sha256 {digest} does not match the pinned {expected}. "
                "Use --no-verify only if you intend to use different data."
            )
        (raw_dir / filename).write_bytes(content)
        files.append({"file": filename, "url": url, "sha256": digest, "bytes": len(content)})

    manifest = {
        "source": "Our World in Data — CO2 and Greenhouse Gas Emissions",
        "repository": f"https://github.com/{REPO}",
        "commit": commit,
        "license": "CC BY 4.0",
        "downloaded_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "verified_against_pinned_hashes": verify,
        "files": files,
    }
    (raw_dir / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--commit", default=PINNED_COMMIT, help="Git commit or branch of owid/co2-data")
    parser.add_argument("--no-verify", action="store_true", help="Skip the pinned SHA-256 check")
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    args = parser.parse_args(argv)

    try:
        manifest = download(args.commit, verify=not args.no_verify, raw_dir=args.raw_dir)
    except (IntegrityError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote {len(manifest['files'])} files and {MANIFEST_NAME} to {args.raw_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
