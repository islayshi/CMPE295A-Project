import React from 'react';

const DataCard = ({
  name = "Google Earth Engine (GEE)",
  description = "Provides multi-spectral satellite imagery and surface reflectance for fuel density and vegetation analysis.",
  origin = "USGS / NASA (Sentinel-2 & Landsat)",
  format = "Raster (GeoTIFF)",
  resolution = "30m x 30m per pixel",
  frequency = "Every 12 Hours",
  coverage = "California / Western US",
}) => {
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm hover:shadow-md transition-shadow max-w-md font-sans">
      {/* Header: Dataset Name */}
      <div className="mb-3">
        <h3 className="text-lg font-bold text-gray-900">{name}</h3>
      </div>

      {/* Description */}
      <p className="text-sm text-gray-500 mb-5 leading-relaxed">
        {description}
      </p>

      <hr className="border-gray-100 mb-4" />

      {/* Metadata Key-Value List */}
      <div className="space-y-3 text-sm">
        <DataRow label="Origin" value={origin} />
        <DataRow label="Data Format" value={format} />
        <DataRow label="Spatial Resolution" value={resolution} />
        <DataRow label="Update Frequency" value={frequency} />
        {coverage && <DataRow label="Coverage Area" value={coverage} />}
      </div>
    </div>
  );
};

// Internal reusable helper row for metadata key-values
const DataRow = ({ label, value }) => (
  <div className="flex justify-between items-center py-1 border-b border-gray-50 last:border-none">
    <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
      {label}
    </span>
    <span className="font-medium text-gray-800 text-right font-mono text-xs">
      {value}
    </span>
  </div>
);

export default DataCard;