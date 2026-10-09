import React, { useState, useEffect } from 'react';
import Navbar from '../components/Navbar';
import DataCard from '../components/DataCard';
import AirQualityTable from '../components/AirQualityTable';
import { MapContainer, TileLayer, LayersControl } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import DatePicker from 'react-datepicker';
import 'react-datepicker/dist/react-datepicker.css';

const categories = [
  'Remote Sensing/Satellite',
  'Weather & Meteorology',
  'Topography & Fuel Beds',
  'EPA AirNow / Open-Meteo',
];

const bayAreaStations = [
  { id: 'SF-01', name: 'San Francisco - Financial Dist', subRegion: 'San Francisco', lat: 37.79, lon: -122.40 },
  { id: 'OAK-02', name: 'Oakland Hills - Redwood Canyon', subRegion: 'East Bay', lat: 37.81, lon: -122.21 },
  { id: 'SJ-03', name: 'San Jose - Foothills / Alum Rock', subRegion: 'South Bay', lat: 37.36, lon: -121.82 },
  { id: 'BERK-04', name: 'UC Berkeley Lab Station', subRegion: 'East Bay', lat: 37.87, lon: -122.25 },
  { id: 'RWC-05', name: 'Redwood City - Port Monitor', subRegion: 'Peninsula', lat: 37.50, lon: -122.21 },
  { id: 'MRN-06', name: 'Marin - Mt. Tamalpais Ridge', subRegion: 'North Bay', lat: 37.92, lon: -122.59 },
];

const datasets = [
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

const DataPage = () => {
  const [selectedCategory, setSelectedCategory] = useState('Remote Sensing/Satellite');
  const [availableDates, setAvailableDates] = useState([]);
  const [selectedDate, setSelectedDate] = useState(new Date());

  // Real API Data States (Open-Meteo)
  const [telemetryData, setTelemetryData] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  // GEE NDVI Tile States
  const [ndviTileUrl, setNdviTileUrl] = useState(null);
  const [isGeeLoading, setIsGeeLoading] = useState(false);
  const [geeError, setGeeError] = useState(null);

  // Helper to format Date objects as YYYY-MM-DD
  const formatDateString = (dateObj) => {
    return dateObj.toISOString().split('T')[0];
  };

  // 1. Fetch available acquisition dates from Django
  useEffect(() => {
    const fetchAvailableDates = async () => {
      try {
        const res = await fetch('http://127.0.0.1:8000/api/telemetry/gee/available-dates/');
        const data = await res.json();
        if (res.ok && data.status === 'success') {
          const dateObjects = data.dates.map(dateStr => new Date(dateStr + 'T00:00:00'));
          setAvailableDates(dateObjects);
          if (dateObjects.length > 0) {
            setSelectedDate(dateObjects[dateObjects.length - 1]);
          }
        }
      } catch (err) {
        console.error('Failed to fetch GEE available dates:', err);
      }
    };

    fetchAvailableDates();
  }, []);

  // 2. Fetch GEE NDVI Tile when category or date changes
  useEffect(() => {
    if (selectedCategory !== 'Remote Sensing/Satellite') return;

    const fetchGeeTile = async () => {
      setIsGeeLoading(true);
      setGeeError(null);

      try {
        const dateStr = formatDateString(selectedDate);
        const startDate = new Date(selectedDate.getTime() - 15 * 24 * 60 * 60 * 1000);
        const startDateStr = formatDateString(startDate);

        const url = `http://127.0.0.1:8000/api/telemetry/gee/ndvi-tile/?start_date=${startDateStr}&end_date=${dateStr}`;
        
        const res = await fetch(url);
        const data = await res.json();
        
        if (res.ok && data.status === 'success') {
          setNdviTileUrl(data.tile_url);
        } else {
          throw new Error(data.message || 'Failed to fetch satellite layer.');
        }
      } catch (err) {
        setGeeError(err.message);
      } finally {
        setIsGeeLoading(false);
      }
    };

    fetchGeeTile();
  }, [selectedCategory, selectedDate]);

  // 3. Fetch Open-Meteo Air Quality Data
  useEffect(() => {
    if (selectedCategory !== 'EPA AirNow / Open-Meteo') return;

    const fetchBayAreaAQI = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const dateStr = formatDateString(selectedDate);
        const requests = bayAreaStations.map(async (station) => {
          const url = `https://air-quality-api.open-meteo.com/v1/air-quality?latitude=${station.lat}&longitude=${station.lon}&hourly=pm10,pm2_5,us_aqi&start_date=${dateStr}&end_date=${dateStr}`;
          
          const res = await fetch(url);
          if (!res.ok) throw new Error(`HTTP ${res.status} on station ${station.id}`);
          const json = await res.json();

          const hourly = json.hourly || {};
          const timestamps = hourly.time || [];
          const pm25List = hourly.pm2_5 || [];
          const pm10List = hourly.pm10 || [];
          const aqiList = hourly.us_aqi || [];

          return timestamps.map((time, idx) => ({
            id: `${station.id}-${idx}`,
            timestamp: time.replace('T', ' '),
            stationId: station.id,
            stationName: station.name,
            subRegion: station.subRegion,
            pm25: pm25List[idx] ?? 0,
            pm10: pm10List[idx] ?? 0,
            aqi: aqiList[idx] ?? 0,
            lat: station.lat,
            lon: station.lon,
          }));
        });

        const results = await Promise.all(requests);
        const allRows = results.flat();

        setTelemetryData(allRows);
      } catch (err) {
        console.error('Failed to fetch Open-Meteo data:', err);
        setError('Failed to fetch live station data. Check your network connection.');
      } finally {
        setIsLoading(false);
      }
    };

    fetchBayAreaAQI();
  }, [selectedCategory, selectedDate]);

  const filteredDatasets = datasets.filter((item) => item.category === selectedCategory);

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      <main className="max-w-7xl mx-auto px-4 pt-24 pb-8">
        
        {/* Category Tabs */}
        <div className="flex flex-wrap gap-2 mb-8 border-b border-gray-200 pb-4">
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                selectedCategory === cat
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'bg-white text-gray-600 hover:bg-gray-100 border border-gray-200'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>

        {/* View Switcher */}
        {selectedCategory === 'Remote Sensing/Satellite' ? (
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden p-6">
            
            {/* Header & DatePicker Control */}
            <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
              <div>
                <h2 className="text-xl font-semibold text-gray-800">
                  Google Earth Engine (GEE) - Sentinel-2 NDVI
                </h2>
                <p className="text-sm text-gray-600">
                  Multi-spectral surface reflectance and vegetation dryness index for fuel assessment.
                </p>
              </div>

              <div className="flex items-center gap-2">
                <label className="text-sm font-medium text-gray-700">Target Date:</label>
                <DatePicker
                  selected={selectedDate}
                  onChange={(date) => setSelectedDate(date)}
                  includeDates={availableDates}
                  dateFormat="yyyy-MM-dd"
                  placeholderText="Select date with data"
                  className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm bg-white shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            {isGeeLoading && (
              <div className="p-8 text-center text-sm font-semibold text-blue-600 bg-blue-50 rounded-xl border border-blue-100 animate-pulse mb-4">
                Fetching live satellite raster composite from Google Earth Engine...
              </div>
            )}

            {geeError && (
              <div className="p-4 text-sm text-red-700 bg-red-50 rounded-xl border border-red-200 mb-4">
                Failed to load satellite tiles: {geeError}
              </div>
            )}

            {/* Map Canvas */}
            <div className="h-[550px] w-full rounded-lg overflow-hidden border border-gray-200 relative">
              <MapContainer
                center={[37.6, -122.1]}
                zoom={9}
                style={{ height: '100%', width: '100%' }}
              >
                <LayersControl position="topright">
                  <LayersControl.BaseLayer checked name="OpenStreetMap Standard">
                    <TileLayer
                      url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                      attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                    />
                  </LayersControl.BaseLayer>

                  <LayersControl.BaseLayer name="Esri World Imagery">
                    <TileLayer
                      url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
                      attribution="Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community"
                    />
                  </LayersControl.BaseLayer>

                  <LayersControl.Overlay checked name="Sentinel-2 Vegetation Dryness (NDVI)">
                    {ndviTileUrl && (
                      <TileLayer
                        url={ndviTileUrl}
                        opacity={0.75}
                        maxZoom={18}
                        attribution="Google Earth Engine | Sentinel-2"
                      />
                    )}
                  </LayersControl.Overlay>
                </LayersControl>
              </MapContainer>
            </div>

          </div>
        ) : selectedCategory === 'EPA AirNow / Open-Meteo' ? (
          <div>
            {isLoading && (
              <div className="p-8 text-center text-sm font-semibold text-blue-600 bg-white rounded-xl border border-gray-200 shadow-sm animate-pulse mb-6">
                Fetching live sensor telemetry from Open-Meteo API...
              </div>
            )}

            {error && (
              <div className="p-4 text-sm text-red-700 bg-red-50 rounded-xl border border-red-200 mb-6">
                {error}
              </div>
            )}

            {!isLoading && (
              <AirQualityTable
                telemetryData={telemetryData}
                bayAreaStations={bayAreaStations}
                selectedDate={formatDateString(selectedDate)}
                onDateChange={(dateStr) => setSelectedDate(new Date(dateStr + 'T00:00:00'))}
              />
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredDatasets.map((data) => (
              <DataCard
                key={data.id}
                name={data.name}
                description={data.description}
                origin={data.origin}
                format={data.format}
                resolution={data.resolution}
                frequency={data.frequency}
                coverage={data.coverage}
              />
            ))}
          </div>
        )}

      </main>
    </div>
  );
};

export default DataPage;