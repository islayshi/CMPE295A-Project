"""Models: loading, running the hourly (+1/+3/+6 h) and daily (+24 h) U-Nets, and answering requests."""
import os, json
import numpy as np, pandas as pd, joblib
import tensorflow as tf
from dataclasses import dataclass, field
from settings import *
from postprocessing import *
from native_ingestion import *


def current_fire_geojson(grid, t_end, hours=1):
    t_end = _utc(t_end)
    conf, _, frp = goes_aws_hourly(grid, t_end - pd.Timedelta(hours=hours), hours)
    c, f = conf.max(-1), frp.max(-1)
    fmt = '%Y-%m-%dT%H:%M:%SZ'
    return to_geojson(np.zeros_like(c), grid, t_end.strftime(fmt), {'MODERATE_RISK': 1, 'HIGH_RISK': 1},
                      p_emit=2.0, burned=c >= FIRE_THRESHOLD, extra_layers={'fire_confidence': c, 'frp_mw': f},
                      collection_props={'layer': 'current_fire_detection', 'source': f'GOES-18 {GOES_PRODUCT}',
                                        'window_start': (t_end - pd.Timedelta(hours=hours)).strftime(fmt),
                                        'window_end': t_end.strftime(fmt)})


def goes_normalize(X, mu, sd):
    bad = ~(np.isfinite(mu) & np.isfinite(sd))       # bundles trained before the -inf fix have no stats for rain/NDVI
    with np.errstate(invalid='ignore', divide='ignore'):
        z = (np.asarray(X, np.float32) - np.where(bad, 0, mu)) / np.where(bad, 1, sd)
    z[..., bad] = 0.0
    return np.clip(np.nan_to_num(z, nan=0.0, posinf=0.0, neginf=0.0), -10, 10).astype(np.float32)


def load_goes_bundle(h):
    bdir = os.path.join(BUNDLE_DIR, f'goes_h{h}')
    norm = json.load(open(os.path.join(bdir, 'norm.json')))
    b = {'model': tf.keras.models.load_model(os.path.join(bdir, 'model.keras'), compile=False),
         'mu': np.array(norm['mu'], np.float32), 'sd': np.array(norm['sd'], np.float32),
         'calibrator': joblib.load(os.path.join(bdir, 'calibrator.joblib')),
         'thresholds': json.load(open(os.path.join(bdir, 'thresholds.json'))),
         'manifest': json.load(open(os.path.join(bdir, 'manifest.json')))}
    bad = [GOES_CHANNELS[i] for i in np.where(~(np.isfinite(b['mu']) & np.isfinite(b['sd'])))[0]]
    if bad:
        print(f'+{h} h model was trained without {bad}; retrain them in the final notebook (Section 8), then rebuild this package')
    return b


def fuse(p_unet, p_pinn=None, w_unet=W_UNET):
    p = np.asarray(p_unet, float).copy()
    if p_pinn is not None:
        both = np.isfinite(p_pinn) & np.isfinite(p)
        p[both] = w_unet * p[both] + (1.0 - w_unet) * p_pinn[both]
    return np.clip(p, 0.0, 1.0)


def goes_forecast(grid, t, bundles):
    """Runs the +1/+3/+6 h models. Returns the model inputs, the 'burned in the last 24 h' mask and {h: (p, None, p)}."""
    x, burned = hourly_inputs(grid, t)
    out = {}
    for h, b in bundles.items():
        p = b['model'](goes_normalize(x, b['mu'], b['sd'])[None], training=False).numpy()[0, :, :, 0]
        p = np.minimum(b['calibrator'].predict(p.ravel()).reshape(p.shape), P_MAX)
        out[h] = (p, None, p)
    return x, burned, out


def mask_invalid(fd):
    fd = dict(fd)
    for f in RAW_INPUTS:
        lo, hi = VALID_RANGE[f]
        x = fd[f]
        fd[f] = tf.where(tf.math.is_finite(x) & (x >= lo) & (x <= hi), x, np.nan)
    fd['PrevFireMask'] = tf.where(tf.math.is_finite(fd['PrevFireMask']), fd['PrevFireMask'], -1.0)
    return fd


def add_wind_uv(fd):
    fd = dict(fd)
    th = fd['th'] * (math.pi / 180.0)
    fd['wind_u'] = -fd['vs'] * tf.sin(th)
    fd['wind_v'] = -fd['vs'] * tf.cos(th)
    return fd


def transform_features(fd, features, stats):
    fd = mask_invalid(fd)
    for f in RAW_INPUTS:
        fd[f] = tf.where(tf.math.is_finite(fd[f]), fd[f], stats[f][2])
    fd = add_wind_uv(fd)
    chans = []
    for f in features:
        x = tf.cast(fd[f], tf.float32)
        if f not in UNNORMALIZED:
            lo, hi, mu, sd = stats[f]
            x = (tf.clip_by_value(x, lo, hi) - mu) / sd
        chans.append(tf.where(tf.math.is_finite(x), x, 0.0))
    return tf.stack(chans, axis=-1)


def load_daily_bundle():
    path = os.path.join(BUNDLE_DIR, 'model.keras')
    if not os.path.exists(path):
        return None
    thr = json.load(open(os.path.join(BUNDLE_DIR, 'thresholds.json')))
    thr = dict(thr['validation'] if thr.get('mode') == 'validation' else thr['fixed'])
    thr['MODERATE_RISK'] = max(thr['MODERATE_RISK'], P_EMIT)
    thr['HIGH_RISK'] = min(thr['HIGH_RISK'], P_MAX)
    if thr['MODERATE_RISK'] >= thr['HIGH_RISK']:
        thr['MODERATE_RISK'] = thr['HIGH_RISK'] / 2
    return {'model': tf.keras.models.load_model(path, compile=False),
            'features': json.load(open(os.path.join(BUNDLE_DIR, 'features.json'))),
            'stats': {k: tuple(v) for k, v in json.load(open(os.path.join(BUNDLE_DIR, 'stats.json'))).items()},
            'calibrator': joblib.load(os.path.join(BUNDLE_DIR, 'calibrator.joblib')),
            'thresholds': thr}


def daily_predict(bundle, raw):
    fd = {k: tf.constant(np.asarray(v, np.float32)) for k, v in raw.items()}
    x = transform_features(fd, bundle['features'], bundle['stats'])[None]
    p = bundle['model'](x, training=False).numpy()[0, :, :, 0]
    return np.minimum(bundle['calibrator'].predict(p.ravel()).reshape(p.shape), P_MAX)


@dataclass
class Layer:
    model: str                  # 'hourly', 'daily', 'pinn' or 'ensemble'
    horizon_h: int
    p: np.ndarray               # fire probability per 1 km cell
    grid: Grid
    thresholds: dict
    burned: np.ndarray          # cells already burning (shown as ACTIVE_FIRE)
    issued: pd.Timestamp
    members: list
    extra: dict = field(default_factory=dict)    # extra per-cell values written to the geojson
    inputs: np.ndarray = None


def get_hourly_bundles():
    if not _HOURLY:
        for h in GOES_HORIZONS_H:
            if os.path.exists(os.path.join(BUNDLE_DIR, f'goes_h{h}', 'model.keras')):
                _HOURLY[h] = load_goes_bundle(h)
    return _HOURLY


def get_daily_bundle():
    if 'bundle' not in _DAILY:
        _DAILY['bundle'] = load_daily_bundle()
    return _DAILY['bundle']


def run_hourly(grid, t):
    bundles = get_hourly_bundles()
    if not bundles:
        print('no hourly models yet (train them in Section 8)')
        return []
    x, burned, out = goes_forecast(grid, t, bundles)
    return [Layer('hourly', h, p_u, grid, bundles[h]['thresholds'], burned, _utc(t).floor('h'), ['unet-goes'], inputs=x)
            for h, (p_u, _, _) in out.items()]


def run_daily(grid, t):
    bundle = get_daily_bundle()
    if bundle is None or not FIRMS_MAP_KEY or not EE_READY:
        print('daily model skipped: needs the saved model, a FIRMS key and Earth Engine')
        return []
    raw, burned = daily_inputs(grid, t)
    p = daily_predict(bundle, raw)
    return [Layer('daily', 24, p, grid, bundle['thresholds'], burned, _utc(t).floor('h'), ['unet-daily'],
                  inputs=raw['PrevFireMask'][..., None])]


def layer_geojson(layer):
    fmt = '%Y-%m-%dT%H:%M:%SZ'
    return to_geojson(layer.p, layer.grid, layer.issued.strftime(fmt), layer.thresholds, burned=layer.burned,
                      extra_layers=layer.extra,
                      collection_props={'valid_time': (layer.issued + pd.Timedelta(hours=layer.horizon_h)).strftime(fmt),
                                        'horizon_hours': layer.horizon_h, 'layer': 'spread_risk', 'model': layer.model,
                                        'members': layer.members, 'risk_thresholds': layer.thresholds})


def available_models():
    hourly = bool(get_hourly_bundles())
    return {'fire_check': True, 'current_fire': True, 'hourly': hourly, 'ensemble': hourly,
            'daily': bool(EE_READY and FIRMS_MAP_KEY and get_daily_bundle() is not None), 'pinn': False}


def serve_request(inst):
    """One request from the backend, e.g. {'model': 'hourly', 'lat': 34.07, 'lon': -118.58, 'time': 'now'}."""
    fmt = '%Y-%m-%dT%H:%M:%SZ'
    model = inst.get('model', 'hourly')
    when = inst.get('time', 'now')
    t = pd.Timestamp.now('UTC').floor('h') if when == 'now' else _utc(when).floor('h')
    if model == 'fire_check' and inst.get('lat') is None:
        fires = find_active_fires(goes_fire_points(t, bbox=CA_BBOX))
        return {'status': 'ok', 'time': t.strftime(fmt), 'fires': json.loads(fires.round(4).to_json(orient='records'))}
    lat, lon = float(inst['lat']), float(inst['lon'])
    check = fire_check(lat, lon, t, radius_km=float(inst.get('radius_km', FIRE_CHECK_RADIUS_KM)))
    base = {'time': t.strftime(fmt), 'model': model, 'active_fire': bool(check['active']),
            'nearest_fire_km': check['nearest_km']}
    if model == 'fire_check':
        return {'status': 'ok', **base, 'fires': json.loads(check['fires'].round(4).to_json(orient='records'))}
    if not check['active']:
        return {'status': 'no_active_fire', **base, 'layers': {}}
    if not available_models().get(model):
        return {'status': 'unavailable', **base, 'layers': {}, 'message': f'{model} is not enabled on this server'}
    layers = {}
    if model == 'current_fire':
        layers['current_fire'] = current_fire_geojson(Grid.around(lat, lon), t)
    elif model in ('hourly', 'ensemble'):          # ensemble = hourly U-Net until the PINN runs in the cloud
        for l in run_hourly(Grid.around(lat, lon), t):
            layers[f'h{l.horizon_h}'] = layer_geojson(l)
    elif model == 'daily':
        for l in run_daily(Grid.around(lat, lon, size=DAILY_TILE), t):
            layers['h24'] = layer_geojson(l)
    return {'status': 'ok', **base, 'layers': layers}


class ContractError(ValueError):
    """A request the service cannot answer; serve.py turns it into an HTTP error with a JSON message."""
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def parse_issue_time(date_value, params):
    """'YYYY-MM-DD' -> 21:00 UTC (or additional_params.hour); a full ISO timestamp is used as given.
    Times in the future become the latest full hour. Returns (time, was_clamped)."""
    s = str(date_value or '').strip()
    if not s:
        raise ContractError('date is required, e.g. "2026-10-16" or "2026-10-16T21:00:00Z"')
    try:
        if len(s) <= 10:
            hour = int(params.get('hour', DEFAULT_HOUR_UTC))
            if not 0 <= hour <= 23:
                raise ContractError('additional_params.hour must be between 0 and 23')
            t = pd.Timestamp(s).tz_localize('UTC') + pd.Timedelta(hours=hour)
        else:
            t = _utc(s)
    except ContractError:
        raise
    except Exception:
        raise ContractError(f'could not read date {s!r}; use "YYYY-MM-DD" or an ISO-8601 UTC timestamp')
    t, now = t.floor('h'), pd.Timestamp.now('UTC').floor('h')
    return (now, True) if t > now else (t, False)


def parse_bbox(value):
    try:
        b = [float(v) for v in value]
    except Exception:
        raise ContractError('bbox must be [min_lon, min_lat, max_lon, max_lat] in degrees')
    if len(b) != 4 or not (-180 <= b[0] < b[2] <= 180 and -90 <= b[1] < b[3] <= 90):
        raise ContractError('bbox must be [min_lon, min_lat, max_lon, max_lat] with min < max')
    return tuple(b)


def predict_contract(req):
    """The backend contract: bbox + date + time_horizon -> one GeoJSON FeatureCollection with horizons 0/1/3/6."""
    model_type = str(req.get('model_type', 'unet')).lower()
    if model_type not in ('unet', 'ensemble'):
        raise ContractError(f"model_type '{model_type}' is not served by the U-Net service; "
                            "send it to the PINN service or let the ML adapter combine models")
    bbox = parse_bbox(req.get('bbox'))
    params = req.get('additional_params') or {}
    try:
        limit = int(req.get('time_horizon', 6))
        p_min = max(float(params.get('confidence_threshold', P_EMIT)), MIN_CONFIDENCE)
    except (TypeError, ValueError):
        raise ContractError('time_horizon must be a whole number of hours and confidence_threshold a number')
    horizons = [h for h in CONTRACT_HORIZONS if h <= limit]
    t, clamped = parse_issue_time(req.get('date'), params)
    try:
        grid = model_grid_for_bbox(bbox)
    except ValueError as ex:
        raise ContractError(str(ex))
    w, s, e, n = bbox
    radius = float(haversine_km(s, w, n, e)) / 2 + FIRE_SEARCH_PAD_KM
    check = fire_check((s + n) / 2, (w + e) / 2, t, radius_km=radius)
    meta = {'requested_model_type': model_type, 'time_clamped_to_latest_hour': clamped,
            'active_fires_nearby': int(len(check['fires'])), 'nearest_fire_km': check['nearest_km']}
    if not check['active'] or not horizons:
        return unified_feature_collection([], bbox, t, p_min, status='no_active_fire' if not check['active'] else 'ok',
                                          extra_metadata=meta)
    bundles = get_hourly_bundles()
    if not bundles:
        raise ContractError('the hourly models are not loaded on this server', status=503)
    x, burned, out = goes_forecast(grid, t, bundles)
    layers = []
    if 0 in horizons:      # current state: cells GOES-18 saw burning in the last hour
        layers.append({'h': 0, 'p': np.full(burned.shape, np.nan), 'grid': grid,
                       'thresholds': {'MODERATE_RISK': 1.0, 'HIGH_RISK': 1.0}, 'burned': x[..., 0] > 0})
    for h in horizons:
        if h in out:
            layers.append({'h': h, 'p': out[h][0], 'grid': grid, 'thresholds': bundles[h]['thresholds'], 'burned': burned})
    return unified_feature_collection(layers, bbox, t, p_min, extra_metadata=meta)

__all__ = [n for n in list(globals()) if not n.startswith('__')]   # lets the other modules import every name