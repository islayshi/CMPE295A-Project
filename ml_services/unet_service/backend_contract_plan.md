# Plan: match the U-Net service to the backend's "black box" contract

Sources: backend messages `message.txt` (v1) and `message_1.txt` (v2, with answers), Oct 2026.
Notebook: `deploy_unet_wildfirepinn.ipynb`. Work in steps; stop after each step for a go-ahead.

## Status
- [x] Step 1 – Gap analysis, plan, questions
- [x] Step 1b – Backend answered all questions (v2); plan updated
- [x] Step 2 – Service code split into the files they asked for + contract logic, tested
      (serve.py, inference.py, native_ingestion.py, postprocessing.py, settings.py; Dockerfile now port 8081 / serve:app;
      NetCDF read lock added; notes for backend in `unet_service_notes_for_backend.txt`)
- [ ] Step 3 – Docker: port 8081, Apple Silicon check, `latest` image tag, hand-off zip + README
- [ ] Step 4 – Hand-off docs: U-Net contract sheet, sample fixture JSON, frontend notes
- [ ] Step 5 – Update notebook, full re-test, redeploy note (same endpoint ID), deliver

## Decisions (from backend answers, v2)
| Topic | Decision |
|---|---|
| grid_id | Keep our California 1 km lattice ids; backend stubs unknown ids using our polygons |
| Time | `date` may be a date or a full ISO timestamp. Date only → 21:00 UTC; `additional_params.hour` overrides. If that time is in the future (today), use the latest full hour |
| members | 1 for every cell we return (standalone model); w_unet = 1.0 |
| Inputs | Native ingestion (we fetch GOES-18, Open-Meteo, terrain ourselves). No `.npz` |
| Extra fields | `risk_label` etc. are fine (stored in `ml_metrics`) |
| Port | U-Net local port **8081** (PINN 8082). Vertex AI still sets `AIP_HTTP_PORT`; container reads it first |
| model_type | Adapter does the ensemble itself. Our service: `unet` (and `ensemble` treated as unet); `pinn`/`rl` → HTTP 400 |
| Files they expect | `serve.py`, `postprocessing.py`, `native_ingestion.py`, `Dockerfile` |

## Contract to implement (Step 2)
- Request: raw JSON or `{"instances": [...]}`; fields `bbox`, `date`, `time_horizon`, `model_type`, `additional_params` (`confidence_threshold`, `hour`). Keep old `lat/lon/time` requests working (current Deploy & test examples).
- Response: one FeatureCollection, horizons 0 (current GOES fire, p = 1.0) and 1/3/6 up to `time_horizon`; `metadata` {timestamp, source_model, model_version, grid_resolution_km, total_cells, status, issue_time, risk_thresholds}; per cell grid_id, fire_probability, horizon_hours, source_model, w_unet, members, risk_label. Polygons clipped to bbox. Raw request → bare FC; `instances` → `{"predictions": [FC]}`.
- Health: `{"status": "ok", "models_loaded": true, ...}`.
- Model area: always at least a 96 km tile around the bbox centre (the model needs context), then clip to the bbox.

## Issues to raise with backend/frontend
1. **Tiny bboxes.** v2 says Celery computes "1 km x 1 km bounding boxes" per fire anomaly. Clipping the forecast to a 1 km box hides the spread. Ask for a bbox padded by at least ~25 km around each fire cluster (or one bbox per region).
2. **FIRMS vs GOES.** Backend scouts with FIRMS (VIIRS, 375 m); our model needs fire seen by GOES-18 (2 km). Small fires may appear in FIRMS but not GOES → our response is empty with `metadata.status = "no_active_fire"`.
3. **Colour scale (frontend).** Forecast probabilities are capped at 0.60; burning cells are 1.0. A 0-1 colour ramp will make every forecast cell look pale. Use `risk_label`, or a ramp topping out near 0.6 with burning cells separate.
4. **gcr.io** in their example is retired; our image lives in Artifact Registry (`us-central1-docker.pkg.dev/wildfirepinn/wildfire/wildfire-unet`). Add a `latest` tag so they can pull it (needs Artifact Registry Reader).

## Hand-off files (Steps 3-4)
- Backend: `unet_service.zip` (code + models + terrain file + Dockerfile + README), U-Net contract sheet (`unet_service_contract.md`), endpoint details (project `wildfirepinn`, region `us-central1`, endpoint `1266228926628233216`), IAM note (Vertex AI User for their Cloud Run service account).
- Frontend: sample fixture `unet_palisades_fixture.json` (real Palisades replay, all horizons) + colour/threshold notes.

## Other checks
- Apple Silicon: does `tensorflow-cpu` have linux arm64 wheels? Else document `--platform linux/amd64`.
- Response size: round coordinates to 5 decimals; warn near 1.5 MB on Vertex AI.
- `WILDFIRE_WARM_CACHE=0` for quick local tests; container needs internet; first past-date call 10-30 s.
- After Step 5 the endpoint must be redeployed (service code changed). Endpoint ID stays the same.

## Step 2 results (tested with real models + stand-in NOAA/Open-Meteo data)
- Palisades bbox, all horizons: 1,737 cells, ~550 KB, 2-3 s (cached files). Bay Area: `no_active_fire`.
- Wrapper, ensemble, threshold, hour override, future date, 400 errors, old lat/lon format: all pass.
- 1 km bbox: only 16 cells -> raised in the notes (3.1).
- Found and fixed: NetCDF reads are not thread-safe -> added a lock (two simultaneous requests could have crashed the server).
- Clipped edge cells keep their grid_id but have a smaller polygon -> raised in the notes (3.5).
- Redeploy needed after this change (same endpoint id).
