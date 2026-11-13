import React from 'react';
import Navbar from '../components/Navbar';
import ModelCard from '../components/ModelCard';
import { EVALUATION_NOTE, MODEL_CARDS } from '../config/modelCards';

const ModelPage = () => (
  <div className="min-h-screen bg-gray-50">
    <Navbar />

    {/* pt-24 keeps the content below the fixed Navbar */}
    <main className="max-w-7xl mx-auto px-4 pt-24 pb-8">
      <div className="mb-6 max-w-3xl">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Models</h1>
        <p className="text-sm text-gray-500 leading-relaxed">{EVALUATION_NOTE}</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {MODEL_CARDS.map((card) => (
          <ModelCard key={card.id} {...card} />
        ))}
      </div>
    </main>
  </div>
);

export default ModelPage;
