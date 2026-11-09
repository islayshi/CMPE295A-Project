import React, { useState, useEffect } from 'react';
import Navbar from '../components/Navbar';
import ModelCard from '../components/ModelCard';

const ModelPage = () => {
  const [unetMetrics, setUnetMetrics] = useState(null);
  const [pinnMetrics, setPinnMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchMetrics = async () => {
      setLoading(true);
      try {
        // Fetch metrics for both models in parallel from Django Gateway
        const [unetRes, pinnRes] = await Promise.all([
          fetch('/api/telemetry/models/metrics/?service=unet'),
          fetch('/api/telemetry/models/metrics/?service=pinn'),
        ]);

        const unetData = await unetRes.json();
        const pinnData = await pinnRes.json();

        if (unetData.status === 'success') setUnetMetrics(unetData.metrics);
        if (pinnData.status === 'success') setPinnMetrics(pinnData.metrics);
      } catch (err) {
        setError('Failed to load real-time metrics from microservices.');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchMetrics();
  }, []);

  const handleToggleModel = (modelName, status) => {
    console.log(`${modelName} active state: ${status}`);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      <main className="max-w-7xl mx-auto px-4 pt-24 pb-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">Model Performance Telemetry</h1>

        {loading ? (
          <div className="text-center py-12 text-gray-500 animate-pulse">
            Connecting to ML inference services...
          </div>
        ) : error ? (
          <div className="p-4 mb-6 text-sm text-red-600 bg-red-50 rounded-lg border border-red-200">
            {error}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {/* U-Net Model Card */}
            <ModelCard
              name="U-Net Spatial Predictor"
              description="Deep vision architecture analyzing multi-spectral imagery to delineate 6-hour fire propagation boundaries."
              metrics={unetMetrics}
              onToggle={(status) => handleToggleModel('U-Net', status)}
            />

            {/* PINN Model Card */}
            <ModelCard
              name="PINN Physics Engine"
              description="Physics-Informed Neural Network modeling thermodynamics and fluid mechanics across Bay Area terrain."
              metrics={pinnMetrics}
              onToggle={(status) => handleToggleModel('PINN', status)}
            />
          </div>
        )}
      </main>
    </div>
  );
};

export default ModelPage;