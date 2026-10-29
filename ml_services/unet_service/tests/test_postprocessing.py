"""Unit tests for U-Net postprocessing emission thresholds and noise gate configuration."""
import ast
import py_compile
import unittest
from pathlib import Path

UNET_SERVICE_DIR = Path(__file__).resolve().parent.parent


class TestUnetEmissionThresholds(unittest.TestCase):
    def setUp(self):
        self.settings_path = UNET_SERVICE_DIR / "settings.py"
        self.postprocessing_path = UNET_SERVICE_DIR / "postprocessing.py"
        self.inference_path = UNET_SERVICE_DIR / "inference.py"

    def _get_assignment_value(self, file_path, var_name):
        tree = ast.parse(file_path.read_text(), filename=str(file_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == var_name:
                        if isinstance(node.value, ast.Constant):
                            return node.value.value
        return None

    def test_p_emit_threshold_is_0_05_noise_gate(self):
        """P_EMIT must be set to 0.05 to act as a noise gate against background CNN static."""
        val = self._get_assignment_value(self.settings_path, "P_EMIT")
        self.assertEqual(val, 0.05, f"Expected P_EMIT=0.05 in settings.py, got {val}")

    def test_min_confidence_is_0_01(self):
        """MIN_CONFIDENCE must be set to 0.01 (1%) as the lower bound accepted from callers."""
        val = self._get_assignment_value(self.settings_path, "MIN_CONFIDENCE")
        self.assertEqual(val, 0.01, f"Expected MIN_CONFIDENCE=0.01 in settings.py, got {val}")

    def test_postprocessing_fire_probability_rounding_precision(self):
        """to_geojson must round fire_probability to 3 decimal places."""
        content = self.postprocessing_path.read_text()
        self.assertIn(
            "round(float(p[r, c]), 3)",
            content,
            "Expected 'round(float(p[r, c]), 3)' in to_geojson",
        )

    def test_noise_gate_suppression_simulation(self):
        """Verify that background CNN static and water artifacts (< 0.05) are suppressed by P_EMIT."""
        p_emit = self._get_assignment_value(self.settings_path, "P_EMIT")
        self.assertIsNotNone(p_emit)

        # Background noise and water artifacts observed when P_EMIT was lowered:
        ocean_noise = 0.002
        suisun_bay_water_noise = 0.017
        valley_background_static = 0.0268
        # Actual fire spread signal:
        genuine_fire_spread = 0.065
        high_risk_spread = 0.55

        # Background noise must be strictly rejected
        self.assertFalse(ocean_noise >= p_emit, f"Ocean noise {ocean_noise} must be < {p_emit}")
        self.assertFalse(suisun_bay_water_noise >= p_emit, f"Water noise {suisun_bay_water_noise} must be < {p_emit}")
        self.assertFalse(valley_background_static >= p_emit, f"Static {valley_background_static} must be < {p_emit}")

        # Genuine fire spread must pass
        self.assertTrue(genuine_fire_spread >= p_emit, f"Spread {genuine_fire_spread} must be >= {p_emit}")
        self.assertTrue(high_risk_spread >= p_emit, f"High risk {high_risk_spread} must be >= {p_emit}")

    def test_python_syntax(self):
        """Verify that all modified files have valid Python syntax."""
        for path in [self.settings_path, self.postprocessing_path, self.inference_path]:
            py_compile.compile(str(path), doraise=True)


if __name__ == "__main__":
    unittest.main()
