// src/config/datasets.js

export const CATEGORIES = [
  'Remote Sensing/Satellite',
  'NASA FIRMS', 
  'GOES-18 FDCC Fire Telemetry',
  'Weather & Meteorology',
  'EPA AirNow / Open-Meteo',
  'MTBS Burn Severity',
  'GRIDMET Fire Weather Surface Meteorology + GRIDMET DROUGHT',
  'NDWS Benchmark Tensor Layers',
  'GPW Population Density',
  'Viirs NDVI (VNP13A1)',
  'USGS 30m Terrain & Topography',
  'RTMA',
  'Palisades Event Data',
];

export const BAY_AREA_STATIONS = [
  { id: 'SF-01', name: 'San Francisco - Financial Dist', subRegion: 'San Francisco', lat: 37.79, lon: -122.40 },
  { id: 'OAK-02', name: 'Oakland Hills - Redwood Canyon', subRegion: 'East Bay', lat: 37.81, lon: -122.21 },
  { id: 'SJ-03', name: 'San Jose - Foothills / Alum Rock', subRegion: 'South Bay', lat: 37.36, lon: -121.82 },
  { id: 'BERK-04', name: 'UC Berkeley Lab Station', subRegion: 'East Bay', lat: 37.87, lon: -122.25 },
  { id: 'RWC-05', name: 'Redwood City - Port Monitor', subRegion: 'Peninsula', lat: 37.50, lon: -122.21 },
  { id: 'MRN-06', name: 'Marin - Mt. Tamalpais Ridge', subRegion: 'North Bay', lat: 37.92, lon: -122.59 },
];

export const DATASETS = [
  {
    id: 'noaa',
    name: 'NOAA / RAWS Weather Stations',
    category: 'Weather & Meteorology',
    description: 'Real-time surface weather observations including wind speed, direction, relative humidity, and ambient temperature.',
    origin: 'National Weather Service',
    format: 'JSON / Spatial Points',
    resolution: 'Point Locations',
    frequency: 'Every 15 Minutes',
    coverage: 'Western US Grid',
  },
  {
    id: 'landfire',
    name: 'LANDFIRE Fuel & Elevation',
    category: 'Topography & Fuel Beds',
    description: '3D Digital Elevation Models (DEM), slope, aspect, and canopy fuel characterization layers.',
    origin: 'USDA / US Forest Service',
    format: 'Raster / Vector Polygons',
    resolution: '30m Grid',
    frequency: 'Annual / Static',
    coverage: 'Continental US',
  },
];