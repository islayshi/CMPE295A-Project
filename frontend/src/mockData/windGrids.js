export const createWindGrid = (u, v) => {
  const grid = [];
  // Generating a grid covering the Hayward bounding box
  for (let lon = -122.20; lon <= -121.90; lon += 0.02) {
    for (let lat = 37.55; lat <= 37.80; lat += 0.02) {
      grid.push({ position: [lon, lat], u, v });
    }
  }
  return grid;
};

// Gentle wind moving West (matching "10 mph W")
export const normalWind = createWindGrid(-5, 0);

// Fierce wind moving South-West (matches "45 mph SW")
export const severeWind = createWindGrid(-20, -20);
