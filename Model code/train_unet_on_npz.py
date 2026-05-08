"""
Train a U-Net (from wildfire_cnn_us_california.py) on your generated 2D map dataset.

Dataset format: directory of .npz files (e.g., unet_bay_area_2020/)
Each file must contain:
  - X: float32 (H, W, 12)  (already normalized like the Kaggle dataset)
  - y: float32 (H, W, 1)   (0/1 next-day fire mask)

PowerShell example:
  python train_unet_on_npz.py --data-dir unet_bay_area_2020 --pixels 64 --epochs 20 --model-out wildfire_unet_npz.keras

Tip: start with a shorter window (Aug-Sep 2020) and smaller pixels (32) for fast iteration.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import numpy as np
import tensorflow as tf


def build_unet(input_shape=(32, 32, 12), num_filters_start=64) -> tf.keras.Model:
    from tensorflow.keras import Model, layers

    inputs = layers.Input(shape=input_shape)

    # Encoder
    c1 = layers.Conv2D(num_filters_start, 3, activation="relu", padding="same")(inputs)
    c1 = layers.Conv2D(num_filters_start, 3, activation="relu", padding="same")(c1)
    c1 = layers.BatchNormalization()(c1)
    p1 = layers.MaxPooling2D(pool_size=(2, 2))(c1)
    p1 = layers.Dropout(0.2)(p1)

    c2 = layers.Conv2D(num_filters_start * 2, 3, activation="relu", padding="same")(p1)
    c2 = layers.Conv2D(num_filters_start * 2, 3, activation="relu", padding="same")(c2)
    c2 = layers.BatchNormalization()(c2)
    p2 = layers.MaxPooling2D(pool_size=(2, 2))(c2)
    p2 = layers.Dropout(0.2)(p2)

    c3 = layers.Conv2D(num_filters_start * 4, 3, activation="relu", padding="same")(p2)
    c3 = layers.Conv2D(num_filters_start * 4, 3, activation="relu", padding="same")(c3)
    c3 = layers.BatchNormalization()(c3)
    p3 = layers.MaxPooling2D(pool_size=(2, 2))(c3)
    p3 = layers.Dropout(0.3)(p3)

    # Bottleneck
    c4 = layers.Conv2D(num_filters_start * 8, 3, activation="relu", padding="same")(p3)
    c4 = layers.Conv2D(num_filters_start * 8, 3, activation="relu", padding="same")(c4)
    c4 = layers.BatchNormalization()(c4)
    c4 = layers.Dropout(0.3)(c4)

    # Decoder
    u5 = layers.Conv2DTranspose(num_filters_start * 4, 2, strides=(2, 2), padding="same")(c4)
    u5 = layers.concatenate([u5, c3])
    c5 = layers.Conv2D(num_filters_start * 4, 3, activation="relu", padding="same")(u5)
    c5 = layers.Conv2D(num_filters_start * 4, 3, activation="relu", padding="same")(c5)
    c5 = layers.BatchNormalization()(c5)

    u6 = layers.Conv2DTranspose(num_filters_start * 2, 2, strides=(2, 2), padding="same")(c5)
    u6 = layers.concatenate([u6, c2])
    c6 = layers.Conv2D(num_filters_start * 2, 3, activation="relu", padding="same")(u6)
    c6 = layers.Conv2D(num_filters_start * 2, 3, activation="relu", padding="same")(c6)
    c6 = layers.BatchNormalization()(c6)

    u7 = layers.Conv2DTranspose(num_filters_start, 2, strides=(2, 2), padding="same")(c6)
    u7 = layers.concatenate([u7, c1])
    c7 = layers.Conv2D(num_filters_start, 3, activation="relu", padding="same")(u7)
    c7 = layers.Conv2D(num_filters_start, 3, activation="relu", padding="same")(c7)
    c7 = layers.BatchNormalization()(c7)

    outputs = layers.Conv2D(1, 1, activation="sigmoid", padding="same")(c7)
    return Model(inputs=[inputs], outputs=[outputs])


def weighted_bce_loss(fire_weight: float = 20.0, no_fire_weight: float = 1.0):
    fw = float(fire_weight)
    nw = float(no_fire_weight)

    def loss(y_true, y_pred):
        y_pred = tf.clip_by_value(y_pred, 1e-7, 1.0 - 1e-7)
        l = -(
            fw * y_true * tf.math.log(y_pred)
            + nw * (1.0 - y_true) * tf.math.log(1.0 - y_pred)
        )
        return tf.reduce_mean(l)

    return loss


def list_npz(data_dir: Path, pattern: str) -> List[Path]:
    rx = re.compile(pattern)
    return sorted([p for p in data_dir.iterdir() if p.is_file() and rx.match(p.name)])


def load_npz_xy(path: Path) -> Tuple[np.ndarray, np.ndarray]:
    z = np.load(path)
    X = np.asarray(z["X"], dtype=np.float32)
    y = np.asarray(z["y"], dtype=np.float32)
    return X, y


def make_dataset(paths: List[Path], *, batch_size: int, shuffle: bool, seed: int) -> tf.data.Dataset:
    def gen():
        for p in paths:
            X, y = load_npz_xy(p)
            yield X, y

    # Peek one sample to define signature
    X0, y0 = load_npz_xy(paths[0])
    ds = tf.data.Dataset.from_generator(
        gen,
        output_signature=(
            tf.TensorSpec(shape=X0.shape, dtype=tf.float32),
            tf.TensorSpec(shape=y0.shape, dtype=tf.float32),
        ),
    )
    if shuffle:
        ds = ds.shuffle(buffer_size=min(2048, len(paths)), seed=seed, reshuffle_each_iteration=True)
    ds = ds.batch(batch_size).prefetch(tf.data.AUTOTUNE)
    return ds


def steps_for(n_files: int, batch_size: int) -> int:
    return int(np.ceil(n_files / max(1, batch_size)))


@dataclass
class Split:
    train: List[Path]
    val: List[Path]
    test: List[Path]


def time_split(paths: List[Path], train_frac: float, val_frac: float) -> Split:
    n = len(paths)
    if n < 3:
        raise ValueError(f"Need at least 3 samples to split train/val/test; have n={n}")

    # Ensure each split gets at least 1 file.
    n_val = max(1, int(n * val_frac))
    n_test = max(1, int(n * (1.0 - train_frac - val_frac)))
    n_train = n - n_val - n_test
    if n_train < 1:
        n_train = 1
        # Re-adjust val/test to fit
        remaining = n - n_train
        n_val = max(1, min(n_val, remaining - 1))
        n_test = remaining - n_val

    return Split(train=paths[:n_train], val=paths[n_train : n_train + n_val], test=paths[n_train + n_val :])


def main() -> None:
    ap = argparse.ArgumentParser(description="Train U-Net on .npz (X,y) samples.")
    ap.add_argument("--data-dir", required=True, help="Directory containing unet_YYYY-MM-DD.npz files.")
    # Regex for filenames like: unet_2020-09-10.npz
    ap.add_argument("--pattern", default=r"unet_\d{4}-\d{2}-\d{2}\.npz")
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--epochs", type=int, default=20)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--pixels", type=int, default=64, help="Expected H=W size (32/64).")
    ap.add_argument("--filters", type=int, default=64, help="Base number of filters.")
    ap.add_argument("--fire-weight", type=float, default=20.0)
    ap.add_argument("--no-fire-weight", type=float, default=1.0)
    ap.add_argument("--train-frac", type=float, default=0.7)
    ap.add_argument("--val-frac", type=float, default=0.15)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--model-out", default="wildfire_unet_npz.keras")
    ap.add_argument("--history-csv", default=None, help="Optional: write training history to CSV.")
    ap.add_argument("--plots-out", default=None, help="Optional: write training curves PNG.")
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    paths = list_npz(data_dir, args.pattern)
    if not paths:
        raise SystemExit(f"No .npz files found in {data_dir} matching {args.pattern}")

    # Sanity check one sample shape
    X0, y0 = load_npz_xy(paths[0])
    if X0.shape[0] != args.pixels or X0.shape[1] != args.pixels:
        print(f"WARNING: first X shape={X0.shape}; you passed --pixels {args.pixels}")
    if X0.shape[-1] != 12 or y0.shape[-1] != 1:
        raise SystemExit(f"Expected X[...,12] and y[...,1]. Got X={X0.shape} y={y0.shape}")

    split = time_split(paths, args.train_frac, args.val_frac)
    print(f"files train/val/test: {len(split.train)}/{len(split.val)}/{len(split.test)}")

    train_ds = make_dataset(split.train, batch_size=args.batch_size, shuffle=True, seed=args.seed)
    val_ds = make_dataset(split.val, batch_size=args.batch_size, shuffle=False, seed=args.seed)
    test_ds = make_dataset(split.test, batch_size=args.batch_size, shuffle=False, seed=args.seed)

    model = build_unet(input_shape=(args.pixels, args.pixels, 12), num_filters_start=args.filters)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=args.lr),
        loss=weighted_bce_loss(args.fire_weight, args.no_fire_weight),
        metrics=[
            tf.keras.metrics.AUC(name="auc", curve="ROC"),
            tf.keras.metrics.AUC(name="pr_auc", curve="PR"),
            tf.keras.metrics.Precision(name="precision"),
            tf.keras.metrics.Recall(name="recall"),
            tf.keras.metrics.BinaryAccuracy(name="accuracy", threshold=0.5),
        ],
    )

    cb = [
        tf.keras.callbacks.EarlyStopping(monitor="val_pr_auc", mode="max", patience=5, restore_best_weights=True),
        tf.keras.callbacks.ModelCheckpoint(args.model_out, monitor="val_pr_auc", mode="max", save_best_only=True),
        tf.keras.callbacks.ReduceLROnPlateau(monitor="val_pr_auc", mode="max", factor=0.5, patience=2, verbose=1),
    ]

    # Repeat train forever so Keras doesn't stop early on small datasets.
    train_steps = steps_for(len(split.train), args.batch_size)
    val_steps = steps_for(len(split.val), args.batch_size)
    hist = model.fit(
        train_ds.repeat(),
        steps_per_epoch=train_steps,
        validation_data=val_ds.repeat(),
        validation_steps=val_steps,
        epochs=args.epochs,
        callbacks=cb,
        verbose=1,
    )
    print(f"saved_best_model={args.model_out}")

    # Training curves + history export
    if args.history_csv or args.plots_out:
        try:
            import pandas as pd

            dfh = pd.DataFrame(hist.history)
            dfh.insert(0, "epoch", np.arange(1, len(dfh) + 1))
            if args.history_csv:
                out_csv = Path(args.history_csv)
                out_csv.parent.mkdir(parents=True, exist_ok=True)
                dfh.to_csv(out_csv, index=False)
                print(f"wrote_history_csv={out_csv.resolve()}")

            if args.plots_out:
                import matplotlib.pyplot as plt

                out_png = Path(args.plots_out)
                out_png.parent.mkdir(parents=True, exist_ok=True)

                # Choose common metric keys if present
                keys = [
                    ("loss", "val_loss", "Loss"),
                    ("auc", "val_auc", "ROC-AUC"),
                    ("pr_auc", "val_pr_auc", "PR-AUC"),
                    ("precision", "val_precision", "Precision"),
                    ("recall", "val_recall", "Recall"),
                    ("accuracy", "val_accuracy", "Accuracy"),
                ]
                present = [(a, b, t) for (a, b, t) in keys if a in dfh.columns or b in dfh.columns]

                nrows = int(np.ceil(len(present) / 2)) if present else 1
                fig, axes = plt.subplots(nrows, 2, figsize=(12, 3.2 * nrows))
                axes = np.atleast_2d(axes)

                for i, (a, b, title) in enumerate(present):
                    ax = axes[i // 2, i % 2]
                    if a in dfh.columns:
                        ax.plot(dfh["epoch"], dfh[a], label=a)
                    if b in dfh.columns:
                        ax.plot(dfh["epoch"], dfh[b], label=b)
                    ax.set_title(title)
                    ax.set_xlabel("epoch")
                    ax.grid(True, alpha=0.3)
                    ax.legend()

                # Hide unused subplots
                for j in range(len(present), nrows * 2):
                    axes[j // 2, j % 2].axis("off")

                plt.tight_layout()
                plt.savefig(out_png, dpi=150, bbox_inches="tight")
                plt.close()
                print(f"wrote_training_plots={out_png.resolve()}")
        except Exception as e:
            print(f"history_plot_skipped={e}")

    metrics = model.evaluate(test_ds, verbose=0)
    print("test_metrics=" + str(dict(zip(model.metrics_names, [float(x) for x in metrics]))))


if __name__ == "__main__":
    main()

