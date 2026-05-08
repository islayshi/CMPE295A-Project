"""
Visualize U-Net samples produced by build_unet_dataset_weather_geojson.py.

For each .npz: plots denormalized weather maps (where useful), PrevFireMask, and
the next-day fire label y. Saves one PNG per sample or a combined multi-row PNG.

PowerShell example:
  python visualize_unet_dataset.py --dir unet_bay_area_2020 --max-plots 8 --out unet_viz_grid.png
  python visualize_unet_dataset.py --npz unet_bay_area_2020/unet_2020-09-10.npz --out unet_one_day.png
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np

from build_unet_dataset_weather_geojson import DATA_STATS, INPUT_FEATURES


def _denorm(name: str, z: np.ndarray) -> np.ndarray:
    mean, std = DATA_STATS[name]
    if name == "PrevFireMask":
        return np.clip(z, 0.0, 1.0).astype(np.float32)
    return (z * std + mean).astype(np.float32)


def _channel_index(name: str) -> int:
    try:
        return INPUT_FEATURES.index(name)
    except ValueError:
        raise SystemExit(f"Unknown feature {name}. INPUT_FEATURES={INPUT_FEATURES}")


def plot_one_sample(
    X: np.ndarray,
    y: np.ndarray,
    date_str: str,
    *,
    axes_row,
) -> None:
    """Fill one row of axes (6 subplots)."""
    idx_tmmx = _channel_index("tmmx")
    idx_vs = _channel_index("vs")
    idx_pr = _channel_index("pr")
    idx_th = _channel_index("th")
    idx_prev = _channel_index("PrevFireMask")

    tmmx_k=_denorm("tmmx", X[..., idx_tmmx])
    tmax_c = tmmx_k - 273.15

    panels = [
        (tmax_c, "inferno", f"{date_str}\ntmax (°C)"),
        (_denorm("vs", X[..., idx_vs]), "viridis", "wind speed (m/s)"),
        (_denorm("pr", X[..., idx_pr]), "Blues", "precip (mm)"),
        (_denorm("th", X[..., idx_th]), "twilight", "wind dir (°)"),
        (X[..., idx_prev], "Reds", "PrevFireMask (d−1)"),
        (y[..., 0], "Reds", "FireMask label (d+1)"),
    ]

    for ax, (img, cmap, title) in zip(axes_row, panels):
        im = ax.imshow(img, cmap=cmap, aspect="equal")
        ax.set_title(title, fontsize=9)
        ax.axis("off")
        plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)


def load_npz(path: Path) -> Tuple[np.ndarray, np.ndarray, str]:
    z = np.load(path)
    X = np.asarray(z["X"], dtype=np.float32)
    y = np.asarray(z["y"], dtype=np.float32)
    raw = z["date"]
    if raw.shape == ():
        date_str = str(np.asarray(raw).item())
    else:
        date_str = str(raw[0] if raw.size else path.stem)
    return X, y, date_str


def main() -> None:
    ap = argparse.ArgumentParser(description="Visualize unet_*.npz tensors.")
    ap.add_argument("--npz", default=None, help="Single .npz file path.")
    ap.add_argument("--dir", default=None, help="Directory of unet_*.npz files.")
    ap.add_argument(
        "--pattern",
        default=r"unet_\d{4}-\d{2}-\d{2}\.npz",
        help="Regex basename filter when using --dir.",
    )
    ap.add_argument("--max-plots", type=int, default=6, help="Max samples when using --dir.")
    ap.add_argument("--out", default="unet_dataset_visualization.png")
    args = ap.parse_args()

    paths: List[Path] = []
    if args.npz:
        paths = [Path(args.npz)]
    elif args.dir:
        root = Path(args.dir)
        rx = re.compile(args.pattern)
        paths = sorted(p for p in root.iterdir() if p.is_file() and rx.match(p.name))
        paths = paths[: args.max_plots]
    else:
        raise SystemExit("Provide --npz or --dir")

    if not paths:
        raise SystemExit("No matching .npz files found.")

    n = len(paths)
    fig, axes = plt.subplots(n, 6, figsize=(14, 2.4 * n))
    if n == 1:
        axes = np.asarray([axes])

    for i, p in enumerate(paths):
        X, y, dstr = load_npz(p)
        plot_one_sample(X, y, dstr, axes_row=axes[i])

    fig.suptitle(
        "Center day d: weather grids (IDW from stations) | PrevFireMask(d−1) | label FireMask(d+1)",
        fontsize=11,
        y=1.02,
    )
    plt.tight_layout()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(str(out_path), dpi=150, bbox_inches="tight")
    plt.close()
    print(f"wrote={out_path.resolve()} samples={n}")


if __name__ == "__main__":
    main()
