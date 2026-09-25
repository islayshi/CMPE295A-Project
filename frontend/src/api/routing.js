import { apiClient } from './client';

export const requestEvacuationRoute = (lat, lon) => {
  return apiClient('/routing/evacuate/', {
    method: 'POST',
    body: JSON.stringify({ origin: { lat, lon } })
  });
};
