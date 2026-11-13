# Fusion UNet service (`model_type: "fusion"`, port 8083)

The physics-informed fusion UNet from the WildfirePINN study, served with the same contract as the U-Net (8081)
and PIML (8082) services. It is the best model of the final evaluation (frozen 9 Nov 2026, 18:36 UTC):

| 11 test fires, +6 h | Hit rate | Precision | F1 | IoU (growth) | False alarm (no growth) | Avg precision |
|---|---|---|---|---|---|---|
| Fusion UNet | 32.6% | 24.6% | **0.280** | 0.206 | 2.2 km² | **0.222** |
| Team ensemble 0.6/0.4 | 48.6% | 17.3% | 0.255 | 0.202 | 5.9 km² | 0.199 |
| PIML | 33.1% | 18.2% | 0.235 | 0.203 | 3.6 km² | 0.121 |
| U-Net (VIIRS seeds) | 53.3% | 9.6% | 0.163 | 0.137 | 15.7 km² | 0.123 |

Validation (20 fires) F1: fusion 0.441, ensemble 0.384.

## How it works

For each request it builds the model's 33 input layers exactly as the training data were collected, on the
U-Net's 1 km EPSG:3310 grid around the bbox:

* **U-Net**: the U-Net service's own code and weights (copied into the image) run on GOES-18 alone and with the
  last 12 h of VIIRS detections as seed points (+1/+3/+6 h), plus its 12 inputs (GOES fire now/3 h/24 h,
  weather, terrain, NDVI).
* **PIML**: the PIML service's calibrated level-set forecast from the FIRMS VIIRS start, and again with its
  start brought up to the issue time and merged with GOES fire cells, plus its physics fields (burnable share,
  raw and calibrated spread rate, start mask).
* **VIIRS**: cells detected in the last 5 days (FIRMS limit) and in the last 12 h.

Then a 32 x 32 km crop around each fire goes through the 3 frozen copies (NumPy, `fusion/net.py`), averaged and
Platt-calibrated (fitted on the dev fires). Only cells within 10 km of the fire are forecast.

## Output

One FeatureCollection with horizons 0, 1, 3, 6 (`<= time_horizon`):

* `fire_probability`: calibrated chance the cell **newly** burns (as VIIRS would see it) by the horizon.
  Cells burning at issue time come back as 1.0 with `burning_at_issue: true` and `risk_label: ACTIVE_FIRE`.
* The model forecasts +3 h and +6 h. **The +1 h layer shows only the fire at issue time** (the time scrubber
  needs all four horizons; `metadata.horizon_1h_note` says so).
* `risk_label`: `HIGH_RISK` at >= 0.12 (the dev-tuned operating point the test F1 was measured at),
  `MODERATE_RISK` at >= 0.04, else `LOW_RISK`. Cells below 0.02 (or `confidence_threshold`) are left out.
* `grid_id = row * 1000 + col` on the U-Net lattice, so cells line up with the U-Net and PIML services.
* `copy_spread`: standard deviation of the 3 trained copies (a rough uncertainty).

Coverage is the PIML's static layers (Bay Area LANDFIRE fuel), as for the PIML service.

## Run and test

```
cd ml_services/fusion_service
python -m unittest discover -s tests -v          # no TensorFlow or network needed
python serve.py --port 8083                      # needs the U-Net requirements + FIRMS_MAP_KEY in the environment
```

Container (build context is `ml_services/`, because the image bundles the U-Net and PIML code):

```
docker build -f fusion_service/Dockerfile -t fusion-service ml_services
docker run --rm -p 8083:8083 -e FIRMS_MAP_KEY=<your key> fusion-service
gcloud builds submit ml_services --config ml_services/fusion_service/cloudbuild.yaml \
    --substitutions=_IMAGE=us-central1-docker.pkg.dev/ffwai-prod/ffwai-docker-repo/fusion-service:latest
```

`infra/scripts/build_and_push.sh` and `deploy_services.sh` build and deploy it with the other ML services
(`fusion-service` on Cloud Run, FIRMS key from Secret Manager, 4 GiB, 2 CPU, one request at a time, 300 s
timeout), and give the ML adapter `FUSION_SERVICE_URL`. A forecast takes roughly 30-90 s (GOES download, two
PIML runs, two U-Net runs).

## Files

* `fusion/net.py`: forward pass; `fusion/weights/fusion_s{0,1,2}.npz`: the frozen copies (with the SHA-256 of
  the research checkpoint each came from); `fusion/config.json`: calibration, thresholds, test results.
* `fusion/inputs.py`: builds the input layers (mirrors the research collector `rl/ens/fusion_collect.py`).
* `fusion/predict.py`: request parsing, crops, calibration, GeoJSON.
* `tests/fixture_dev_crops.npz`: 3 dev-fire crops with the research code's outputs; the tests check the service
  reproduces them.
