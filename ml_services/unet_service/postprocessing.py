"""Model grid -> GeoJSON: grid ids, cell polygons, risk labels, one FeatureCollection for all horizons, bbox clipping."""
import math
import numpy as np, pandas as pd
from dataclasses import dataclass
from settings import *


@dataclass(frozen=True)
class Grid:
    x0: float   # west edge (m)
    y0: float   # north edge (m)
    h: int
    w: int
    res: float = RES_M

    @classmethod
    def around_xy(cls, x, y, size=GOES_TILE, res=RES_M):
        c0 = round((x - size * res / 2 - LATTICE_X0) / res)
        r0 = round((LATTICE_Y0 - (y + size * res / 2)) / res)
        return cls(LATTICE_X0 + c0 * res, LATTICE_Y0 - r0 * res, size, size, res)

    @classmethod
    def around(cls, lat, lon, size=GOES_TILE, res=RES_M):
        return cls.around_xy(*_to_grid.transform(lon, lat), size=size, res=res)

    @property
    def bounds(self):
        return self.x0, self.x0 + self.w * self.res, self.y0 - self.h * self.res, self.y0

    def centers(self):
        xs = self.x0 + (np.arange(self.w) + 0.5) * self.res
        ys = self.y0 - (np.arange(self.h) + 0.5) * self.res
        return np.meshgrid(xs, ys)

    def grid_ids(self):
        ncols = int(round(LATTICE_NCOLS * RES_M / self.res))      # 1000 for 1 km cells, 4000 for 250 m cells
        c0 = round((self.x0 - LATTICE_X0) / self.res)
        r0 = round((LATTICE_Y0 - self.y0) / self.res)
        r, c = np.mgrid[r0:r0 + self.h, c0:c0 + self.w]
        return (r * ncols + c).astype(np.int64)


def grid_id_to_center_lonlat(gid, res=RES_M):
    r, c = divmod(int(gid), LATTICE_NCOLS)
    return _to_wgs.transform(LATTICE_X0 + (c + 0.5) * res, LATTICE_Y0 - (r + 0.5) * res)


def risk_label(p, thr):
    return np.where(p >= thr['HIGH_RISK'], 'HIGH_RISK',
                    np.where(p >= thr['MODERATE_RISK'], 'MODERATE_RISK', 'LOW_RISK'))


def to_geojson(p, grid, timestamp, thr, p_emit=P_EMIT, burned=None, extra_layers=None, collection_props=None, ndp=6):
    p = np.asarray(p, float)
    burned = np.zeros(p.shape, bool) if burned is None else np.asarray(burned, bool)
    ids, labels = grid.grid_ids(), risk_label(np.nan_to_num(p), thr)
    cx = grid.x0 + np.arange(grid.w + 1) * grid.res
    cy = grid.y0 - np.arange(grid.h + 1) * grid.res
    LON, LAT = _to_wgs.transform(*np.meshgrid(cx, cy))
    LON, LAT = np.round(LON, ndp), np.round(LAT, ndp)
    feats = []
    rows, cols = np.where((np.isfinite(p) & (p >= p_emit)) | burned)
    for r, c in zip(rows.tolist(), cols.tolist()):
        # SW, SE, NE, NW, SW
        ring = [[LON[r + 1, c], LAT[r + 1, c]], [LON[r + 1, c + 1], LAT[r + 1, c + 1]],
                [LON[r, c + 1], LAT[r, c + 1]], [LON[r, c], LAT[r, c]], [LON[r + 1, c], LAT[r + 1, c]]]
        if burned[r, c]:
            props = {'grid_id': int(ids[r, c]), 'fire_probability': 1.0, 'risk_label': 'ACTIVE_FIRE'}
        else:
            props = {'grid_id': int(ids[r, c]), 'fire_probability': round(float(p[r, c]), 3),
                     'risk_label': str(labels[r, c])}
        for name, layer in (extra_layers or {}).items():
            if layer is not None:
                v = layer[r, c]
                props[name] = None if not np.isfinite(v) else round(float(v), 3)
        feats.append({'type': 'Feature', 'properties': props,
                      'geometry': {'type': 'Polygon', 'coordinates': [[[float(a), float(b)] for a, b in ring]]}})
    fc = {'type': 'FeatureCollection', 'timestamp': timestamp}
    fc.update(collection_props or {})
    fc['features'] = feats
    return fc


def validate_feature_collection(fc):
    ids = [f['properties']['grid_id'] for f in fc['features']]
    assert len(ids) == len(set(ids)), 'duplicate grid_id'
    for f in fc['features']:
        ring = f['geometry']['coordinates'][0]
        assert len(ring) == 5 and ring[0] == ring[-1], 'ring not closed'
        assert sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(ring[:-1], ring[1:])) > 0, 'ring not counter-clockwise'
        pr = f['properties']
        assert 0 <= pr['fire_probability'] <= 1
        assert pr['risk_label'] in {'LOW_RISK', 'MODERATE_RISK', 'HIGH_RISK', 'ACTIVE_FIRE'}
    json.dumps(fc)


def grid_id_to_polygon(gid, res=RES_M):
    """Full (unclipped) [lon, lat] ring of a 1 km lattice cell, counter-clockwise, closed."""
    r, c = divmod(int(gid), LATTICE_NCOLS)
    xs = [LATTICE_X0 + c * res, LATTICE_X0 + (c + 1) * res]
    ys = [LATTICE_Y0 - (r + 1) * res, LATTICE_Y0 - r * res]
    lon, lat = _to_wgs.transform([xs[0], xs[1], xs[1], xs[0], xs[0]], [ys[0], ys[0], ys[1], ys[1], ys[0]])
    return [[round(a, 6), round(b, 6)] for a, b in zip(lon, lat)]


def model_grid_for_bbox(bbox, min_km=GOES_TILE, max_km=MAX_BBOX_KM):
    """Square model grid centred on the bbox: at least min_km wide (the model needs context), a multiple of 16 cells."""
    w, s, e, n = bbox
    xs, ys = _to_grid.transform([w, e, e, w], [s, s, n, n])
    span_km = max(max(xs) - min(xs), max(ys) - min(ys)) / 1000.0
    if span_km > max_km:
        raise ValueError(f'bbox is {span_km:.0f} km across; the largest supported is {max_km} km')
    size = max(min_km, int(math.ceil((span_km + 2) / 16.0)) * 16)
    return Grid.around_xy((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, size=size)


def _cross_x(a, b, x):
    t = (x - a[0]) / (b[0] - a[0])
    return [x, a[1] + t * (b[1] - a[1])]


def _cross_y(a, b, y):
    t = (y - a[1]) / (b[1] - a[1])
    return [a[0] + t * (b[0] - a[0]), y]


def _ring_area(pts):
    return 0.5 * sum(pts[i - 1][0] * pts[i][1] - pts[i][0] * pts[i - 1][1] for i in range(len(pts)))


def clip_ring_to_bbox(ring, bbox, ndp=5):
    """Cuts a closed [lon, lat] ring to the bbox (keeps it a single Polygon). Returns a closed ring, or None if nothing is left."""
    w, s, e, n = bbox
    pts = [list(p) for p in ring[:-1]]
    if all(w <= x <= e and s <= y <= n for x, y in pts):
        out = pts
    else:
        edges = ((lambda p: p[0] >= w, lambda a, b: _cross_x(a, b, w)), (lambda p: p[0] <= e, lambda a, b: _cross_x(a, b, e)),
                 (lambda p: p[1] >= s, lambda a, b: _cross_y(a, b, s)), (lambda p: p[1] <= n, lambda a, b: _cross_y(a, b, n)))
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
    rounded = []
    for x, y in out:
        p = [round(min(max(x, w), e), ndp), round(min(max(y, s), n), ndp)]
        if not rounded or p != rounded[-1]:
            rounded.append(p)
    if len(rounded) > 1 and rounded[0] == rounded[-1]:
        rounded.pop()
    if len(rounded) < 3 or abs(_ring_area(rounded)) < 1e-10:
        return None
    return rounded + [rounded[0]]


def unified_feature_collection(layers, bbox, issue_time, p_min=P_EMIT, source_model='unet', status='ok', extra_metadata=None):
    """One FeatureCollection for all horizons. layers: [{'h', 'p', 'grid', 'thresholds', 'burned'}]."""
    fmt = '%Y-%m-%dT%H:%M:%SZ'
    feats = []
    for lay in layers:
        fc = to_geojson(lay['p'], lay['grid'], '', lay['thresholds'], p_emit=p_min, burned=lay['burned'])
        for f in fc['features']:
            ring = clip_ring_to_bbox(f['geometry']['coordinates'][0], bbox)
            if ring is None:
                continue
            props = f['properties']
            props.update({'horizon_hours': int(lay['h']), 'source_model': source_model, 'w_unet': 1.0, 'members': 1})
            feats.append({'type': 'Feature', 'geometry': {'type': 'Polygon', 'coordinates': [ring]}, 'properties': props})
    meta = {'timestamp': pd.Timestamp.now('UTC').strftime(fmt), 'issue_time': pd.Timestamp(issue_time).strftime(fmt),
            'source_model': source_model, 'model_version': MODEL_VERSION, 'grid_resolution_km': RES_M / 1000.0,
            'total_cells': len(feats), 'status': status, 'bbox': [float(v) for v in bbox],
            'horizons': sorted({int(l['h']) for l in layers}),
            'risk_thresholds': {str(l['h']): {k: round(float(v), 4) for k, v in l['thresholds'].items()}
                                for l in layers if l['h'] > 0}}
    meta.update(extra_metadata or {})
    return {'type': 'FeatureCollection', 'metadata': meta, 'features': feats}


__all__ = [n for n in list(globals()) if not n.startswith('__')]   # lets the other modules import every name