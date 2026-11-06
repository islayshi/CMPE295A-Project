import React, { useState, useEffect } from 'react';
import { MapContainer, TileLayer, GeoJSON, Popup, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

// Component to dynamically re-center/fit Leaflet map bounds to GeoJSON layer
const MapBoundsFitter = ({ geoJsonData }) => {
  const map = useMap();

  useEffect(() => {
    if (geoJsonData && geoJsonData.features && geoJsonData.features.length > 0) {
      try {
        const L = require('leaflet');
        const geoJsonLayer = L.geoJSON(geoJsonData);
        const bounds = geoJsonLayer.getBounds();
        if (bounds.isValid()) {
          map.fitBounds(bounds, { padding: [20, 20] });
        }
      } catch (err) {
        console.error('Error updating map bounds:', err);
      }
    }
  }, [geoJsonData, map]);

  return null;
};

const MtbsHistoricalPanel = () => {
  const [yearMin, setYearMin] = useState(2015);
  const [yearMax, setYearMax] = useState(2024);
  const [mtbsData, setMtbsData] = useState(null);
  const [selectedIncident, setSelectedIncident] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchMtbsPerimeters = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const res = await fetch(
          `http://127.0.0.1:8000/api/telemetry/mtbs/?year_min=${yearMin}&year_max=${yearMax}`
        );
        const data = await res.json();

        if (res.ok && data.status === 'success') {
          setMtbsData(data);
          setSelectedIncident(null);
        } else {
          throw new Error(data.message || 'Failed to fetch MTBS historical perimeters.');
        }
      } catch (err) {
        console.error('MTBS fetch error:', err);
        setError(err.message);
      } finally {
        setIsLoading(false);
      }
    };

    fetchMtbsPerimeters();
  }, [yearMin, yearMax]);

  // Leaflet polygon style function for MTBS burn perimeters
  const getGeoJsonStyle = (feature) => {
    const isSelected = selectedIncident && feature.id === selectedIncident.id;
    return {
      fillColor: isSelected ? '#ef4444' : '#c2410c',
      weight: isSelected ? 2.5 : 1.5,
      opacity: 0.9,
      color: isSelected ? '#991b1b' : '#ea580c',
      fillOpacity: isSelected ? 0.65 : 0.45,
    };
  };

  // Bind popups and interactivity to GeoJSON perimeters
  const onEachFeature = (feature, layer) => {
    const props = feature.properties || {};
    const name = (props.Incid_Name || 'UNNAMED').toUpperCase();
    const acres = props.BurnBndAc ? Math.round(props.BurnBndAc).toLocaleString() : 'N/A';
    const year = props.FIRE_YEAR || 'N/A';

    layer.bindPopup(`
      <div style="font-family: sans-serif; padding: 4px;">
        <h4 style="margin: 0; font-size: 14px; font-weight: bold; color: #9a3412;">${name} FIRE</h4>
        <p style="margin: 4px 0 0 0; font-size: 12px; color: #4b5563;">Year: <strong>${year}</strong></p>
        <p style="margin: 2px 0 0 0; font-size: 12px; color: #4b5563;">Burned Area: <strong>${acres} acres</strong></p>
      </div>
    `);

    layer.on({
      mouseover: (e) => {
        const l = e.target;
        l.setStyle({ fillOpacity: 0.75, weight: 2.5 });
      },
      mouseout: (e) => {
        const l = e.target;
        l.setStyle({ fillOpacity: 0.45, weight: 1.5 });
      },
    });
  };

  const summary = mtbsData?.summary || {};
  const incidents = mtbsData?.incidents || [];

  return (
    <div className="space-y-6">
      {/* 1. Header & Year Controls */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-gray-800">
              MTBS Historical Burn Severity & Perimeters
            </h2>
            <p className="text-sm text-gray-600">
              USFS & NIFC archived fire perimeters (&gt;1,000 acres) across the SF Bay Area ({yearMin}–{yearMax}).
            </p>
          </div>

          <div className="flex items-center gap-3 bg-gray-50 p-2.5 rounded-lg border border-gray-200">
            <div className="flex items-center gap-1.5">
              <label className="text-xs font-semibold text-gray-600 uppercase">From:</label>
              <select
                value={yearMin}
                onChange={(e) => setYearMin(Number(e.target.value))}
                className="px-2 py-1 border border-gray-300 rounded text-xs bg-white font-medium focus:outline-none focus:ring-2 focus:ring-orange-500"
              >
                {[...Array(30)].map((_, i) => {
                  const y = 2024 - i;
                  return <option key={y} value={y}>{y}</option>;
                })}
              </select>
            </div>

            <span className="text-gray-400 font-bold">-</span>

            <div className="flex items-center gap-1.5">
              <label className="text-xs font-semibold text-gray-600 uppercase">To:</label>
              <select
                value={yearMax}
                onChange={(e) => setYearMax(Number(e.target.value))}
                className="px-2 py-1 border border-gray-300 rounded text-xs bg-white font-medium focus:outline-none focus:ring-2 focus:ring-orange-500"
              >
                {[...Array(30)].map((_, i) => {
                  const y = 2024 - i;
                  return <option key={y} value={y}>{y}</option>;
                })}
              </select>
            </div>
          </div>
        </div>

        {/* Metric Summary Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-6">
          <div className="bg-orange-50/50 rounded-lg p-4 border border-orange-100">
            <p className="text-xs font-semibold text-orange-800 uppercase">Total Major Incidents</p>
            <p className="text-2xl font-bold text-orange-950 mt-1">
              {summary.totalIncidents ?? 0}
            </p>
            <p className="text-[11px] text-orange-700/80 mt-0.5">Large fires (&gt;1k acres)</p>
          </div>

          <div className="bg-red-50/50 rounded-lg p-4 border border-red-100">
            <p className="text-xs font-semibold text-red-800 uppercase">Total Acres Burned</p>
            <p className="text-2xl font-bold text-red-950 mt-1">
              {summary.totalAcresBurned ? summary.totalAcresBurned.toLocaleString() : 0} <span className="text-sm font-normal">acres</span>
            </p>
            <p className="text-[11px] text-red-700/80 mt-0.5">Cumulative scar footprint</p>
          </div>

          <div className="bg-amber-50/50 rounded-lg p-4 border border-amber-100">
            <p className="text-xs font-semibold text-amber-800 uppercase">Largest Complex</p>
            <p className="text-xl font-bold text-amber-950 mt-1 truncate">
              {summary.largestFire ? `${summary.largestFire.fireName} (${summary.largestFire.year})` : 'N/A'}
            </p>
            <p className="text-[11px] text-amber-700/80 mt-0.5">
              {summary.largestFire ? `${Math.round(summary.largestFire.acresBurned).toLocaleString()} acres` : 'No data'}
            </p>
          </div>
        </div>
      </div>

      {/* 2. Interactive Leaflet Map Overlay */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4">
        <h3 className="text-base font-semibold text-gray-800 mb-3 px-2">
          Historical Perimeter Map Overlay
        </h3>
        <div className="h-[420px] w-full rounded-lg overflow-hidden border border-gray-200 relative">
          {isLoading && (
            <div className="absolute inset-0 z-[1000] bg-white/80 backdrop-blur-sm flex items-center justify-center">
              <span className="text-sm font-semibold text-orange-600 animate-pulse">
                Fetching MTBS GeoJSON perimeters from USFS...
              </span>
            </div>
          )}

          {error ? (
            <div className="h-full flex items-center justify-center p-6 bg-red-50 text-red-700 text-sm">
              {error}
            </div>
          ) : (
            <MapContainer
              center={[37.7749, -122.4194]}
              zoom={8}
              style={{ height: '100%', width: '100%' }}
            >
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              {mtbsData?.geoJson && (
                <>
                  <GeoJSON
                    key={JSON.stringify(mtbsData.geoJson.features?.length || 0) + yearMin + yearMax}
                    data={mtbsData.geoJson}
                    style={getGeoJsonStyle}
                    onEachFeature={onEachFeature}
                  />
                  <MapBoundsFitter geoJsonData={mtbsData.geoJson} />
                </>
              )}
            </MapContainer>
          )}
        </div>
      </div>

      {/* 3. Incident History Table */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">
          Recorded Fire Incidents ({incidents.length})
        </h3>

        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50 text-gray-600 uppercase tracking-wider">
                <th className="py-2.5 px-3">Fire Name</th>
                <th className="py-2.5 px-3">Year</th>
                <th className="py-2.5 px-3">Ignition Date</th>
                <th className="py-2.5 px-3">Acres Burned</th>
                <th className="py-2.5 px-3">Incident Type</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 text-gray-700">
              {incidents.length === 0 ? (
                <tr>
                  <td colSpan="5" className="py-6 text-center text-gray-500">
                    No MTBS perimeters recorded in selected year range.
                  </td>
                </tr>
              ) : (
                incidents.map((fire, idx) => (
                  <tr
                    key={fire.id || idx}
                    onClick={() => setSelectedIncident(fire)}
                    className={`hover:bg-orange-50/60 cursor-pointer transition-colors ${
                      selectedIncident?.id === fire.id ? 'bg-orange-100/70 font-semibold' : ''
                    }`}
                  >
                    <td className="py-2.5 px-3 font-medium text-gray-900">{fire.fireName}</td>
                    <td className="py-2.5 px-3">{fire.year}</td>
                    <td className="py-2.5 px-3">{fire.ignitionDate || 'N/A'}</td>
                    <td className="py-2.5 px-3 font-semibold text-orange-700">
                      {Math.round(fire.acresBurned).toLocaleString()}
                    </td>
                    <td className="py-2.5 px-3">{fire.incidentType}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default MtbsHistoricalPanel;