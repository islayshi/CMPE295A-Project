# Fire Project (Demo Repo)

This folder contains the **minimal, reproducible code** to:

- turn **weather CSVs** + **CA perimeter GeoJSON** into U‑Net training samples
- train a **U‑Net** to predict next‑day fire masks
- evaluate with **slide-ready metrics**
- export a predicted fire mask to **GeoJSON** for simulation software

> Large datasets (`.geojson`, raw weather dumps, generated `.npz`, models) should NOT be committed to GitHub. Keep them local and regenerate using the commands below.

## Setup

Recommended (new venv):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Data inputs (not in GitHub)

You need these locally:

- **Weather CSVs** (Meteostat exports) for many Bay Area cities (2018–2021 recommended)
- **California Historic Fire Perimeters** GeoJSON (large)

## Step 1: Create a deduped weather manifest

If your weather files live in `18_21_Data/`:

```powershell
python make_manifest_from_18_21_data.py --data-dir 18_21_Data --out bay_area_manifest_18_21.csv
```

This removes duplicate city files (identical content) so your interpolation isn’t fake.

## Step 2: Fill lat/lon using Meteostat station metadata

```powershell
python fill_manifest_latlon_meteostat.py --in bay_area_manifest_18_21.csv --out bay_area_manifest_18_21_filled.csv --only-missing
```

## Step 3: Build U‑Net training samples (.npz)

This creates one file per day:

- `X`: `(pixels, pixels, 12)` input channels (normalized)
- `y`: `(pixels, pixels, 1)` next‑day fire mask label

```powershell
python build_unet_dataset_weather_geojson.py `
  --manifest bay_area_manifest_18_21_filled.csv `
  --data-dir . `
  --geojson "California_Historic_Fire_Perimeters_*.geojson" `
  --center-lat 37.55 --center-lon -122.15 --radius-km 120 --pixels 64 `
  --date-start 2018-01-02 --date-end 2021-12-30 `
  --out-dir unet_bay_area_18_21
```

## Step 4: Train the U‑Net

```powershell
python train_unet_on_npz.py `
  --data-dir unet_bay_area_18_21 `
  --pixels 64 --epochs 15 --batch-size 8 `
  --model-out wildfire_unet_bay_18_21.keras `
  --history-csv unet_train_history.csv `
  --plots-out unet_training_curves.png
```

## Step 5: Evaluate metrics + confusion matrix

Evaluate on a fire-season window (recommended):

```powershell
python evaluate_unet_metrics.py `
  --data-dir unet_bay_area_18_21 `
  --model wildfire_unet_bay_18_21.keras `
  --date-start 2020-08-10 --date-end 2020-09-30 --max-samples 200 `
  --threshold 0.5 `
  --cm-out confusion_matrix.png
```

## Step 6: Generate slide-ready metrics report image

```powershell
python make_unet_metrics_report_image.py `
  --data-dir unet_bay_area_18_21 `
  --model wildfire_unet_bay_18_21.keras `
  --date-start 2020-08-10 --date-end 2020-09-30 --max-samples 200 `
  --threshold 0.5 `
  --out unet_metrics_report_2020_fireseason.png
```

## Step 7: Visualize predictions (inputs → pred → truth)

```powershell
python visualize_unet_predictions.py `
  --data-dir unet_bay_area_18_21 `
  --model wildfire_unet_bay_18_21.keras `
  --date-start 2020-08-10 --date-end 2020-09-30 --max 6 `
  --out unet_predictions_panel.png
```

## Step 8: Export predicted mask to GeoJSON (for simulation)

```powershell
python predict_firemask_to_geojson.py `
  --model wildfire_unet_bay_18_21.keras `
  --npz unet_bay_area_18_21/unet_2020-09-10.npz `
  --center-lat 37.55 --center-lon -122.15 --radius-km 120 --pixels 64 `
  --threshold 0.7 `
  --out predicted_firemask_2020-09-11.geojson
```

## Repo hygiene (recommended)

- Don’t commit:
  - raw weather dumps (thousands of rows × many cities)
  - huge GeoJSONs
  - generated `.npz` samples
  - trained `.keras` models

Use `.gitignore` below.

