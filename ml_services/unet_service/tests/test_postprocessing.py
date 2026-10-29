"""Unit tests for U-Net postprocessing emission thresholds and configuration."""
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

    def test_p_emit_threshold_is_lowered_to_0_001(self):
        """P_EMIT must be set to 0.001 (Option 1) so low-probability spread is emitted."""
        val = self._get_assignment_value(self.settings_path, "P_EMIT")
        self.assertEqual(val, 0.001, f"Expected P_EMIT=0.001 in settings.py, got {val}")

    def test_min_confidence_is_lowered_to_0_001(self):
        """MIN_CONFIDENCE must be set to 0.001 so callers can request low confidence thresholds."""
        val = self._get_assignment_value(self.settings_path, "MIN_CONFIDENCE")
        self.assertEqual(val, 0.001, f"Expected MIN_CONFIDENCE=0.001 in settings.py, got {val}")

    def test_postprocessing_fire_probability_rounding_precision(self):
        """to_geojson must round fire_probability to 4 decimal places to preserve small spread probabilities."""
        content = self.postprocessing_path.read_text()
        self.assertIn(
            "round(float(p[r, c]), 4)",
            content,
            "Expected 'round(float(p[r, c]), 4)' in to_geojson to preserve low-probability spread values",
        )

    def test_threshold_logic_simulation(self):
        """Verify that simulated probabilities from live fires pass the 0.001 threshold."""
        p_emit = self._get_assignment_value(self.settings_path, "P_EMIT")
        self.assertIsNotNone(p_emit)

        # Calibrated probabilities observed in the Los Gatos / Morgan Hill incidents:
        los_gatos_1h = 0.00283
        los_gatos_3h = 0.01717
        los_gatos_6h = 0.00245
        sub_threshold = 0.0005

        self.assertTrue(los_gatos_1h >= p_emit, f"{los_gatos_1h} must be >= {p_emit}")
        self.assertTrue(los_gatos_3h >= p_emit, f"{los_gatos_3h} must be >= {p_emit}")
        self.assertTrue(los_gatos_6h >= p_emit, f"{los_gatos_6h} must be >= {p_emit}")
        self.assertFalse(sub_threshold >= p_emit, f"{sub_threshold} must be < {p_emit}")

    def test_python_syntax(self):
        """Verify that all modified files have valid Python syntax."""
        for path in [self.settings_path, self.postprocessing_path, self.inference_path]:
            py_compile.compile(str(path), doraise=True)


if __name__ == "__main__":
    unittest.main()
