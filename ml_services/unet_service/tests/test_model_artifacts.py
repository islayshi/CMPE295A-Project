"""Tests verifying model artifacts and static terrain cache in the U-Net service."""
import os
import unittest
from pathlib import Path

UNET_SERVICE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = UNET_SERVICE_DIR / "models"
STATIC_CACHE_FILE = UNET_SERVICE_DIR / "static_ca_1km.npz"
DOCKERIGNORE_FILE = UNET_SERVICE_DIR / ".dockerignore"


class TestModelArtifacts(unittest.TestCase):
    def test_static_cache_exists_and_valid(self):
        self.assertTrue(STATIC_CACHE_FILE.is_file(), f"Missing {STATIC_CACHE_FILE}")
        self.assertGreater(STATIC_CACHE_FILE.stat().st_size, 1_000_000, "static_ca_1km.npz is suspiciously small")
        expected_keys = {"x0", "y0", "res", "elevation", "slope", "NDVI"}
        try:
            import numpy as np

            data = np.load(STATIC_CACHE_FILE)
            self.assertTrue(expected_keys.issubset(set(data.keys())), f"Missing keys in {STATIC_CACHE_FILE}")
        except ImportError:
            import zipfile

            with zipfile.ZipFile(STATIC_CACHE_FILE, "r") as z:
                keys = {name.replace(".npy", "") for name in z.namelist()}
                self.assertTrue(expected_keys.issubset(keys), f"Missing keys in {STATIC_CACHE_FILE}")

    def test_models_directory_exists(self):
        self.assertTrue(MODELS_DIR.is_dir(), f"Missing {MODELS_DIR}")

    def test_daily_model_artifacts(self):
        required_files = [
            "model.keras",
            "features.json",
            "stats.json",
            "calibrator.joblib",
            "thresholds.json",
            "manifest.json",
        ]
        for fname in required_files:
            fpath = MODELS_DIR / fname
            self.assertTrue(fpath.is_file(), f"Missing {fname} in {MODELS_DIR}")
            self.assertGreater(fpath.stat().st_size, 0)

    def test_hourly_model_bundles(self):
        required_bundle_files = [
            "model.keras",
            "norm.json",
            "calibrator.joblib",
            "thresholds.json",
            "manifest.json",
        ]
        for h in (1, 3, 6):
            hdir = MODELS_DIR / f"goes_h{h}"
            self.assertTrue(hdir.is_dir(), f"Missing hourly bundle {hdir}")
            for fname in required_bundle_files:
                fpath = hdir / fname
                self.assertTrue(fpath.is_file(), f"Missing {fname} in {hdir}")
                self.assertGreater(fpath.stat().st_size, 0)

    def test_dockerignore_configuration(self):
        self.assertTrue(DOCKERIGNORE_FILE.is_file(), f"Missing {DOCKERIGNORE_FILE}")
        content = DOCKERIGNORE_FILE.read_text()
        self.assertIn("u_net_files", content)


if __name__ == "__main__":
    unittest.main()
