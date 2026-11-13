"""Fusion service tests (no TensorFlow or network needed):

    cd ml_services/fusion_service && python -m unittest discover -s tests -v

  * the service's NumPy forward pass reproduces the frozen research model on 3 dev-fire crops
  * contract: request parsing, horizons, polygons on the U-Net lattice, metadata, no-fire answer
"""
import datetime as dt
import sys
import unittest
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent.parent / "ml_pinn_service"))

from fusion import predict as fp  # noqa: E402
from fusion.channels import CH, IDX  # noqa: E402
from fusion.net import predict_raw  # noqa: E402

FIX = np.load(HERE / "fixture_dev_crops.npz")


class Grid:  # the U-Net service's model-grid object (only the fields the fusion code reads)
    def __init__(self, x0=-200000.0, y0=0.0, h=96, w=96):
        self.x0, self.y0, self.h, self.w, self.res = x0, y0, h, w, 1000.0


class FakeUNet:
    def model_grid_for_bbox(self, bbox):
        return Grid()

    def hourly_inputs(self, grid, t):
        raise RuntimeError("no GOES in tests")


def fake_collect(z):
    """Replace inputs.collect with one that returns a ready stack (z) on a 96 x 96 patch."""
    from fusion import inputs

    def collect(bbox, issue, unet, source, cfg):
        patch = inputs.Patch(Grid())
        return patch, {"__stack__": z, "pinn": True, "unet_goes": True}, {"test": True}
    return collect


class NetTests(unittest.TestCase):
    def test_reproduces_frozen_model(self):
        p3, p6, _ = predict_raw(fp.nets(), FIX["X"])
        self.assertLess(np.abs(p3 - FIX["p3"]).max(), 1e-6)
        self.assertLess(np.abs(p6 - FIX["p6"]).max(), 1e-6)
        self.assertLess(np.abs(fp.calibrated(p6, 6) - FIX["p6_cal"]).max(), 1e-6)

    def test_three_copies(self):
        self.assertEqual(len(fp.nets()), 3)
        self.assertEqual(len(CH), 33)


class ContractTests(unittest.TestCase):
    def setUp(self):
        from fusion import inputs
        self._collect, self._stack = inputs.collect, inputs.stack
        z = np.zeros((len(CH), 96, 96), np.float32)
        z[:, 32:64, 40:72] = FIX["X"][0]          # a real dev-fire crop placed inside the patch
        self.z = z
        inputs.collect = fake_collect(z)
        inputs.stack = lambda a: a["__stack__"]
        self.patch = inputs.Patch(Grid())
        lo, la, hi, ha = self.patch.lonlat_bbox()
        self.bbox = [lo + 0.2, la + 0.2, hi - 0.2, ha - 0.2]

    def tearDown(self):
        from fusion import inputs
        inputs.collect, inputs.stack = self._collect, self._stack

    def ask(self, **kw):
        req = {"bbox": self.bbox, "date": "2026-10-16T21:00:00Z", "time_horizon": 6, "model_type": "fusion"}
        req.update(kw)
        return fp.handle(req, unet=FakeUNet(), source=object())

    def test_ok(self):
        status, fc = self.ask()
        self.assertEqual(status, 200, fc)
        self.assertEqual(fc["type"], "FeatureCollection")
        self.assertEqual(fc["metadata"]["source_model"], "fusion")
        self.assertEqual(fc["metadata"]["horizons_hours"], [0, 1, 3, 6])
        self.assertTrue(fc["features"])
        hs = {f["properties"]["horizon_hours"] for f in fc["features"]}
        self.assertEqual(hs, {0, 1, 3, 6})
        for f in fc["features"]:
            p = f["properties"]
            self.assertEqual(p["source_model"], "fusion")
            self.assertEqual(p["members"], 1)
            self.assertTrue(0.0 <= p["fire_probability"] <= 1.0)
            self.assertGreater(p["grid_id"], 0)
            ring = f["geometry"]["coordinates"][0]
            self.assertEqual(ring[0], ring[-1])
            for lon, lat in ring:
                self.assertTrue(self.bbox[0] - 1e-9 <= lon <= self.bbox[2] + 1e-9 and self.bbox[1] - 1e-9 <= lat <= self.bbox[3] + 1e-9)

    def test_grid_ids_are_unet_lattice(self):
        _, fc = self.ask()
        ids = self.patch.grid_ids()
        valid = set(ids.ravel().tolist())
        self.assertTrue(all(f["properties"]["grid_id"] in valid for f in fc["features"]))
        from pinn_service.lattice import LatticeGrid
        g = LatticeGrid()
        for f in fc["features"][:20]:
            ring = np.array(f["geometry"]["coordinates"][0][:-1])
            cell = g.locate(ring[:, 0].mean(), ring[:, 1].mean())
            self.assertEqual(int(cell), f["properties"]["grid_id"])

    def test_burning_cells_and_monotone(self):
        _, fc = self.ask()
        by = {}
        for f in fc["features"]:
            by.setdefault(f["properties"]["horizon_hours"], {})[f["properties"]["grid_id"]] = f["properties"]["fire_probability"]
        self.assertTrue(all(v == 1.0 for v in by[0].values()))
        self.assertEqual(by[1], by[0])                    # no +1 h head: the fire at issue time
        for gid, p in by[3].items():
            self.assertLessEqual(p, by[6].get(gid, 0.0) + 1e-9)

    def test_matches_frozen_probabilities(self):
        """Cells inside the crop get the frozen model's calibrated +6 h probability."""
        P3, P6, SD, burning, n = fp.forecast_patch(self.z, 4)
        self.assertEqual(n, 1)
        crop6 = P6[32:64, 40:72]
        cal = FIX["p6_cal"][0]
        on = crop6 > 0
        self.assertTrue(on.any())
        self.assertLess(np.abs(crop6[on] - cal[on]).max(), 1e-5)

    def test_time_horizon_limits(self):
        _, fc = self.ask(time_horizon=3)
        self.assertEqual(fc["metadata"]["horizons_hours"], [0, 1, 3])
        _, fc = self.ask(time_horizon=0)
        self.assertEqual({f["properties"]["horizon_hours"] for f in fc["features"]}, {0})

    def test_confidence_threshold(self):
        _, fc = self.ask(additional_params={"confidence_threshold": 0.3})
        self.assertTrue(all(f["properties"]["fire_probability"] >= 0.3 for f in fc["features"]))

    def test_rejections(self):
        self.assertEqual(self.ask(model_type="unet")[0], 400)
        self.assertEqual(self.ask(bbox=[1, 2, 3])[0], 400)
        self.assertEqual(self.ask(date="not a date")[0], 400)

    def test_date_only_is_21z_and_future_clamped(self):
        t = fp.parse_issue_time("2026-10-16", {})
        self.assertEqual(t, dt.datetime(2026, 10, 16, 21, tzinfo=dt.timezone.utc))
        future = fp.parse_issue_time("2099-01-01T00:00:00Z", {})
        self.assertLessEqual(future, dt.datetime.now(dt.timezone.utc))

    def test_no_fire(self):
        from fusion import inputs
        inputs.collect = lambda *a: (self.patch, {}, {"viirs_detections": 0})
        status, fc = self.ask()
        self.assertEqual(status, 200)
        self.assertEqual(fc["metadata"]["status"], "no_active_fire")
        self.assertEqual(fc["features"], [])


class LivePipelineTests(unittest.TestCase):
    """inputs.collect end to end on the PIML service's synthetic fire (recorded-format FIRMS / Open-Meteo /
    gridMET responses, no network), with the U-Net unavailable: PIML hooks, physics fields, crops, GeoJSON."""

    def test_synthetic_fire(self):
        import math
        try:
            from pinn_service.tests import test_service as T
        except ImportError as exc:                      # needs fastapi (the PIML service's test module)
            self.skipTest(f"PIML test fixtures unavailable: {exc}")
        from pinn_service import native_ingestion as ni
        from pinn_service.lattice import to_3310

        class UNetDown(FakeUNet):
            def model_grid_for_bbox(self, b):
                x, y = to_3310([b[0], b[2]], [b[1], b[3]])
                n = int(math.ceil((max(x) - min(x) + 2000) / 16000)) * 16
                cx, cy = (min(x) + max(x)) / 2, (min(y) + max(y)) / 2
                return Grid(math.floor((cx - n * 500) / 1000) * 1000, math.ceil((cy + n * 500) / 1000) * 1000, n, n)

        T.setUpModule()
        try:
            status, fc = fp.handle({"bbox": T.BBOX, "date": T.FIRE_DAY, "time_horizon": 6, "model_type": "fusion"},
                                   unet=UNetDown(), source=ni.NativeSource())
        finally:
            T.tearDownModule()
        self.assertEqual(status, 200, fc)
        m = fc["metadata"]
        self.assertEqual(m["status"], "ok")
        self.assertFalse(m["has_unet"])
        self.assertEqual(m["fires_forecast"], 1)            # the refinery hot spot the PIML rejects is not forecast
        risks = {f["properties"]["risk_label"] for f in fc["features"] if f["properties"]["horizon_hours"] == 6}
        self.assertIn("ACTIVE_FIRE", risks)
        self.assertTrue(risks - {"ACTIVE_FIRE"})            # and some forecast spread
        for f in fc["features"]:
            lon, lat = np.mean(f["geometry"]["coordinates"][0][:-1], axis=0)
            self.assertFalse(abs(lon + 122.3) < 0.02 and abs(lat - 37.7) < 0.02)


class StackTests(unittest.TestCase):
    def test_stack_layout(self):
        from fusion.inputs import stack
        H = W = 8
        a = {"viirs_prior": np.zeros((H, W), bool), "viirs_recent": np.zeros((H, W), bool),
             "unet_goes": np.full((3, H, W), 0.2, np.float16), "unet_seed": np.full((3, H, W), 0.3, np.float16),
             "pinn": np.full((3, H, W), 0.4, np.float16), "pinn_goes": np.full((3, H, W), 0.5, np.float16),
             "phys": np.ones((4, H, W), np.float16), "x": np.zeros((H, W, 12), np.float16),
             "goes_burned24": np.zeros((H, W), bool)}
        a["x"][..., 0] = 1.0
        z = stack(a)
        self.assertEqual(z.shape, (33, H, W))
        self.assertAlmostEqual(float(z[IDX["unet_seed6"]].max()), 0.3, places=3)
        self.assertAlmostEqual(float(z[IDX["pinn_goes3"]].max()), 0.5, places=3)
        self.assertAlmostEqual(float(z[IDX["ros_raw"]].max()), float(np.log1p(100)), places=3)
        self.assertEqual(float(z[IDX["has_unet"]].max()), 1.0)
        self.assertEqual(float(z[IDX["has_goes_fire"]].max()), 1.0)
        self.assertEqual(float(z[IDX["goes_fire_now"]].max()), 1.0)


if __name__ == "__main__":
    unittest.main()
