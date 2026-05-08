"""
Create a weather-station manifest from 18_21_Data/*.csv.

Why this exists:
  - Your 18_21_Data CSVs do NOT include latitude/longitude.
  - Some files are duplicates (same bytes under different city names).

This script:
  1) Scans 18_21_Data/*.csv
  2) Groups identical files by MD5
  3) Writes a manifest CSV with ONE entry per unique file content:
       city,lat,lon,csv
     with lat/lon left blank for you to fill (or you can fill later with another script).

PowerShell:
  python make_manifest_from_18_21_data.py --data-dir 18_21_Data --out bay_area_manifest_18_21.csv
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import pandas as pd


def main() -> None:
    ap = argparse.ArgumentParser(description="Build a manifest from 18_21_Data CSVs (dedup by content).")
    ap.add_argument("--data-dir", default="18_21_Data", help="Directory containing *_18_21.csv files.")
    ap.add_argument("--out", default="bay_area_manifest_18_21.csv", help="Output manifest CSV.")
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    files = sorted(data_dir.glob("*.csv"))
    if not files:
        raise SystemExit(f"No CSV files found in {data_dir}")

    # Group by exact content hash
    groups: dict[str, list[Path]] = {}
    for p in files:
        h = hashlib.md5(p.read_bytes()).hexdigest()
        groups.setdefault(h, []).append(p)

    rows = []
    for h, ps in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[1][0].name)):
        # Choose the first filename as the representative city label
        rep = ps[0]
        city = rep.stem.replace("_18_21", "").replace("_", " ")
        rows.append(
            {
                "city": city,
                "lat": "",
                "lon": "",
                "csv": str(rep.as_posix()),
                "duplicates": ";".join([p.name for p in ps[1:]]),
                "md5": h,
            }
        )

    out = pd.DataFrame(rows)
    out_path = Path(args.out)
    out.to_csv(out_path, index=False)

    dup_files = sum(max(0, len(v) - 1) for v in groups.values())
    print(f"total_files={len(files)} unique_contents={len(groups)} duplicate_files={dup_files}")
    print(f"wrote_manifest={out_path.resolve()}")


if __name__ == "__main__":
    main()

