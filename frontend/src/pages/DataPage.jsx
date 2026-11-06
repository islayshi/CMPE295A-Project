// src/pages/DataPage.jsx
import React, { useState } from 'react';
import Navbar from '../components/Navbar';
import DataCard from '../components/DataCard';
import { CATEGORIES, DATASETS } from '../config/datasets';

// Data Panel Components
import GeeNdviPanel from '../components/DataPages/GeeNdviPanel';
import AirQualityPanel from '../components/DataPages/AirQualityPanel';
import FirmsHotspotMap from '../components/DataPages/FirmsHotspotMap';
import WeatherTelemetryPanel from '../components/DataPages/WeatherTelemetryPanel';
import GoesFireTrackingPanel from '../components/DataPages/GoesFireTrackingPanel';
import MtbsHistoricalPanel from '../components/DataPages/MtbsHistoricalPanel';
import GridmetPanel from '../components/DataPages/GridmetPanel';
import NdwsPanel from '../components/DataPages/NDWSPanel';
import GpwPanel from '../components/DataPages/GpwPanel';
import ViirsPanel from '../components/DataPages/ViirsPanel';
import UsgsPanel from '../components/DataPages/UsgsPanel';
import RtmaPanel from '../components/DataPages/RtmaPanel';  
import PalisadesTimelinePanel from '../components/DataPages/PalisadesTimelinePanel';

const DataPage = () => {
  const [selectedCategory, setSelectedCategory] = useState('Remote Sensing/Satellite');
  const [selectedDate, setSelectedDate] = useState(new Date());

  // Helper to format Date objects as YYYY-MM-DD
  const formatDateString = (dateObj) => {
    return dateObj.toISOString().split('T')[0];
  };

  const sharedProps = { selectedDate, setSelectedDate, formatDateString };

  // Dynamic Component Mapping
  const renderPanelContent = () => {
    switch (selectedCategory) {
      case 'Remote Sensing/Satellite':
        return <GeeNdviPanel {...sharedProps} />;
      case 'NASA FIRMS':
        return <FirmsHotspotMap {...sharedProps} />;
      case 'GOES-18 FDCC Fire Telemetry':
        return <GoesFireTrackingPanel selectedDate={selectedDate} formatDateString={formatDateString} />;
      case 'EPA AirNow / Open-Meteo':
        return <AirQualityPanel {...sharedProps} />;
      case 'Weather & Meteorology':
        return <WeatherTelemetryPanel selectedDate={selectedDate} formatDateString={formatDateString} />;
      case 'MTBS Burn Severity':
        return <MtbsHistoricalPanel />;
      case 'GRIDMET Fire Weather Surface Meteorology + GRIDMET DROUGHT':
        return <GridmetPanel selectedDate={selectedDate} formatDateString={formatDateString} />;
      case 'NDWS Benchmark Tensor Layers':
        return <NdwsPanel selectedDate={selectedDate} formatDateString={formatDateString} />;
      case 'GPW Population Density':
        return <GpwPanel selectedDate={selectedDate} formatDateString={formatDateString} />;
      case 'Viirs NDVI (VNP13A1)':
        return (
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden p-6">
            <h2 className="text-xl font-semibold text-gray-800 mb-4">
              NASA VIIRS NDVI (VNP13A1) 16-Day Composite
            </h2>
            <p className="text-sm text-gray-600 mb-6">
              Fetching 500-meter 16-day composite granules directly from NASA LP DAAC.
            </p>
            <ViirsPanel />
          </div>
        );
      case 'USGS 30m Terrain & Topography':
        return <UsgsPanel />;
      case 'RTMA':
        return <RtmaPanel selectedDate={selectedDate} formatDateString={formatDateString} />;
      case 'Palisades Event Data':
        return <PalisadesTimelinePanel selectedDate={selectedDate} formatDateString={formatDateString} />;
      default: {
        const filteredDatasets = DATASETS.filter((item) => item.category === selectedCategory);
        return (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredDatasets.map((data) => (
              <DataCard key={data.id} {...data} />
            ))}
          </div>
        );
      }
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      <main className="max-w-7xl mx-auto px-4 pt-24 pb-8">
        {/* Category Navigation Tabs */}
        <div className="flex flex-wrap gap-2 mb-8 border-b border-gray-200 pb-4">
          {CATEGORIES.map((cat) => (
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

        {/* Selected Category Content */}
        {renderPanelContent()}
      </main>
    </div>
  );
};

export default DataPage;