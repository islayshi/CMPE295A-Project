import React from 'react';
import Navbar from '../components/Navbar';
import DataCard from '../components/DataCard';

const DataPage = () => {
  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <main className="max-w-7xl mx-auto px-4 pt-24 pb-8">
        {/* Cards Container */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <DataCard
            name="Google Earth Engine (GEE)"
            description="Provides multi-spectral satellite imagery and surface reflectance for fuel density and vegetation analysis."
            origin="USGS / NASA (Sentinel-2)"
            format="GeoTIFF / Raster Grid"
            resolution="30m x 30m"
            frequency="Every 12 Hours"
            coverage="California / Western US"
          />
        </div>
      </main>
    </div>
  );
};

export default DataPage;