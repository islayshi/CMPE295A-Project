"""
Create a presentable PNG containing:
  - Confusion matrix heatmap
  - Key metrics text block

Uses the same .npz dataset format and model as evaluate_unet_metrics.py.

PowerShell example:
  python make_unet_metrics_report_image.py ^
    --data-dir "unet_bay_area_18_21" ^
    --model "wildfire_unet_bay_18_21.keras" ^
    --date-start 2020-08-10 --date-end 2020-09-30 --max-samples 200 ^
    --threshold 0.5 ^
    --out "unet_metrics_report_2020_fireseason.png"
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

from build_unet_dataset_weather_geojson import INPUT_FEATURES


def _iter_npz_paths(data_dir: Path, pattern: str) -> List[Path]:
    rx = re.compile(pattern)
    return sorted(p for p in data_dir.iterdir() if p.is_file() and rx.match(p.name))


def _date_from_name(name: str) -> Optional[str]:
    m = re.search(r"(\d{4}-\d{2}-\d{2})", name)
    return m.group(1) if m else None


def _load_npz(path: Path) -> Tuple[np.ndarray, np.ndarray]:
    z = np.load(path)
    X = np.asarray(z["X"], dtype=np.float32)
    y = np.asarray(z["y"], dtype=np.float32)
    return X, y


def _flatten(a: np.ndarray) -> np.ndarray:
    return a.reshape(-1).astype(np.float32)


def _auc_metrics(y_true: np.ndarray, y_score: np.ndarray) -> dict:
    yt = (y_true >= 0.5).astype(np.int32)
    if len(np.unique(yt)) < 2:
        return {"roc_auc": float("nan"), "pr_auc": float("nan")}
    from sklearn.metrics import average_precision_score, roc_auc_score

    return {"roc_auc": float(roc_auc_score(yt, y_score)), "pr_auc": float(average_precision_score(yt, y_score))}


def _prob_metrics(y_true: np.ndarray, y_score: np.ndarray) -> dict:
    yt = (y_true >= 0.5).astype(np.float32)
    p = np.clip(y_score.astype(np.float32), 1e-7, 1.0 - 1e-7)
    brier = float(np.mean((p - yt) ** 2))
    log_loss = float(-np.mean(yt * np.log(p) + (1.0 - yt) * np.log(1.0 - p)))
    return {"brier": brier, "log_loss": log_loss}


def _metrics_at_threshold(y_true: np.ndarray, y_score: np.ndarray, thr: float) -> dict:
    yt = (y_true >= 0.5).astype(np.int32)
    yp = (y_score >= thr).astype(np.int32)
    tp = int(((yp == 1) & (yt == 1)).sum())
    tn = int(((yp == 0) & (yt == 0)).sum())
    fp = int(((yp == 1) & (yt == 0)).sum())
    fn = int(((yp == 0) & (yt == 1)).sum())

    total = max(1, (tp + tn + fp + fn))
    acc = (tp + tn) / total
    prec = tp / max(1, (tp + fp))
    rec = tp / max(1, (tp + fn))
    f1 = (2 * prec * rec) / max(1e-12, (prec + rec))

    iou = tp / max(1, (tp + fp + fn))
    dice = (2 * tp) / max(1, (2 * tp + fp + fn))
    tnr = tn / max(1, (tn + fp))
    fpr = fp / max(1, (fp + tn))
    fnr = fn / max(1, (fn + tp))
    bal_acc = 0.5 * (rec + tnr)
    denom = float((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    mcc = ((tp * tn - fp * fn) / max(1e-12, denom**0.5)) if denom > 0 else 0.0

    return {
        "threshold": float(thr),
        "accuracy": float(acc),
        "precision": float(prec),
        "recall": float(rec),
        "f1": float(f1),
        "iou": float(iou),
        "dice": float(dice),
        "specificity": float(tnr),
        "fpr": float(fpr),
        "fnr": float(fnr),
        "balanced_accuracy": float(bal_acc),
        "mcc": float(mcc),
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Create a metrics+confusion-matrix report image for the U-Net model.")
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--pattern", default=r"unet_\d{4}-\d{2}-\d{2}\.npz")
    ap.add_argument("--date-start", default=None)
    ap.add_argument("--date-end", default=None)
    ap.add_argument("--max-samples", type=int, default=200)
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--title", default=None, help="Optional custom title.")
    ap.add_argument("--out", default="unet_metrics_report.png")
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    paths = _iter_npz_paths(data_dir, args.pattern)
    ds = args.date_start or "0000-01-01"
    de = args.date_end or "9999-12-31"
    filtered = []
    for p in paths:
        d = _date_from_name(p.name)
        if d and ds <= d <= de:
            filtered.append(p)
    paths = filtered[: args.max_samples] if args.max_samples else filtered
    if not paths:
        raise SystemExit("No matching samples found for given date window.")

    import tensorflow as tf

    model = tf.keras.models.load_model(args.model, compile=False)
    prev_idx = INPUT_FEATURES.index("PrevFireMask")

    y_true_all = []
    y_score_all = []
    for p in paths:
        X, y = _load_npz(p)
        pred = model.predict(X[None, ...], verbose=0)[0]
        if pred.ndim == 2:
            pred = pred[..., None]
        y_true_all.append(_flatten(y))
        y_score_all.append(_flatten(pred))

    y_true = np.concatenate(y_true_all, axis=0)
    y_score = np.clip(np.concatenate(y_score_all, axis=0), 0.0, 1.0)

    pos_rate = float((y_true >= 0.5).mean())
    thr = _metrics_at_threshold(y_true, y_score, args.threshold)
    auc = _auc_metrics(y_true, y_score)
    prob = _prob_metrics(y_true, y_score)

    cm = np.array([[thr["tn"], thr["fp"]], [thr["fn"], thr["tp"]]], dtype=np.int64)

    # Build a nice figure
    import matplotlib.pyplot as plt

    title = args.title or f"U-Net Fire Spread Metrics ({ds} to {de})"
    subtitle = f"samples={len(paths)} | pixels={y_true.size:,} | pos_rate={pos_rate:.4%} | thr={args.threshold}"

    fig = plt.figure(figsize=(12, 6))
    gs = fig.add_gridspec(2, 3, width_ratios=[1.2, 1.0, 1.0], height_ratios=[0.25, 0.75])

    ax_title = fig.add_subplot(gs[0, :])
    ax_title.axis("off")
    ax_title.text(0.0, 0.72, title, fontsize=16, fontweight="bold")
    ax_title.text(0.0, 0.22, subtitle, fontsize=10)

    ax_cm = fig.add_subplot(gs[1, 0])
    im = ax_cm.imshow(cm, cmap="Blues")
    ax_cm.set_title("Confusion Matrix", fontsize=12, fontweight="bold")
    ax_cm.set_xlabel("Predicted")
    ax_cm.set_ylabel("Actual")
    ax_cm.set_xticks([0, 1])
    ax_cm.set_yticks([0, 1])
    ax_cm.set_xticklabels(["0 (no fire)", "1 (fire)"])
    ax_cm.set_yticklabels(["0 (no fire)", "1 (fire)"])
    for (i, j), v in np.ndenumerate(cm):
        ax_cm.text(j, i, f"{int(v):,}", ha="center", va="center", fontsize=11, fontweight="bold")
    fig.colorbar(im, ax=ax_cm, fraction=0.046, pad=0.04)

    ax_txt = fig.add_subplot(gs[1, 1:])
    ax_txt.axis("off")

    def fmt(x: float) -> str:
        return "—" if (x is None or (isinstance(x, float) and np.isnan(x))) else f"{x:.4f}"

    metrics_lines = [
        ("ROC-AUC", fmt(auc.get("roc_auc"))),
        ("PR-AUC", fmt(auc.get("pr_auc"))),
        ("Accuracy", fmt(thr["accuracy"])),
        ("Balanced Acc", fmt(thr["balanced_accuracy"])),
        ("Precision", fmt(thr["precision"])),
        ("Recall", fmt(thr["recall"])),
        ("F1 / Dice", fmt(thr["f1"])),
        ("IoU", fmt(thr["iou"])),
        ("Specificity", fmt(thr["specificity"])),
        ("FPR", fmt(thr["fpr"])),
        ("FNR", fmt(thr["fnr"])),
        ("MCC", fmt(thr["mcc"])),
        ("Brier", fmt(prob["brier"])),
        ("Log Loss", fmt(prob["log_loss"])),
    ]

    ax_txt.text(0.0, 1.0, "Metrics", fontsize=12, fontweight="bold", va="top")
    y0 = 0.92
    dy = 0.06
    for i, (k, v) in enumerate(metrics_lines):
        ax_txt.text(0.0, y0 - i * dy, f"{k:>12}  :  {v}", fontsize=11, family="monospace", va="top")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(out, dpi=175, bbox_inches="tight")
    plt.close()
    print(f"wrote={out.resolve()}")


if __name__ == "__main__":
    main()

