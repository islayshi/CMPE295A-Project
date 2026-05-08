"""
Visualize U-Net predictions on your .npz dataset.

Creates a panel with:
  tmax (°C), wind speed, precip, PrevFireMask, Pred FireMask, True FireMask, Error

PowerShell:
  python visualize_unet_predictions.py --data-dir unet_bay_area_18_21 --model wildfire_unet_bay_18_21.keras --date 2020-09-10 --out pred_2020-09-10.png
  python visualize_unet_predictions.py --data-dir unet_bay_area_18_21 --model wildfire_unet_bay_18_21.keras --date-start 2020-08-10 --date-end 2020-09-30 --max 6 --out pred_panel.png
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import tensorflow as tf

from build_unet_dataset_weather_geojson import DATA_STATS, INPUT_FEATURES


def _denorm(name: str, z: np.ndarray) -> np.ndarray:
    mean, std = DATA_STATS[name]
    if name == "PrevFireMask":
        return np.clip(z, 0.0, 1.0).astype(np.float32)
    return (z * std + mean).astype(np.float32)


def load_npz(path: Path) -> Tuple[np.ndarray, np.ndarray, str]:
    z = np.load(path)
    X = np.asarray(z["X"], dtype=np.float32)
    y = np.asarray(z["y"], dtype=np.float32)
    raw = z["date"]
    if raw.shape == ():
        d = str(np.asarray(raw).item())
    else:
        d = str(raw[0] if raw.size else path.stem)
    return X, y, d


def find_paths(data_dir: Path, *, date_start: str, date_end: str, max_n: int) -> List[Path]:
    paths = sorted(data_dir.glob("unet_*.npz"))
    out = []
    for p in paths:
        # unet_YYYY-MM-DD.npz
        d = p.stem.replace("unet_", "")
        if date_start <= d <= date_end:
            out.append(p)
        if max_n and len(out) >= max_n:
            break
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Visualize U-Net predictions on .npz samples.")
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--date", default=None, help="Single date YYYY-MM-DD")
    ap.add_argument("--date-start", default=None)
    ap.add_argument("--date-end", default=None)
    ap.add_argument("--max", type=int, default=6)
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--out", default="unet_predictions.png")
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    if args.date:
        paths = [data_dir / f"unet_{args.date}.npz"]
    else:
        ds = args.date_start or "0000-01-01"
        de = args.date_end or "9999-12-31"
        paths = find_paths(data_dir, date_start=ds, date_end=de, max_n=args.max)

    paths = [p for p in paths if p.exists()]
    if not paths:
        raise SystemExit("No matching .npz files found for requested dates.")

    model = tf.keras.models.load_model(args.model, compile=False)

    idx = {n: INPUT_FEATURES.index(n) for n in INPUT_FEATURES}
    n = len(paths)
    cols = 7
    fig, axes = plt.subplots(n, cols, figsize=(3.0 * cols, 2.6 * n))
    if n == 1:
        axes = np.asarray([axes])

    for r, p in enumerate(paths):
        X, y, d = load_npz(p)
        pred = model.predict(X[None, ...], verbose=0)[0][..., 0]
        prev = X[..., idx["PrevFireMask"]]

        tmax_c = _denorm("tmmx", X[..., idx["tmmx"]]) - 273.15
        wspd = _denorm("vs", X[..., idx["vs"]])
        prcp = _denorm("pr", X[..., idx["pr"]])

        panels = [
            (tmax_c, "inferno", f"{d}\ntmax °C"),
            (wspd, "viridis", "wind m/s"),
            (prcp, "Blues", "prcp mm"),
            (prev, "Reds", "PrevFireMask"),
            (pred, "YlOrRd", "Pred Fire"),
            (y[..., 0], "Reds", "True Fire"),
            (((pred >= args.threshold).astype(np.float32) - y[..., 0]), "bwr", "Pred-True"),
        ]

        for c, (img, cmap, title) in enumerate(panels):
            ax = axes[r, c]
            im = ax.imshow(img, cmap=cmap)
            ax.set_title(title, fontsize=9)
            ax.axis("off")
            plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    plt.tight_layout()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"wrote={out.resolve()} samples={n}")


if __name__ == "__main__":
    main()

