"""The U-Net service's 1 km lattice (EPSG:3310, NAD83 California Albers), so PIML and U-Net cells share grid_ids.

The U-Net service (ml_services/unet_service/settings.py) numbers cells on a fixed 1 km lattice:
    x0 = -430000 m, y0 = 480000 m (north-west corner), 1000 columns, row 0 at the top,
    grid_id = row * 1000 + col.
The ML adapter merges U-Net and PIML forecasts cell by cell on grid_id, so the PIML service must use the
same numbering. pyproj is not needed: EPSG:3310 is computed here with Snyder's ellipsoidal Albers formulas
(GRS80; agrees with pyproj to well under a millimetre over California).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

LATTICE_X0 = -430000.0
LATTICE_Y0 = 480000.0
LATTICE_NCOLS = 1000
LATTICE_NROWS = 1200      # down to y = -720 km, south of the Mexican border
RES_M = 1000.0

_A, _F = 6378137.0, 1 / 298.257222101
_E2 = _F * (2 - _F)
_E = math.sqrt(_E2)


def _q(phi):
    s = np.sin(phi)
    return (1 - _E2) * (s / (1 - _E2 * s * s) - (1 / (2 * _E)) * np.log((1 - _E * s) / (1 + _E * s)))


def _m(phi):
    s = np.sin(phi)
    return np.cos(phi) / np.sqrt(1 - _E2 * s * s)


_P1, _P2, _P0, _L0 = np.deg2rad(34.0), np.deg2rad(40.5), 0.0, np.deg2rad(-120.0)
_N = (_m(_P1) ** 2 - _m(_P2) ** 2) / (_q(_P2) - _q(_P1))
_C = _m(_P1) ** 2 + _N * _q(_P1)
_RHO0 = _A * np.sqrt(_C - _N * _q(_P0)) / _N
_FALSE_NORTHING = -4000000.0


def to_3310(lon, lat):
    """lon/lat (degrees) -> EPSG:3310 x, y (metres)."""
    phi, lam = np.deg2rad(np.asarray(lat, float)), np.deg2rad(np.asarray(lon, float))
    rho = _A * np.sqrt(_C - _N * _q(phi)) / _N
    th = _N * (lam - _L0)
    return rho * np.sin(th), _RHO0 - rho * np.cos(th) + _FALSE_NORTHING


def from_3310(x, y):
    """EPSG:3310 x, y (metres) -> lon, lat (degrees)."""
    x, y = np.asarray(x, float), np.asarray(y, float) - _FALSE_NORTHING
    rho = np.hypot(x, _RHO0 - y)
    th = np.arctan2(x, _RHO0 - y)
    lam = _L0 + th / _N
    q = (_C - (rho * _N / _A) ** 2) / _N
    phi = np.arcsin(np.clip(q / 2, -1, 1))
    for _ in range(8):
        s = np.sin(phi)
        phi = phi + (1 - _E2 * s * s) ** 2 / (2 * np.cos(phi)) * (
            q / (1 - _E2) - s / (1 - _E2 * s * s) + (1 / (2 * _E)) * np.log((1 - _E * s) / (1 + _E * s)))
    return np.rad2deg(lam), np.rad2deg(phi)


def clip_ring_to_bbox(ring, bbox, ndp=6):
    """Cut a closed [lon, lat] ring to the bbox (Sutherland-Hodgman). Returns a closed ring or None."""
    w, s, e, n = bbox
    pts = [list(p) for p in ring[:-1]]

    def cross_x(a, b, x):
        t = (x - a[0]) / (b[0] - a[0])
        return [x, a[1] + t * (b[1] - a[1])]

    def cross_y(a, b, y):
        t = (y - a[1]) / (b[1] - a[1])
        return [a[0] + t * (b[0] - a[0]), y]

    edges = ((lambda p: p[0] >= w, lambda a, b: cross_x(a, b, w)), (lambda p: p[0] <= e, lambda a, b: cross_x(a, b, e)),
             (lambda p: p[1] >= s, lambda a, b: cross_y(a, b, s)), (lambda p: p[1] <= n, lambda a, b: cross_y(a, b, n)))
    out = pts
    for inside, cross in edges:
        nxt = []
        for i, cur in enumerate(out):
            prev = out[i - 1]
            if inside(cur):
                if not inside(prev):
                    nxt.append(cross(prev, cur))
                nxt.append(cur)
            elif inside(prev):
                nxt.append(cross(prev, cur))
        out = nxt
        if not out:
            return None
    pts = []
    for x, y in out:
        p = [round(min(max(x, w), e), ndp), round(min(max(y, s), n), ndp)]
        if not pts or p != pts[-1]:
            pts.append(p)
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts.pop()
    if len(pts) < 3:
        return None
    area = 0.5 * sum(pts[i - 1][0] * pts[i][1] - pts[i][0] * pts[i - 1][1] for i in range(len(pts)))
    if abs(area) < 1e-10:
        return None
    return pts + [pts[0]]


@dataclass(frozen=True)
class LatticeGrid:
    """Same interface as postprocessing.GridSpec; the flat index IS the grid_id (row * 1000 + col)."""

    name: str = "U-Net 1 km lattice (EPSG:3310, grid_id = row * 1000 + col)"
    provisional: bool = False
    resolution_km: float = RES_M / 1000.0

    def locate(self, lon, lat) -> np.ndarray:
        x, y = to_3310(lon, lat)
        col = np.floor((np.asarray(x) - LATTICE_X0) / RES_M).astype(np.int64)
        row = np.floor((LATTICE_Y0 - np.asarray(y)) / RES_M).astype(np.int64)
        ok = (col >= 0) & (col < LATTICE_NCOLS) & (row >= 0) & (row < LATTICE_NROWS)
        flat = row * LATTICE_NCOLS + col
        return np.where(ok & (flat > 0), flat, -1)

    def grid_id(self, flat: int) -> int:
        return int(flat)

    def corners(self, flat: int):
        """Closed [lon, lat] ring of the cell, counter-clockwise (same as the U-Net service's grid_id_to_polygon)."""
        r, c = divmod(int(flat), LATTICE_NCOLS)
        xs = [LATTICE_X0 + c * RES_M, LATTICE_X0 + (c + 1) * RES_M]
        ys = [LATTICE_Y0 - (r + 1) * RES_M, LATTICE_Y0 - r * RES_M]
        lon, lat = from_3310([xs[0], xs[1], xs[1], xs[0], xs[0]], [ys[0], ys[0], ys[1], ys[1], ys[0]])
        return [[round(float(a), 6), round(float(b), 6)] for a, b in zip(lon, lat)]

    def bounds(self, flat: int) -> tuple[float, float, float, float]:
        ring = np.array(self.corners(flat))
        return float(ring[:, 0].min()), float(ring[:, 1].min()), float(ring[:, 0].max()), float(ring[:, 1].max())

    def ring(self, flat: int, bbox) -> list[list[float]] | None:
        return clip_ring_to_bbox(self.corners(flat), bbox)
