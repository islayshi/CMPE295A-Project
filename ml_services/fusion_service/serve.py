"""Physics-informed fusion UNet service (model_type "fusion"), port 8083. Same contract as the U-Net and PIML
services: POST /predict with {bbox, date, time_horizon, model_type: "fusion"} (raw or Vertex AI {"instances": [...]}).

Local (from the repo):  cd ml_services/fusion_service && python serve.py --port 8083
Container:              see Dockerfile (built from ml_services/ by cloudbuild.yaml)
"""
import argparse
import logging
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# U-Net service code (+ weights) and the PIML package: /app/unet and /app/pinn_service in the container,
# the sibling folders in the repo.
UNET_DIR = Path(os.environ.get("UNET_DIR", "/app/unet" if Path("/app/unet").exists() else HERE.parent / "unet_service"))
PINN_ROOT = Path(os.environ.get("PINN_ROOT", "/app" if Path("/app/pinn_service").exists() else HERE.parent / "ml_pinn_service"))
os.environ.setdefault("WILDFIRE_MODEL_DIR", str(UNET_DIR / "models"))
os.environ.setdefault("WILDFIRE_STATIC_CACHE", str(UNET_DIR / "static_ca_1km.npz"))
for p in (HERE, PINN_ROOT, UNET_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from fastapi import Body, FastAPI  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

from fusion import predict as fp  # noqa: E402

log = logging.getLogger("fusion_service")
app = FastAPI(title="Fight Fire With AI - physics-informed fusion UNet", version=fp.CONFIG["model_version"])
HEALTH_ROUTE = os.environ.get("AIP_HEALTH_ROUTE", "/health")
PREDICT_ROUTE = os.environ.get("AIP_PREDICT_ROUTE", "/predict")


def _patch_goes_time_decoding():
    """A few GOES-18 files carry a time attribute xarray cannot decode; the U-Net only needs the fire mask and the
    projection, so retry such a file without decoding times (same patch used when the training data were made)."""
    try:
        import xarray as xr
    except ImportError:
        return
    original = xr.open_dataset

    def safe(*a, **k):
        try:
            return original(*a, **k)
        except ValueError as exc:
            if "decode time" not in str(exc) or "decode_times" in k:
                raise
            return original(*a, decode_times=False, **k)

    xr.open_dataset = safe


@app.on_event("startup")
def _startup():
    _patch_goes_time_decoding()
    fp.nets()
    try:
        import inference
        inference.get_hourly_bundles()
    except Exception as exc:  # health reports it; requests still run PIML-only inputs
        log.warning("U-Net models not loaded: %s", exc)


@app.get(HEALTH_ROUTE)
def health():
    out = {"status": "ok", "model_version": fp.CONFIG["model_version"], "fusion_copies_loaded": len(fp.nets())}
    try:
        import inference
        out["unet_horizons_loaded"] = sorted(inference.get_hourly_bundles())
    except Exception as exc:
        out["unet_error"] = str(exc)
    out["models_loaded"] = out["fusion_copies_loaded"] == 3 and bool(out.get("unet_horizons_loaded"))
    out["firms_key_set"] = bool(os.environ.get("FIRMS_MAP_KEY"))
    return out


def handle(body):
    if isinstance(body.get("instances"), list):              # Vertex AI wrapper in -> wrapper out
        params = body.get("parameters") or {}
        results = []
        for inst in body["instances"]:
            status, res = fp.handle({**params, **inst})
            if status != 200:
                return status, res
            results.append(res)
        return 200, {"predictions": results}
    return fp.handle(body)


@app.post(PREDICT_ROUTE)
def predict(body: dict = Body(...)):
    try:
        status, res = handle(body)
    except Exception as exc:
        log.exception("fusion internal error")
        return JSONResponse(status_code=500, content={"detail": f"fusion internal error: {exc}"})
    if status != 200:
        log.warning("predict -> %s: %s", status, res.get("detail"))
    return JSONResponse(status_code=status, content=res)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the fusion UNet service")
    parser.add_argument("--port", type=int, default=int(os.environ.get("AIP_HTTP_PORT", 8083)))
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port)
