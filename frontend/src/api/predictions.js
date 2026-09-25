import { apiClient } from './client';

export const fetchCurrentPredictions = () => {
  return apiClient('/predictions/current/');
};
