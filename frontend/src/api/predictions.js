import { apiClient } from './client';

export const fetchCurrentPredictions = (params = {}) => {
  const query = new URLSearchParams();
  if (params.model) {
    query.set('model', params.model);
  }
  if (params.horizon !== undefined && params.horizon !== null) {
    query.set('horizon', params.horizon);
  }
  const qs = query.toString();
  return apiClient(`/predictions/current/${qs ? `?${qs}` : ''}`);
};
