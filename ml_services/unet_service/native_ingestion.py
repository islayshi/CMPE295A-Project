"""Native ingestion: everything the models read for a place and time (GOES-18 on AWS, Open-Meteo, terrain file,
and for the daily model Earth Engine + FIRMS). Also the active-fire check."""
import os, re, glob, math, threading, time as _time
import numpy as np, pandas as pd, requests
import xml.etree.ElementTree as ET
import xarray as xr
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pyproj import Transformer, CRS
from sklearn.cluster import DBSCAN
from settings import *
from postprocessing import Grid

_NC_LOCK = threading.Lock()   # the NetCDF/HDF5 readers are not thread-safe


def _utc(t):
    t = pd.Timestamp(t)
    return t.tz_localize('UTC') if t.tzinfo is None else t.tz_convert('UTC')


def mask_to_conf(mask):
    m = np.clip(np.nan_to_num(np.asarray(mask, float), nan=0.0), 0, 255).astype(int)
    return _CONF_LUT[m]


def _s3_list_keys(bucket, prefix):
    keys, token = [], None
    while True:
        params = {'list-type': '2', 'prefix': prefix}
        if token:
            params['continuation-token'] = token
        r = requests.get(f'https://{bucket}.s3.amazonaws.com/', params=params, timeout=60)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        keys += [e.text for e in root.findall('s3:Contents/s3:Key', _S3_NS)]
        if root.findtext('s3:IsTruncated', default='false', namespaces=_S3_NS) != 'true':
            return keys
        token = root.findtext('s3:NextContinuationToken', namespaces=_S3_NS)


def _s3_download(bucket, key):
    dest = os.path.join(GOES_CACHE, os.path.basename(key))
    if not os.path.exists(dest):
        r = requests.get(f'https://{bucket}.s3.amazonaws.com/{key}', timeout=120)
        r.raise_for_status()
        with open(dest + '.part', 'wb') as f:
            f.write(r.content)
        os.replace(dest + '.part', dest)
    return dest


def goes_keys_for_hour(t_hour):
    t = _utc(t_hour)
    prefix = f'{GOES_PRODUCT}/{t:%Y}/{t.dayofyear:03d}/{t:%H}/'
    return sorted(k for k in _s3_list_keys(GOES_BUCKET, prefix) if k.endswith('.nc'))[::GOES_FILE_STRIDE]


def _goes_indices(ds, grid):
    # row/col of the GOES pixel under each grid cell centre, cached per grid and file geometry
    p = ds['goes_imager_projection'].attrs
    h, lon0 = float(p['perspective_point_height']), float(p['longitude_of_projection_origin'])
    x, y = ds['x'].values.astype(float), ds['y'].values.astype(float)    # scan angles in radians
    key = (grid, h, lon0, x[0], x[-1], len(x), y[0], y[-1], len(y))
    if key not in _GOES_INDEX_CACHE:
        geos = CRS.from_proj4(f"+proj=geos +h={h} +lon_0={lon0} +sweep={p.get('sweep_angle_axis', 'x')} "
                              f"+a={float(p['semi_major_axis'])} +b={float(p['semi_minor_axis'])} +units=m +no_defs")
        X, Y = grid.centers()
        gx, gy = Transformer.from_crs(GRID_CRS, geos, always_xy=True).transform(X, Y)
        ix = np.rint((np.asarray(gx) / h - x[0]) / (x[1] - x[0]))
        iy = np.rint((np.asarray(gy) / h - y[0]) / (y[1] - y[0]))
        ok = np.isfinite(ix) & np.isfinite(iy) & (ix >= 0) & (ix < len(x)) & (iy >= 0) & (iy < len(y))
        _GOES_INDEX_CACHE[key] = (np.where(ok, iy, 0).astype(int), np.where(ok, ix, 0).astype(int), ok)
    return _GOES_INDEX_CACHE[key]


def _window(iy, ix, ok):
    """Smallest block of GOES rows/columns that covers the grid, so only that part of each file is read."""
    if not ok.any():
        return 0, 1, 0, 1
    return int(iy[ok].min()), int(iy[ok].max()) + 1, int(ix[ok].min()), int(ix[ok].max()) + 1


@lru_cache(maxsize=4096)
def read_fdc_on_grid(path, grid):
    """One GOES file -> fire confidence, clear-sky look (0/1) and fire power (MW) on the grid (cached per file and grid)."""
    import xarray as xr
    with _NC_LOCK, xr.open_dataset(path) as ds:
        iy, ix, ok = _goes_indices(ds, grid)
        r0, r1, c0, c1 = _window(iy, ix, ok)
        part = {v: ds[v].isel(y=slice(r0, r1), x=slice(c0, c1)).values for v in ('Mask', 'DQF', 'Power')}
    jy, jx = np.clip(iy - r0, 0, r1 - r0 - 1), np.clip(ix - c0, 0, c1 - c0 - 1)
    conf = np.where(ok, mask_to_conf(part['Mask'][jy, jx]), 0.0)
    d = np.asarray(part['DQF'][jy, jx], float)
    clear = ok & np.isfinite(d) & (d <= 1)     # DQF 0 = good fire pixel, 1 = good fire-free land
    frp = np.where(ok, np.nan_to_num(np.asarray(part['Power'][jy, jx], float), nan=0.0), 0.0)
    return conf.astype(np.float32), clear.astype(np.float32), frp.astype(np.float32)


def _download_all(keys, workers=16):
    """Downloads many GOES files at the same time; returns {key: local path}."""
    with ThreadPoolExecutor(workers) as pool:
        return dict(zip(keys, pool.map(lambda k: _s3_download(GOES_BUCKET, k), keys)))


def goes_aws_hourly(grid, t0, n_hours):
    """Hourly max fire confidence, number of clear looks and max fire power, each [h, w, n_hours]."""
    t0 = _utc(t0).floor('h')
    hours = [t0 + pd.Timedelta(hours=k) for k in range(n_hours)]
    with ThreadPoolExecutor(16) as pool:
        keys_per_hour = list(pool.map(goes_keys_for_hour, hours))
    paths = _download_all([k for ks in keys_per_hour for k in ks])
    conf = np.zeros((grid.h, grid.w, n_hours), np.float32)
    nval, frp = np.zeros_like(conf), np.zeros_like(conf)
    for k, keys in enumerate(keys_per_hour):
        if not keys:
            print(f'  no GOES files for {hours[k]:%Y-%m-%d %H}Z')
        for key in keys:
            c, v, f = read_fdc_on_grid(paths[key], grid)
            conf[..., k] = np.maximum(conf[..., k], c)
            nval[..., k] += v
            frp[..., k] = np.maximum(frp[..., k], f)
    return conf, nval, frp


def _geos_crs(p):
    return CRS.from_proj4(f"+proj=geos +h={float(p['perspective_point_height'])} "
                          f"+lon_0={float(p['longitude_of_projection_origin'])} +sweep={p.get('sweep_angle_axis', 'x')} "
                          f"+a={float(p['semi_major_axis'])} +b={float(p['semi_minor_axis'])} +units=m +no_defs")


def goes_fire_points(t_end, hours=1, bbox=CA_BBOX):
    """Every GOES-18 fire pixel (confidence 0.5 or more) inside bbox in the hours before t_end."""
    t_end = _utc(t_end).floor('h')
    w, s, e, n = bbox
    frames = []
    for k in range(hours, 0, -1):
        for key in goes_keys_for_hour(t_end - pd.Timedelta(hours=k)):
            path = _s3_download(GOES_BUCKET, key)
            with _NC_LOCK, xr.open_dataset(path) as ds:
                attrs = dict(ds['goes_imager_projection'].attrs)
                conf = mask_to_conf(ds['Mask'].values)
                iy, ix = np.where(conf >= FIRE_THRESHOLD)
                if len(iy) == 0:
                    continue
                h = float(attrs['perspective_point_height'])
                gx = ds['x'].values[ix].astype(float) * h
                gy = ds['y'].values[iy].astype(float) * h
                frp = np.nan_to_num(np.asarray(ds['Power'].values[iy, ix], float))
                c = conf[iy, ix]
            lon, lat = Transformer.from_crs(_geos_crs(attrs), 'EPSG:4326', always_xy=True).transform(gx, gy)
            keep = (lon >= w) & (lon <= e) & (lat >= s) & (lat <= n)
            frames.append(pd.DataFrame({'lat': lat[keep], 'lon': lon[keep], 'confidence': c[keep],
                                        'frp_mw': frp[keep], 'scan': re.search(r'_s(\d{11})', key).group(1)}))
    if not frames:
        return pd.DataFrame(columns=['lat', 'lon', 'confidence', 'frp_mw', 'scan'])
    return pd.concat(frames, ignore_index=True)


def find_active_fires(points, eps_km=4.0, min_scans=2):
    """Groups fire pixels into fires. A fire has to show up in at least min_scans scans."""
    cols = ['lat', 'lon', 'pixels', 'scans', 'max_frp_mw']
    if len(points) == 0:
        return pd.DataFrame(columns=cols)
    labels = DBSCAN(eps=eps_km / 6371.0, min_samples=1, metric='haversine').fit_predict(
        np.radians(points[['lat', 'lon']].to_numpy(float)))
    fires = (points.assign(fire=labels).groupby('fire')
                   .agg(lat=('lat', 'mean'), lon=('lon', 'mean'), pixels=('lat', 'size'),
                        scans=('scan', 'nunique'), max_frp_mw=('frp_mw', 'max')))
    fires = fires[fires['scans'] >= min_scans].sort_values('max_frp_mw', ascending=False)
    return fires.reset_index(drop=True)[cols]


def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1 = math.radians(lat1), math.radians(lon1)
    lat2, lon2 = np.radians(np.asarray(lat2, float)), np.radians(np.asarray(lon2, float))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * np.arcsin(np.sqrt(a))


def bbox_around(lat, lon, radius_km):
    dlat = radius_km / 111.0
    dlon = radius_km / (111.0 * math.cos(math.radians(lat)))
    return (lon - dlon, lat - dlat, lon + dlon, lat + dlat)


def fire_check(lat, lon, t_end, radius_km=FIRE_CHECK_RADIUS_KM, fires=None):
    """Is there an active fire within radius_km of (lat, lon) in the hour before t_end?"""
    if fires is None:
        fires = find_active_fires(goes_fire_points(t_end, bbox=bbox_around(lat, lon, radius_km)))
    if len(fires) == 0:
        return {'active': False, 'nearest_km': None, 'fires': fires}
    d = haversine_km(lat, lon, fires['lat'], fires['lon'])
    near = fires.assign(distance_km=np.round(d, 1))[d <= radius_km].reset_index(drop=True)
    return {'active': len(near) > 0, 'nearest_km': round(float(np.min(d)), 1), 'fires': near}


def relative_humidity(t_c, td_c):
    return np.clip(100.0 * np.exp(17.625 * td_c / (243.04 + td_c)) / np.exp(17.625 * t_c / (243.04 + t_c)), 0, 100)


def window(conf, nval, a, b):
    return conf[..., a:b].max(-1), nval[..., a:b].sum(-1)


def make_label(conf_w, nval_w):
    return np.where(conf_w >= FIRE_THRESHOLD, 1.0, np.where(nval_w > 0, 0.0, -1.0)).astype(np.float32)


def goes_inputs(conf, nval, k, weather, static):
    # k is the issue hour in the stack; hour k-1 is "the last hour"
    now_c, _ = window(conf, nval, k - 1, k)
    prev_c, _ = window(conf, nval, max(k - 4, 0), k - 1)
    day_c, _ = window(conf, nval, max(k - 24, 0), k)
    w = weather
    x = np.stack([(now_c >= FIRE_THRESHOLD).astype(np.float32), prev_c, day_c,
                  w['TMP'], relative_humidity(w['TMP'], w['DPT']), w['UGRD'], w['VGRD'], w['GUST'], w['ACPC01'],
                  static['elevation'], static['slope'], static['NDVI']], -1)
    return x.astype(np.float32)


def _open_meteo_get(url, params):
    r = requests.get(url, params=params, timeout=90)
    r.raise_for_status()
    return r.json()


def openmeteo_weather(grid, t, n=WEATHER_GRID_N):
    from scipy.interpolate import RegularGridInterpolator
    t = _utc(t).floor('h')
    xmin, xmax, ymin, ymax = grid.bounds
    xs, ys = np.linspace(xmin, xmax, n), np.linspace(ymin, ymax, n)
    lon, lat = _to_wgs.transform(*np.meshgrid(xs, ys))
    recent = pd.Timestamp.now('UTC') - t < pd.Timedelta(days=80)
    url = ('https://api.open-meteo.com/v1/forecast' if recent
           else 'https://historical-forecast-api.open-meteo.com/v1/forecast')
    js = _open_meteo_get(url, {'latitude': ','.join(f'{v:.4f}' for v in np.ravel(lat)),
                               'longitude': ','.join(f'{v:.4f}' for v in np.ravel(lon)),
                               'hourly': ','.join(OPEN_METEO_VARS), 'wind_speed_unit': 'ms', 'timezone': 'UTC',
                               'start_date': f'{t:%Y-%m-%d}', 'end_date': f'{t:%Y-%m-%d}'})
    js = js if isinstance(js, list) else [js]
    key = t.strftime('%Y-%m-%dT%H:00')
    v = {name: np.array([loc['hourly'][name][loc['hourly']['time'].index(key)] for loc in js], float).reshape(n, n)
         for name in OPEN_METEO_VARS}
    wd = np.deg2rad(v['wind_direction_10m'])
    fields = {'TMP': v['temperature_2m'], 'DPT': v['dew_point_2m'],
              'UGRD': -v['wind_speed_10m'] * np.sin(wd), 'VGRD': -v['wind_speed_10m'] * np.cos(wd),
              'GUST': v['wind_gusts_10m'], 'ACPC01': v['precipitation']}
    X, Y = grid.centers()
    pts = np.c_[Y.ravel(), X.ravel()]
    return {k: RegularGridInterpolator((ys, xs), np.nan_to_num(f), bounds_error=False, fill_value=None)(pts)
               .reshape(X.shape).astype(np.float32) for k, f in fields.items()}


def static_layers_from_cache(grid, date=None, path=None):
    """Same output as static_layers(), read from the California file instead of Earth Engine."""
    path = path or STATIC_CACHE
    if path not in _STATIC:
        _STATIC[path] = dict(np.load(path))
    s = _STATIC[path]
    full_h, full_w = s['elevation'].shape
    r0 = int(round((float(s['y0']) - grid.y0) / grid.res))
    c0 = int(round((grid.x0 - float(s['x0'])) / grid.res))
    out = {}
    for k in ('elevation', 'slope', 'NDVI'):
        a = np.full((grid.h, grid.w), np.nan, np.float32)
        rs, cs, re_, ce = max(r0, 0), max(c0, 0), min(r0 + grid.h, full_h), min(c0 + grid.w, full_w)
        if rs < re_ and cs < ce:
            a[rs - r0:re_ - r0, cs - c0:ce - c0] = s[k][rs:re_, cs:ce]
        out[k] = a
    return out


static_layers = static_layers_from_cache


def hourly_inputs(grid, t):
    """Native ingestion for the hourly model at time t: GOES-18 fire (last 24 h, AWS), Open-Meteo weather, terrain/NDVI file."""
    t = _utc(t).floor('h')
    conf, nval, _ = goes_aws_hourly(grid, t - pd.Timedelta(hours=24), 24)
    x = goes_inputs(conf, nval, 24, openmeteo_weather(grid, t), static_layers(grid, t))
    burned = window(conf, nval, 0, 24)[0] >= FIRE_THRESHOLD      # seen burning in the last 24 h
    return x, burned


def _ee_latest(collection_id, date, lookback_days, bands):
    d = ee.Date(date)
    col = ee.ImageCollection(collection_id).filterDate(d.advance(-lookback_days, 'day'), d.advance(1, 'day'))
    return ee.Image(col.sort('system:time_start', False).first()).select(bands)


def gee_features(grid, date_str):
    """Daily model inputs (everything except the fire mask) on the grid, in the units used in training."""
    gm = _ee_latest('IDAHO_EPSCOR/GRIDMET', date_str, 5, ['tmmn', 'tmmx', 'vs', 'th', 'sph', 'pr', 'erc'])
    pdsi = _ee_latest('GRIDMET/DROUGHT', date_str, 15, ['pdsi'])
    ndvi = _ee_latest('NASA/VIIRS/002/VNP13A1', date_str, 40, ['NDVI'])
    elev = ee.Image('USGS/SRTMGL1_003').select(['elevation'])
    pop = (ee.ImageCollection('CIESIN/GPWv411/GPW_Population_Density')
             .sort('system:time_start', False).first().select(['population_density'], ['population']))
    stack = ee.Image.cat([elev, gm, pdsi, ndvi, pop]).toFloat()
    arr = ee.data.computePixels({
        'expression': stack, 'fileFormat': 'NUMPY_NDARRAY',
        'grid': {'dimensions': {'width': grid.w, 'height': grid.h},
                 'affineTransform': {'scaleX': grid.res, 'shearX': 0, 'translateX': grid.x0,
                                     'shearY': 0, 'scaleY': -grid.res, 'translateY': grid.y0},
                 'crsCode': GRID_CRS}})
    out = {name: np.asarray(arr[name], np.float32) for name in arr.dtype.names}
    out['NDVI'] = out['NDVI'] * 10000.0      # Earth Engine's VNP13A1 is 0-1; training data used NDVI x 10,000
    return out


def _with_datetime(df):
    df = df.copy()
    if 'datetime_utc' in df.columns:
        df['datetime_utc'] = pd.to_datetime(df['datetime_utc'], utc=True)
    else:
        t = df['acq_time'].astype(int).astype(str).str.zfill(4)
        df['datetime_utc'] = pd.to_datetime(df['acq_date'].astype(str) + ' ' + t.str[:2] + ':' + t.str[2:], utc=True)
    return df


def drop_non_vegetation(df):
    # FIRMS archive 'type': 0 = vegetation fire, 2 = static land source (refineries, flares), 1/3 = volcano/offshore
    if 'type' in df.columns:
        df = df[pd.to_numeric(df['type'], errors='coerce').fillna(0) == 0]
    return df


def grid_bbox_lonlat(grid, pad_deg=0.05):
    xmin, xmax, ymin, ymax = grid.bounds
    lon, lat = _to_wgs.transform([xmin, xmax, xmax, xmin], [ymin, ymin, ymax, ymax])
    return (min(lon) - pad_deg, min(lat) - pad_deg, max(lon) + pad_deg, max(lat) + pad_deg)


def fetch_firms(start_day, n_days, bbox, sources):
    """VIIRS fire detections from FIRMS in bbox for [start_day, start_day + n_days)."""
    w, s, e, n = bbox
    frames, day = [], pd.Timestamp(start_day)
    end = day + pd.Timedelta(days=n_days)
    while day < end:
        span = min(5, (end - day).days)
        for src in sources:
            url = f'https://firms.modaps.eosdis.nasa.gov/api/area/csv/{FIRMS_MAP_KEY}/{src}/{w},{s},{e},{n}/{span}/{day:%Y-%m-%d}'
            try:
                df = pd.read_csv(url)
                if 'latitude' in df.columns:
                    frames.append(df.assign(source=src))
            except Exception as ex:
                print(f'{src}: {ex}')
        day += pd.Timedelta(days=span)
    if not frames:
        return pd.DataFrame(columns=['latitude', 'longitude', 'datetime_utc'])
    df = _with_datetime(pd.concat(frames, ignore_index=True))
    conf = df['confidence'].astype(str).str.lower().str[0]
    return drop_non_vegetation(df[conf != 'l']).reset_index(drop=True)


def rasterize_points(df, grid):
    mask = np.zeros((grid.h, grid.w), np.float32)
    if df is None or len(df) == 0:
        return mask
    xs, ys = _to_grid.transform(df['longitude'].to_numpy(), df['latitude'].to_numpy())
    col = np.floor((xs - grid.x0) / grid.res).astype(int)
    row = np.floor((grid.y0 - ys) / grid.res).astype(int)
    ok = (row >= 0) & (row < grid.h) & (col >= 0) & (col < grid.w)
    mask[row[ok], col[ok]] = 1.0
    return mask


def utc_day(df, day):
    return df[df['datetime_utc'].dt.strftime('%Y-%m-%d') == day]


def daily_inputs(grid, t):
    """Inputs for a forecast issued at t: fire detections of t's UTC day (up to t) plus Earth Engine layers."""
    t = _utc(t)
    recent = pd.Timestamp.now('UTC') - t < pd.Timedelta(days=60)
    start = (t - pd.Timedelta(days=3)).strftime('%Y-%m-%d')
    dets = fetch_firms(start, 4, grid_bbox_lonlat(grid), FIRMS_NRT_SOURCES if recent else FIRMS_ARCHIVE_SOURCES)
    dets = dets[dets['datetime_utc'] <= t] if len(dets) else dets
    raw = gee_features(grid, t.strftime('%Y-%m-%d'))
    raw['PrevFireMask'] = rasterize_points(utc_day(dets, t.strftime('%Y-%m-%d')) if len(dets) else dets, grid)
    return raw, rasterize_points(dets, grid) > 0


def _keep_goes_cache_warm(every_min=10, hours=25):
    """Keeps the last day of GOES-18 files on the server and deletes files older than two days."""
    while True:
        try:
            now = pd.Timestamp.now('UTC').floor('h')
            hrs = [now - pd.Timedelta(hours=k) for k in range(hours, -1, -1)]
            with ThreadPoolExecutor(16) as pool:
                keys = [k for ks in pool.map(goes_keys_for_hour, hrs) for k in ks]
            _download_all(keys)
            cutoff = _time.time() - 48 * 3600
            for f in glob.glob(os.path.join(GOES_CACHE, '*.nc')):
                if os.path.getmtime(f) < cutoff:
                    os.remove(f)
        except Exception as ex:
            print('GOES warm-up skipped:', str(ex)[:120])
        _time.sleep(every_min * 60)


if os.environ.get('WILDFIRE_WARM_CACHE', '1') == '1':
    threading.Thread(target=_keep_goes_cache_warm, daemon=True).start()


__all__ = [n for n in list(globals()) if not n.startswith('__')]   # lets the other modules import every name