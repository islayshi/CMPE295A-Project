import { apiClient } from './client';

export const fetchShelters = () => {
  return apiClient('/telemetry/shelters/');
};

export const fetchWindData = () => {
  return apiClient('/telemetry/wind/');
};

export const fetchAlerts = () => {
  return apiClient('/telemetry/alerts/');
};
