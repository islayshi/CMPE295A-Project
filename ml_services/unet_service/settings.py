"""Settings shared by all modules: grid, GOES-18, model files, and the contract defaults."""
import os, json, math, re, glob
import numpy as np, pandas as pd, requests, joblib
import xml.etree.ElementTree as ET
import xarray as xr
import tensorflow as tf
from dataclasses import dataclass, field
from pyproj import Transformer, CRS
from scipy import ndimage
from sklearn.cluster import DBSCAN
import threading, time as _time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache


GRID_CRS = 'EPSG:3310'
RES_M = 1000.0
LATTICE_X0 = -430000.0
LATTICE_Y0 = 480000.0
LATTICE_NCOLS = 1000
CA_BBOX = (-124.5, 32.5, -114.0, 42.1)
GOES_TILE = 96
DAILY_TILE = 64
GOES_BUCKET = 'noaa-goes18'
GOES_PRODUCT = 'ABI-L2-FDCC'
GOES_FILE_STRIDE = 2
GOES_HORIZONS_H = (1, 3, 6)
P_EMIT = 0.001
P_MAX = 0.6
W_UNET = 0.5
WEATHER_GRID_N = 9
FIRE_CODES = [10, 30, 11, 31, 12, 32, 13, 33, 14, 34, 15, 35]
FIRE_CONF = [1.0, 1.0, 0.9, 0.9, 0.8, 0.8, 0.5, 0.5, 0.3, 0.3, 0.1, 0.1]
FIRE_THRESHOLD = 0.5
FIRE_CHECK_RADIUS_KM = 50
GOES_CHANNELS = ['fire_now', 'fire_prev3h', 'fire_24h', 'tmp_c', 'rh', 'wind_u', 'wind_v', 'gust', 'precip', 'elevation', 'slope', 'NDVI']
GOES_FIRE_CHANNELS = 3
OPEN_METEO_VARS = ['temperature_2m', 'dew_point_2m', 'wind_speed_10m', 'wind_direction_10m', 'wind_gusts_10m', 'precipitation']
RAW_INPUTS = ['elevation', 'th', 'vs', 'tmmn', 'tmmx', 'sph', 'pr', 'pdsi', 'NDVI', 'population', 'erc']
FEATURES = ['elevation', 'vs', 'wind_u', 'wind_v', 'tmmn', 'tmmx', 'sph', 'pr', 'pdsi', 'NDVI', 'population', 'erc', 'PrevFireMask']
UNNORMALIZED = {'PrevFireMask'}
VALID_RANGE = {'elevation': (-100.0, 4500.0), 'th': (0.0, 360.0), 'vs': (0.0, 30.0), 'tmmn': (230.0, 330.0), 'tmmx': (230.0, 330.0), 'sph': (0.0, 0.05), 'pr': (0.0, 300.0), 'pdsi': (-15.0, 15.0), 'NDVI': (-10000.0, 10000.0), 'population': (0.0, 100000.0), 'erc': (0.0, 150.0)}
FIRMS_ARCHIVE_SOURCES = ['VIIRS_SNPP_SP', 'VIIRS_NOAA20_SP']
FIRMS_NRT_SOURCES = ['VIIRS_SNPP_NRT', 'VIIRS_NOAA20_NRT', 'VIIRS_NOAA21_NRT']
PINN_CFG = {'s_m': 1000.0, 'inside_negative': True}   # PINN not used in this service


BUNDLE_DIR = os.environ.get('WILDFIRE_MODEL_DIR', '/app/models')
STATIC_CACHE = os.environ.get('WILDFIRE_STATIC_CACHE', '/app/static_ca_1km.npz')
GOES_CACHE = os.environ.get('WILDFIRE_GOES_CACHE', '/tmp/goes_cache')
os.makedirs(GOES_CACHE, exist_ok=True)
FIRMS_MAP_KEY = os.environ.get('FIRMS_MAP_KEY', '')
_to_grid = Transformer.from_crs('EPSG:4326', GRID_CRS, always_xy=True)
_to_wgs = Transformer.from_crs(GRID_CRS, 'EPSG:4326', always_xy=True)
_CONF_LUT = np.zeros(256, np.float32)
for _code, _conf in zip(FIRE_CODES, FIRE_CONF):
    _CONF_LUT[_code] = _conf
_S3_NS = {'s3': 'http://s3.amazonaws.com/doc/2006-03-01/'}
_GOES_INDEX_CACHE, _HOURLY, _DAILY, _STATIC = {}, {}, {}, {}
PHI, PINN_BOUNDS = None, None
EE_READY = False
try:
    import ee, google.auth
    _creds, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/earthengine',
                                           'https://www.googleapis.com/auth/cloud-platform'])
    ee.Initialize(_creds, project=os.environ.get('GCP_PROJECT'))
    EE_READY = True
except Exception as _ex:
    print('Earth Engine not available, daily model is off:', _ex)


# contract with the backend (ML adapter)
MODEL_VERSION = 'unet-goes-hourly-1.0'
CONTRACT_HORIZONS = (0, 1, 3, 6)      # 0 = current fire (GOES-18, last hour)
DEFAULT_HOUR_UTC = 21                 # date-only requests use 21:00 UTC (peak afternoon burn window)
MIN_CONFIDENCE = 0.001                 # lowest confidence_threshold accepted (keeps responses small)
MAX_BBOX_KM = 500                     # largest bbox side the service will run
FIRE_SEARCH_PAD_KM = 25               # fires up to this far outside the bbox still count


__all__ = [n for n in list(globals()) if not n.startswith('__')]   # lets the other modules import every name