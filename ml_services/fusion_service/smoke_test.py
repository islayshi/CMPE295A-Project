"""Live end-to-end check of the fusion service without the web server (needs the U-Net requirements, network,
and a FIRMS key in FIRMS_MAP_KEY or firms_key.txt in the current folder).

    python ml_services/fusion_service/smoke_test.py                                   # Bay Area, latest hour
    python ml_services/fusion_service/smoke_test.py --bbox -122.4 37.0 -121.6 37.6 --date 2026-11-12T21:00:00Z
"""
import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "ml_pinn_service"), str(HERE.parent / "unet_service")]
import os  # noqa: E402

os.environ.setdefault("WILDFIRE_MODEL_DIR", str(HERE.parent / "unet_service" / "models"))
os.environ.setdefault("WILDFIRE_STATIC_CACHE", str(HERE.parent / "unet_service" / "static_ca_1km.npz"))

import serve  # noqa: E402,F401  (path setup + GOES time-decoding patch)
from fusion import predict as fp  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--bbox", nargs=4, type=float, default=[-122.9, 36.9, -121.5, 38.3])
ap.add_argument("--date", default=None, help="ISO time (UTC) or YYYY-MM-DD; default = latest hour")
ap.add_argument("--out", default="fusion_smoke.geojson")
args = ap.parse_args()

serve._patch_goes_time_decoding()
t0 = time.perf_counter()
status, fc = fp.handle({"bbox": args.bbox, "date": args.date, "time_horizon": 6, "model_type": "fusion"})
print(f"HTTP-equivalent status {status} in {time.perf_counter() - t0:.1f} s")
if status != 200:
    print(fc)
    sys.exit(1)
m = fc["metadata"]
print(json.dumps({k: m.get(k) for k in ("status", "issue_time", "horizons_hours", "total_cells", "fires_forecast",
                                         "has_unet", "inputs", "note", "runtime_s")}, indent=1, default=str))
by = Counter((f["properties"]["horizon_hours"], f["properties"]["risk_label"]) for f in fc["features"])
for k in sorted(by):
    print(f"  +{k[0]} h {k[1]:<14} {by[k]} cells")
Path(args.out).write_text(json.dumps(fc))
print(f"wrote {args.out}")
