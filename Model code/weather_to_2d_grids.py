import argparse
import os
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd


def _safe_float(x, default: float = 0.0) -> float:
    try:
        if x is None or (isinstance(x, float) and np.isnan(x)):
            return float(default)
        if isinstance(x, str) and x.strip() == "":
            return float(default)
        return float(x)
    except Exception:
        return float(default)


def _unit_vec_from_wind_dir_deg(wdir_deg: float) -> Tuple[float, float]:
    """
    Convert meteorological wind direction degrees into a 2D unit vector for a gradient.

    If wdir is missing, return a neutral direction.
    """
    if not np.isfinite(wdir_deg):
        return (1.0, 0.0)
    # Treat wdir as "direction wind is coming FROM" (meteorological convention).
    # For an advection-ish gradient, we want the "towards" direction.
    theta = np.deg2rad((wdir_deg + 180.0) % 360.0)
    return (float(np.cos(theta)), float(np.sin(theta)))


def make_spread_map(
    *,
    base_value: float,
    size: int,
    wdir_deg: float,
    wspd: float,
    amp: float,
    seed: int,
) -> np.ndarray:
    """
    Turn a single scalar into a smooth 2D field:
    - directional gradient aligned with wind direction
    - low-frequency smooth noise

    This is a *demo-grade* way to get non-trivial spatial input maps from a
    single-station time series.
    """
    rng = np.random.default_rng(seed)
    xs = np.linspace(-1.0, 1.0, size, dtype=np.float32)
    ys = np.linspace(-1.0, 1.0, size, dtype=np.float32)
    XX, YY = np.meshgrid(xs, ys)

    ux, uy = _unit_vec_from_wind_dir_deg(wdir_deg)
    grad = (ux * XX + uy * YY).astype(np.float32)

    # Smooth noise: sum of a few random low-frequency sinusoids
    noise = np.zeros((size, size), dtype=np.float32)
    for k in (1, 2, 3):
        a = rng.uniform(-1.0, 1.0)
        b = rng.uniform(-1.0, 1.0)
        phx = rng.uniform(0, 2 * np.pi)
        phy = rng.uniform(0, 2 * np.pi)
        noise += (a * np.sin((k * np.pi) * XX + phx) + b * np.cos((k * np.pi) * YY + phy)).astype(
            np.float32
        )
    noise = noise / max(1e-6, float(np.abs(noise).max()))

    # Wind speed scales the spatial variation a bit (bounded)
    wspd = float(np.clip(wspd if np.isfinite(wspd) else 0.0, 0.0, 25.0))
    wind_scale = 0.25 + 0.75 * (wspd / 25.0)

    field = base_value + (amp * wind_scale) * (0.7 * grad + 0.3 * noise)
    return field.astype(np.float32)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Create demo 2D weather grids from a station weather CSV (LA_Weather_Data_2020.csv)."
    )
    ap.add_argument("--csv", default="LA_Weather_Data_2020.csv")
    ap.add_argument("--date-col", default="date")
    ap.add_argument("--size", type=int, default=32, help="Grid size H=W (default 32).")
    ap.add_argument("--out-dir", default="weather_grids_la", help="Output dir for per-day .npz grids.")
    ap.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Seed for deterministic spatial patterns (default 0).",
    )
    ap.add_argument(
        "--amp",
        type=float,
        default=1.0,
        help="Overall amplitude of spatial variation in native units (default 1.0).",
    )
    ap.add_argument(
        "--write-preview-pngs",
        action="store_true",
        help="Also write quick PNG previews for a few channels.",
    )
    args = ap.parse_args()

    df = pd.read_csv(args.csv)
    if args.date_col not in df.columns:
        raise SystemExit(f"Missing date column '{args.date_col}' in {args.csv}")

    dt = pd.to_datetime(df[args.date_col], errors="coerce")
    df = df.assign(_date=dt).dropna(subset=["_date"]).sort_values("_date").reset_index(drop=True)
    df["date_str"] = df["_date"].dt.strftime("%Y-%m-%d")

    os.makedirs(args.out_dir, exist_ok=True)

    wrote = 0
    for i, row in df.iterrows():
        day = row["date_str"]

        # Pull station scalars (Celsius for temps)
        tmin_c = _safe_float(row.get("tmin"), 0.0)
        tmax_c = _safe_float(row.get("tmax"), 0.0)
        prcp = _safe_float(row.get("prcp"), 0.0)
        wdir = _safe_float(row.get("wdir"), float("nan"))
        wspd = _safe_float(row.get("wspd"), 0.0)

        # Convert temps to Kelvin to match the U-Net dataset's channel definitions
        tmmn_k = tmin_c + 273.15
        tmmx_k = tmax_c + 273.15

        # Channels that don't exist in this CSV: fill with stable defaults.
        # (These can be replaced later if you ingest real gridded sources.)
        defaults: Dict[str, float] = {
            "elevation": 300.0,
            "sph": 0.0071,
            "pdsi": 0.0,
            "NDVI": 0.31,
            "population": 61.0,
            "erc": 52.0,
        }

        # Build 2D maps
        seed_day = int(args.seed) + i * 97
        grids: Dict[str, np.ndarray] = {}
        grids["tmmn"] = make_spread_map(
            base_value=tmmn_k,
            size=args.size,
            wdir_deg=wdir,
            wspd=wspd,
            amp=max(0.1, args.amp * 2.0),
            seed=seed_day + 1,
        )
        grids["tmmx"] = make_spread_map(
            base_value=tmmx_k,
            size=args.size,
            wdir_deg=wdir,
            wspd=wspd,
            amp=max(0.1, args.amp * 2.0),
            seed=seed_day + 2,
        )
        grids["pr"] = make_spread_map(
            base_value=prcp,
            size=args.size,
            wdir_deg=wdir,
            wspd=wspd,
            amp=max(0.05, args.amp * 0.5),
            seed=seed_day + 3,
        )
        grids["th"] = make_spread_map(
            base_value=wdir if np.isfinite(wdir) else 0.0,
            size=args.size,
            wdir_deg=wdir,
            wspd=wspd,
            amp=max(1.0, args.amp * 15.0),
            seed=seed_day + 4,
        )
        grids["vs"] = make_spread_map(
            base_value=wspd,
            size=args.size,
            wdir_deg=wdir,
            wspd=wspd,
            amp=max(0.1, args.amp * 1.0),
            seed=seed_day + 5,
        )

        # Static-ish channels
        for k in ("elevation", "sph", "pdsi", "NDVI", "population", "erc"):
            grids[k] = make_spread_map(
                base_value=defaults[k],
                size=args.size,
                wdir_deg=wdir,
                wspd=wspd,
                amp=max(0.01, args.amp * 0.1),
                seed=seed_day + hash(k) % 1000,
            )

        out_path = os.path.join(args.out_dir, f"weather_grids_{day}.npz")
        np.savez_compressed(out_path, date=day, **grids)
        wrote += 1

        if args.write_preview_pngs and wrote <= 10:
            import matplotlib.pyplot as plt

            prev_dir = os.path.join(args.out_dir, "_previews")
            os.makedirs(prev_dir, exist_ok=True)
            for key in ("tmmn", "tmmx", "vs", "pr"):
                plt.imsave(os.path.join(prev_dir, f"{key}_{day}.png"), grids[key], cmap="viridis")

    print(f"rows={len(df)} wrote_npz={wrote} out_dir={args.out_dir}")


if __name__ == "__main__":
    main()

