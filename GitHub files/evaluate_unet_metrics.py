"""
Compute visible evaluation metrics for U-Net-style fire mask prediction.

Inputs:
  - Directory of .npz samples produced by build_unet_dataset_weather_geojson.py
    Each .npz must contain:
      X: (H,W,12) float32
      y: (H,W,1) float32 (0/1)

Optional:
  - A trained Keras model (.keras). If not provided, uses a baseline prediction:
      y_pred = PrevFireMask channel (copy-forward baseline)

Outputs:
  - Prints Accuracy, Precision, Recall, F1 at a threshold
  - Prints ROC-AUC and PR-AUC (when both classes exist)
  - Prints confusion matrix

PowerShell examples:
  python evaluate_unet_metrics.py --data-dir unet_bay_area_2020 --max-samples 60
  python evaluate_unet_metrics.py --data-dir unet_bay_area_2020 --model wildfire_spread_unet.keras --threshold 0.5
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

from build_unet_dataset_weather_geojson import INPUT_FEATURES


def _iter_npz_paths(data_dir: Path, pattern: str, max_samples: int) -> List[Path]:
    rx = re.compile(pattern)
    paths = sorted(p for p in data_dir.iterdir() if p.is_file() and rx.match(p.name))
    if max_samples > 0:
        paths = paths[:max_samples]
    return paths


def _date_from_name(name: str) -> Optional[str]:
    # Expect unet_YYYY-MM-DD.npz
    m = re.search(r"(\d{4}-\d{2}-\d{2})", name)
    return m.group(1) if m else None


def _load_npz(path: Path) -> Tuple[np.ndarray, np.ndarray]:
    z = np.load(path)
    X = np.asarray(z["X"], dtype=np.float32)
    y = np.asarray(z["y"], dtype=np.float32)
    if y.ndim != 3 or y.shape[-1] != 1:
        raise ValueError(f"{path.name}: y must be (H,W,1), got {y.shape}")
    return X, y


def _flatten(y: np.ndarray) -> np.ndarray:
    return y.reshape(-1).astype(np.float32)


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
    rec = tp / max(1, (tp + fn))  # TPR
    f1 = (2 * prec * rec) / max(1e-12, (prec + rec))

    # Segmentation-friendly / imbalance-robust metrics
    iou = tp / max(1, (tp + fp + fn))
    dice = (2 * tp) / max(1, (2 * tp + fp + fn))
    tnr = tn / max(1, (tn + fp))  # specificity
    fpr = fp / max(1, (fp + tn))
    fnr = fn / max(1, (fn + tp))
    bal_acc = 0.5 * (rec + tnr)
    # Matthews correlation coefficient
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


def _auc_metrics(y_true: np.ndarray, y_score: np.ndarray) -> dict:
    # These require both classes present.
    yt = (y_true >= 0.5).astype(np.int32)
    if len(np.unique(yt)) < 2:
        return {"roc_auc": float("nan"), "pr_auc": float("nan")}

    try:
        from sklearn.metrics import average_precision_score, roc_auc_score

        return {
            "roc_auc": float(roc_auc_score(yt, y_score)),
            "pr_auc": float(average_precision_score(yt, y_score)),
        }
    except Exception:
        # Fallback: no sklearn or metric failure
        return {"roc_auc": float("nan"), "pr_auc": float("nan")}


def _prob_metrics(y_true: np.ndarray, y_score: np.ndarray) -> dict:
    """
    Threshold-free probability quality metrics.
    """
    yt = (y_true >= 0.5).astype(np.float32)
    p = np.clip(y_score.astype(np.float32), 1e-7, 1.0 - 1e-7)

    brier = float(np.mean((p - yt) ** 2))
    log_loss = float(-np.mean(yt * np.log(p) + (1.0 - yt) * np.log(1.0 - p)))
    return {"brier": brier, "log_loss": log_loss}


def main() -> None:
    ap = argparse.ArgumentParser(description="Evaluate U-Net metrics on .npz samples.")
    ap.add_argument("--data-dir", required=True, help="Directory containing unet_YYYY-MM-DD.npz files.")
    ap.add_argument("--pattern", default=r"unet_\d{4}-\d{2}-\d{2}\.npz", help="Regex file pattern.")
    ap.add_argument("--max-samples", type=int, default=0, help="0 = no limit.")
    ap.add_argument("--model", default=None, help="Optional path to trained Keras model (.keras).")
    ap.add_argument("--threshold", type=float, default=0.5, help="Threshold for accuracy/precision/recall.")
    ap.add_argument("--date-start", default=None, help="Optional filter start date YYYY-MM-DD (by filename).")
    ap.add_argument("--date-end", default=None, help="Optional filter end date YYYY-MM-DD (by filename).")
    ap.add_argument(
        "--cm-out",
        default=None,
        help="Optional output path to save a confusion matrix PNG (e.g., cm.png).",
    )
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    paths = _iter_npz_paths(data_dir, args.pattern, max_samples=0)
    if args.date_start or args.date_end:
        ds = args.date_start or "0000-01-01"
        de = args.date_end or "9999-12-31"
        filtered = []
        for p in paths:
            d = _date_from_name(p.name)
            if d is None:
                continue
            if ds <= d <= de:
                filtered.append(p)
        paths = filtered
    if args.max_samples > 0:
        paths = paths[: args.max_samples]
    if not paths:
        raise SystemExit(f"No .npz files matched in {data_dir}")

    model = None
    if args.model:
        import tensorflow as tf

        model = tf.keras.models.load_model(args.model, compile=False)
        print(f"loaded_model={args.model} input_shape={model.input_shape} output_shape={model.output_shape}")
    else:
        print("model=NONE (using baseline y_pred = PrevFireMask channel)")

    prev_idx = INPUT_FEATURES.index("PrevFireMask")

    y_true_all: List[np.ndarray] = []
    y_score_all: List[np.ndarray] = []

    for p in paths:
        X, y = _load_npz(p)
        if model is None:
            y_pred = X[..., prev_idx : prev_idx + 1]
        else:
            y_pred = model.predict(X[None, ...], verbose=0)[0]
            if y_pred.ndim == 2:
                y_pred = y_pred[..., None]

        y_true_all.append(_flatten(y))
        y_score_all.append(_flatten(y_pred))

    y_true = np.concatenate(y_true_all, axis=0)
    y_score = np.concatenate(y_score_all, axis=0)

    # Clamp scores to [0,1] just in case
    y_score = np.clip(y_score, 0.0, 1.0)

    pos_rate = float((y_true >= 0.5).mean())
    print(f"samples={len(paths)} pixels={y_true.size} pos_rate={pos_rate:.6f}")

    thr_metrics = _metrics_at_threshold(y_true, y_score, args.threshold)
    auc = _auc_metrics(y_true, y_score)
    prob = _prob_metrics(y_true, y_score)

    print(
        "metrics="
        + str(
            {
                "accuracy": round(thr_metrics["accuracy"], 6),
                "precision": round(thr_metrics["precision"], 6),
                "recall": round(thr_metrics["recall"], 6),
                "f1": round(thr_metrics["f1"], 6),
                "iou": round(thr_metrics["iou"], 6),
                "dice": round(thr_metrics["dice"], 6),
                "specificity": round(thr_metrics["specificity"], 6),
                "fpr": round(thr_metrics["fpr"], 6),
                "fnr": round(thr_metrics["fnr"], 6),
                "balanced_accuracy": round(thr_metrics["balanced_accuracy"], 6),
                "mcc": round(thr_metrics["mcc"], 6),
                "brier": round(prob["brier"], 6),
                "log_loss": round(prob["log_loss"], 6),
                "roc_auc": (None if np.isnan(float(auc.get("roc_auc", float("nan")))) else round(float(auc["roc_auc"]), 6)),
                "pr_auc": (None if np.isnan(float(auc.get("pr_auc", float("nan")))) else round(float(auc["pr_auc"]), 6)),
                "threshold": thr_metrics["threshold"],
            }
        )
    )

    print(
        f"confusion_matrix=[[tn={thr_metrics['tn']}, fp={thr_metrics['fp']}], "
        f"[fn={thr_metrics['fn']}, tp={thr_metrics['tp']}]]"
    )

    if args.cm_out:
        import matplotlib.pyplot as plt

        cm = np.array(
            [[thr_metrics["tn"], thr_metrics["fp"]], [thr_metrics["fn"], thr_metrics["tp"]]],
            dtype=np.int64,
        )
        fig, ax = plt.subplots(1, 1, figsize=(4.5, 4))
        im = ax.imshow(cm, cmap="Blues")
        ax.set_title(f"Confusion Matrix (thr={thr_metrics['threshold']})")
        ax.set_xlabel("Predicted")
        ax.set_ylabel("Actual")
        ax.set_xticks([0, 1])
        ax.set_yticks([0, 1])
        ax.set_xticklabels(["0 (no fire)", "1 (fire)"])
        ax.set_yticklabels(["0 (no fire)", "1 (fire)"])
        for (i, j), v in np.ndenumerate(cm):
            ax.text(j, i, str(int(v)), ha="center", va="center", color="black", fontsize=10)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        plt.tight_layout()
        out = Path(args.cm_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(out, dpi=150)
        plt.close()
        print(f"wrote_confusion_matrix_png={out.resolve()}")


if __name__ == "__main__":
    main()

