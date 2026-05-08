"""
Fill missing lat/lon in a manifest CSV using Meteostat station metadata.

Input manifest format (like bay_area_manifest_18_21.csv):
  city,lat,lon,csv,...

This script:
  - For rows where lat/lon are blank, searches Meteostat Stations by city name
  - Prefers stations in California (if available), otherwise falls back to US
  - Writes an output manifest with lat/lon filled and extra columns:
      station_id, station_name, station_lat, station_lon

Notes:
  - This is best-effort matching. City names like "Corte Madera" usually work,
    but some may require slight name tweaks.
  - Requires internet access (Meteostat downloads station metadata).

PowerShell:
  pip install meteostat pandas
  python fill_manifest_latlon_meteostat.py --in bay_area_manifest_18_21.csv --out bay_area_manifest_18_21_filled.csv
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass
class StationPick:
    station_id: str
    name: str
    lat: float
    lon: float
    score: float


def _pick_station_for_city(city: str, *, aliases: Optional[list[str]] = None) -> Optional[StationPick]:
    """
    Try several queries and pick the best station.
    Scoring is heuristic; we prioritize CA hits and closer name matches.
    """
    city_q = (city or "").strip()
    if not city_q:
        return None

    # Query variants (include aliases like nearby larger cities)
    variants = [city_q]
    if aliases:
        for a in aliases:
            a = (a or "").strip()
            if a and a not in variants:
                variants.append(a)
    if "-" in city_q:
        variants.append(city_q.replace("-", " "))
    if "." in city_q:
        variants.append(city_q.replace(".", " "))

    # Some common formatting issues
    variants = list(dict.fromkeys([v.strip() for v in variants if v.strip()]))

    # Meteostat >=2.1 exposes a local sqlite stations DB at ~/.meteostat/stations.db.
    # We query it directly for station names.
    try:
        from meteostat import stations  # type: ignore
    except Exception as e:
        raise SystemExit(
            "Missing dependency: meteostat. Install with: pip install meteostat\n"
            f"Import error: {e}"
        )

    try:
        db_path = stations._get_file_path()  # type: ignore[attr-defined]
    except Exception:
        db_path = None
    if not db_path:
        return None

    import sqlite3

    rows = []
    with sqlite3.connect(db_path) as con:
        for v in variants:
            like = f"%{v}%"
            q = """
            SELECT
              s.id as id,
              n.name as name,
              s.country as country,
              s.region as region,
              s.latitude as latitude,
              s.longitude as longitude
            FROM stations s
            JOIN names n ON n.station = s.id
            WHERE n.language = 'en'
              AND n.name LIKE ?
            LIMIT 200
            """
            try:
                cur = con.execute(q, (like,))
                rows.extend(cur.fetchall())
            except Exception:
                continue

    if not rows:
        # Fallback: for a few cities which rarely appear in station names,
        # use a city centroid -> nearby station search.
        fallback_centroids = {
            "Gilroy": (37.0058, -121.5683),
            "Vacaville": (38.3566, -121.9877),
        }
        if city_q in fallback_centroids:
            try:
                from meteostat import Point  # type: ignore
            except Exception:
                return None
            lat0, lon0 = fallback_centroids[city_q]
            try:
                near = stations.nearby(Point(lat0, lon0), radius=80_000, limit=50)  # type: ignore[attr-defined]
            except Exception:
                return None
            if near is None or len(near) == 0:
                return None
            # near is a DataFrame indexed by station id; expected columns include name/country/region/latitude/longitude
            near = near.reset_index()
            # Prefer CA/US
            def score_near(r) -> float:
                sc = 0.0
                country = str(r.get("country", "")).upper()
                region = str(r.get("region", "")).upper()
                if country == "US":
                    sc += 2.0
                if region in ("CA", "US-CA"):
                    sc += 3.0
                return sc
            near["_score"] = near.apply(score_near, axis=1)
            best = near.sort_values(["_score"], ascending=False).iloc[0]
            return StationPick(
                station_id=str(best.get("id") or best.get("index") or ""),
                name=str(best.get("name", "")),
                lat=float(best.get("latitude")),
                lon=float(best.get("longitude")),
                score=float(best.get("_score", 0.0)),
            )

        return None

    allc = pd.DataFrame(
        rows, columns=["id", "name", "country", "region", "latitude", "longitude"]
    ).drop_duplicates(subset=["id"])

    def score_row(r) -> float:
        name = str(r.get("name", "")).lower()
        country = str(r.get("country", "")).upper()
        region = str(r.get("region", "")).upper()
        # Consider any variant as a name match
        vs = [x.lower() for x in variants if x]

        sc = 0.0
        # Prefer California / US
        if country == "US":
            sc += 2.0
        if region in ("CA", "US-CA"):
            sc += 3.0

        # Prefer name containing city (rough)
        for v in vs:
            if v and v in name:
                sc += 2.5
                break
        # Shorter names slightly preferred (often more specific)
        sc += max(0.0, 1.0 - (len(name) / 80.0))
        return sc

    allc = allc.copy()
    allc["_score"] = allc.apply(score_row, axis=1)
    best = allc.sort_values(["_score"], ascending=False).iloc[0]

    return StationPick(
        station_id=str(best["id"]),
        name=str(best.get("name", "")),
        lat=float(best["latitude"]),
        lon=float(best["longitude"]),
        score=float(best["_score"]),
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Fill manifest lat/lon using Meteostat station metadata.")
    ap.add_argument("--in", dest="inp", required=True, help="Input manifest CSV")
    ap.add_argument("--out", required=True, help="Output manifest CSV with lat/lon filled")
    ap.add_argument("--only-missing", action="store_true", help="Only fill rows where lat/lon are missing")
    args = ap.parse_args()

    df = pd.read_csv(args.inp)
    if "city" not in df.columns:
        raise SystemExit("Manifest must include a 'city' column")
    if "lat" not in df.columns:
        df["lat"] = ""
    if "lon" not in df.columns:
        df["lon"] = ""

    # Normalize existing values
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")

    station_id = []
    station_name = []
    station_lat = []
    station_lon = []
    station_score = []

    filled = 0
    for _, row in df.iterrows():
        city = str(row["city"])
        have = pd.notna(row["lat"]) and pd.notna(row["lon"])
        # If this row represents many duplicate city files, use those names as fallback aliases.
        aliases = []
        dups = row.get("duplicates", "")
        if isinstance(dups, str) and dups.strip():
            for part in dups.split(";"):
                part = part.strip()
                if not part:
                    continue
                # e.g. "San_Rafael_18_21.csv" -> "San Rafael"
                nm = part.replace("_18_21.csv", "").replace(".csv", "").replace("_", " ")
                aliases.append(nm)

        if args.only_missing and have:
            pick = None
        else:
            pick = _pick_station_for_city(city, aliases=aliases)
        if pick is None:
            # Keep existing values (could be NaN)
            station_id.append("")
            station_name.append("")
            station_lat.append(float("nan"))
            station_lon.append(float("nan"))
            station_score.append(float("nan"))
            continue

        station_id.append(pick.station_id)
        station_name.append(pick.name)
        station_lat.append(pick.lat)
        station_lon.append(pick.lon)
        station_score.append(pick.score)

        if not have:
            df.loc[row.name, "lat"] = pick.lat
            df.loc[row.name, "lon"] = pick.lon
            filled += 1

    df["station_id"] = station_id
    df["station_name"] = station_name
    df["station_lat"] = station_lat
    df["station_lon"] = station_lon
    df["station_score"] = station_score

    df.to_csv(args.out, index=False)
    print(f"rows={len(df)} filled_latlon={filled}")
    print(f"wrote={args.out}")


if __name__ == "__main__":
    main()

