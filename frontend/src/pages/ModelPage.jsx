import React from 'react';
import Navbar from '../components/Navbar';
import ModelCard from '../components/ModelCard';

const ModelPage = () => {
  const handleToggleModel = (status) => {
    console.log(`U-Net Model active state: ${status}`);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      {/* Added pt-24 (padding-top) to lower the content below the fixed Navbar */}
      <main className="max-w-7xl mx-auto px-4 pt-24 pb-8">
        {/* Cards Container */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <ModelCard
            name="U-Net Spatial Predictor"
            description="Deep vision architecture analyzing multi-spectral imagery to delineate 6-hour fire propagation boundaries."
            metrics={{
              accuracy: 89.2,
              precision: 85.4,
              recall: 87.1,
              f1Score: 86.2,
            }}
            onToggle={handleToggleModel}
          />
        </div>
      </main>
    </div>
  );
};

export default ModelPage;