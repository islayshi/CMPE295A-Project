"""Forward pass of the physics-informed fusion UNet (NumPy only; the training code with the backward pass lives in
the WildfirePINN research repo, rl/ens/fusion_net.py). Weights: 3 independently trained copies, averaged.

  enc:  conv3x3(C->F) relu, conv3x3(F->F) relu                         (S x S)
  mid:  avgpool2, conv3x3(F->2F) relu, conv3x3(2F->2F) relu            (S/2)
  dec:  upsample2, concat enc, conv3x3(3F->F) relu, conv1x1(F->2)       (S x S)
  out:  logits + a_h * logit(PIML_h) + b_h * logit(U-Net_h)            (h = +3 h, +6 h)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view as _sw

from .channels import CH, IDX

EPS = 1e-4
WEIGHTS = Path(__file__).resolve().parent / "weights"


def logit(p):
    p = np.clip(p, EPS, 1 - EPS)
    return np.log(p / (1 - p))


def _conv(x, w, b):
    if w.shape[-1] == 1:
        return np.einsum("nchw,oc->nohw", x, w[:, :, 0, 0], optimize=True) + b[None, :, None, None]
    win = _sw(np.pad(x, ((0, 0), (0, 0), (1, 1), (1, 1))), (3, 3), axis=(2, 3))
    return np.einsum("nchwij,ocij->nohw", win, w, optimize=True) + b[None, :, None, None]


def _pool(x):
    n, c, h, w = x.shape
    return x.reshape(n, c, h // 2, 2, w // 2, 2).mean((3, 5))


def _up(x):
    return np.repeat(np.repeat(x, 2, 2), 2, 3)


class FusionNet:
    def __init__(self, params: dict, norm_idx, mu, sd):
        self.p = params
        self.norm_idx, self.mu, self.sd = np.asarray(norm_idx), np.asarray(mu), np.asarray(sd)

    @classmethod
    def load(cls, path) -> "FusionNet":
        z = np.load(path)
        params = {k[2:]: z[k] for k in z.files if k.startswith("p_")}
        if list(z["channels"]) != CH:
            raise ValueError(f"{path}: channel list does not match fusion/channels.py")
        return cls(params, z["norm_idx"], z["norm_mu"], z["norm_sd"])

    def normalise(self, X):
        X = X.copy()
        X[:, self.norm_idx] = (X[:, self.norm_idx] - self.mu[None, :, None, None]) / self.sd[None, :, None, None]
        return X

    def logits(self, X):
        """X: (N, 33, S, S) raw stacked inputs (S divisible by 2). Returns logits (N, 2, S, S) for +3 h, +6 h."""
        p = self.p
        Z = self.normalise(X)
        a1 = np.maximum(_conv(Z, p["w1"], p["b1"]), 0)
        a2 = np.maximum(_conv(a1, p["w2"], p["b2"]), 0)
        a3 = np.maximum(_conv(_pool(a2), p["w3"], p["b3"]), 0)
        a4 = np.maximum(_conv(a3, p["w4"], p["b4"]), 0)
        a5 = np.maximum(_conv(np.concatenate([_up(a4), a2], 1), p["w5"], p["b5"]), 0)
        o = _conv(a5, p["w6"], p["b6"])
        Lp = logit(Z[:, [IDX["pinn3"], IDX["pinn6"]]])
        Lu = logit(Z[:, [IDX["unet_seed3"], IDX["unet_seed6"]]])
        has_u = Z[:, IDX["has_unet"]][:, None]
        return o + p["a"][None, :, None, None] * Lp + p["bu"][None, :, None, None] * Lu * has_u


def load_copies(folder=WEIGHTS) -> list[FusionNet]:
    files = sorted(Path(folder).glob("fusion_s*.npz"))
    if not files:
        raise FileNotFoundError(f"no fusion weights in {folder}")
    return [FusionNet.load(f) for f in files]


def predict_raw(nets: list[FusionNet], X: np.ndarray):
    """Mean over the copies of sigmoid(logits): (+3 h, +6 h, std of +6 h across copies), each (N, S, S)."""
    outs = np.array([1 / (1 + np.exp(-n.logits(X))) for n in nets])       # copies, N, 2, S, S
    return outs[:, :, 0].mean(0), outs[:, :, 1].mean(0), outs[:, :, 1].std(0)
