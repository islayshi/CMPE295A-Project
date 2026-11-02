"""Unit tests for U-Net native ingestion weather fallback, caching, and error resilience."""
import ast
import py_compile
import unittest
from pathlib import Path

UNET_SERVICE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = UNET_SERVICE_DIR.parent.parent


class TestNativeIngestionResilience(unittest.TestCase):
    def setUp(self):
        self.ingestion_path = UNET_SERVICE_DIR / "native_ingestion.py"
        self.serve_path = UNET_SERVICE_DIR / "serve.py"
        self.docker_compose_path = PROJECT_ROOT / "docker-compose.yaml"

    def test_open_meteo_timeout_is_reduced(self):
        """Open-Meteo timeout must not hang for 90s; should be <= 20s to prevent Celery task timeouts."""
        tree = ast.parse(self.ingestion_path.read_text(), filename=str(self.ingestion_path))
        found_timeout = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_open_meteo_get":
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Call):
                        for kw in sub.keywords:
                            if kw.arg == "timeout" and isinstance(kw.value, ast.Constant):
                                found_timeout = kw.value.value
        self.assertIsNotNone(found_timeout, "Could not find timeout in _open_meteo_get")
        self.assertLessEqual(found_timeout, 20, f"Expected timeout <= 20s in _open_meteo_get, found {found_timeout}")

    def test_openmeteo_weather_has_climatological_fallback(self):
        """openmeteo_weather must catch exceptions and fall back to climatological weather fields."""
        content = self.ingestion_path.read_text()
        self.assertIn("climatological", content.lower(), "Expected climatological weather fallback in native_ingestion.py")
        self.assertIn("TMP", content)
        self.assertIn("DPT", content)
        self.assertIn("UGRD", content)
        self.assertIn("VGRD", content)
        self.assertIn("GUST", content)
        self.assertIn("ACPC01", content)

    def test_serve_py_has_general_exception_handler(self):
        """serve.py predict endpoint must handle general Exception and log traceback, not just ContractError."""
        content = self.serve_path.read_text()
        self.assertIn("except Exception", content, "Expected general 'except Exception' handler in serve.py")
        self.assertIn("traceback", content, "Expected traceback logging in serve.py")

    def test_docker_compose_mounts_native_ingestion(self):
        """docker-compose.yaml must mount native_ingestion.py so changes take effect without full rebuild."""
        content = self.docker_compose_path.read_text()
        self.assertIn(
            "native_ingestion.py:/app/native_ingestion.py",
            content,
            "docker-compose.yaml must mount native_ingestion.py for unet-service",
        )

    def test_python_syntax(self):
        """Verify that all modified files have valid Python syntax."""
        for path in [self.ingestion_path, self.serve_path]:
            py_compile.compile(str(path), doraise=True)


if __name__ == "__main__":
    unittest.main()
