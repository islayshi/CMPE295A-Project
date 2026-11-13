// Model cards: results from the frozen evaluation (models frozen 9 Nov 2026, 18:36 UTC; nothing refit on the
// validation or test fires). Target: 1 km cells that VIIRS newly detects burning within 6 h of the forecast,
// scored on cells within 10 km of the fire. Test = 11 fires (2022-2026, 351 forecasts), scored once;
// validation = 20 fires. Source: WildfirePINN evaluation hand-off (config.json, evaluate.py).
//
// hitRate = share of newly burned cells the model flagged (recall); precision = share of flagged cells that
// burned; iou = overlap with the real new burn on forecasts where the fire grew; falseAlarmKm2 = km² flagged
// on forecasts where the fire did not grow; ap = average precision (ranking quality, threshold-free).

export const EVALUATION_NOTE =
  'Scored against VIIRS satellite detections of newly burned 1 km cells within 6 h, on 11 held-out test fires ' +
  '(2022–2026) scored once after the models were frozen. Accuracy is not shown: over 97% of cells near a fire ' +
  'do not newly burn, so a model that predicts "no fire" everywhere would look 97% accurate.';

export const MODEL_CARDS = [
  {
    id: 'fusion',
    name: 'Fusion UNet (physics-informed)',
    status: 'live',
    accent: 'amber',
    description:
      'A small UNet that learns from 33 layers: the U-Net and PIML forecasts, physics spread-rate fields, ' +
      'VIIRS and GOES fire, weather, terrain and vegetation. A learned skip keeps it anchored to the two ' +
      'models; a physics loss penalises spread the fire cannot reach in 6 h. Forecasts +3 h and +6 h.',
    test: { hitRate: 0.326, precision: 0.246, f1: 0.28, iou: 0.206, falseAlarmKm2: 2.15, ap: 0.222 },
    validationF1: 0.441,
    best: true,
  },
  {
    id: 'ensemble',
    name: 'Ensemble (U-Net + PIML)',
    status: 'live',
    accent: 'purple',
    description:
      'Weighted union of the two deployed models on the shared 1 km grid: 0.6 × U-Net + 0.4 × PIML per cell, ' +
      'falling back to whichever model answered if one is unavailable.',
    test: { hitRate: 0.486, precision: 0.173, f1: 0.255, iou: 0.202, falseAlarmKm2: 5.85, ap: 0.199 },
    validationF1: 0.384,
  },
  {
    id: 'pinn',
    name: 'PIML (calibrated physics)',
    status: 'live',
    accent: 'teal',
    description:
      'Level-set fire spread with a Rothermel-style rate from LANDFIRE fuel, slope, hourly wind and fuel ' +
      'moisture, calibrated to each fire’s own recent VIIRS growth (learned spread multiplier) and run as a ' +
      '10-member ensemble at 180 m.',
    test: { hitRate: 0.331, precision: 0.182, f1: 0.235, iou: 0.203, falseAlarmKm2: 3.55, ap: 0.121 },
    validationF1: 0.214,
  },
  {
    id: 'unet',
    name: 'U-Net (GOES-18)',
    status: 'live',
    accent: 'indigo',
    description:
      'Hourly convolutional network on GOES-18 fire detections (now, last 3 h, last 24 h), weather, terrain ' +
      'and NDVI at 1 km, forecasting +1, +3 and +6 h. Scored here with recent VIIRS detections added as seed ' +
      'points, as the dashboard calls it.',
    test: { hitRate: 0.533, precision: 0.096, f1: 0.163, iou: 0.137, falseAlarmKm2: 15.73, ap: 0.123 },
    validationF1: 0.276,
  },
  {
    id: 'rl',
    name: 'RL spread policy',
    status: 'research',
    accent: 'slate',
    description:
      'The fire as an agent: burning cells choose which neighbours to ignite each hour, using the physics ' +
      'spread rate plus a learned correction, trained with REINFORCE on rewards from real VIIRS spread. ' +
      'Research result; not deployed on the dashboard.',
    test: { hitRate: 0.434, precision: 0.158, f1: 0.232, iou: 0.18, falseAlarmKm2: 6.33, ap: 0.099 },
    validationF1: 0.333,
  },
];
