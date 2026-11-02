"""Tests for the U-Net service root directory structure and syntax."""
import py_compile
import unittest
from pathlib import Path

UNET_SERVICE_DIR = Path(__file__).resolve().parent.parent
EXPECTED_FILES = [
    "serve.py",
    "settings.py",
    "postprocessing.py",
    "native_ingestion.py",
    "inference.py",
    "requirements.txt",
    "Dockerfile",
]


class TestUnetServiceStructure(unittest.TestCase):
    def test_root_files_exist(self):
        for filename in EXPECTED_FILES:
            file_path = UNET_SERVICE_DIR / filename
            self.assertTrue(file_path.is_file(), f"Missing expected file {filename} in {UNET_SERVICE_DIR}")
            self.assertGreater(file_path.stat().st_size, 0, f"File {filename} is empty")

    def test_python_syntax(self):
        py_files = [f for f in EXPECTED_FILES if f.endswith(".py")]
        for filename in py_files:
            file_path = UNET_SERVICE_DIR / filename
            py_compile.compile(str(file_path), doraise=True)

    def test_serve_py_routes_and_app(self):
        serve_file = UNET_SERVICE_DIR / "serve.py"
        content = serve_file.read_text()
        self.assertIn("app = FastAPI", content)
        self.assertIn("HEALTH_ROUTE", content)
        self.assertIn("PREDICT_ROUTE", content)

    def test_dockerfile_configuration(self):
        dockerfile = UNET_SERVICE_DIR / "Dockerfile"
        content = dockerfile.read_text()
        self.assertIn("EXPOSE 8081", content)
        self.assertIn("uvicorn serve:app", content)
        self.assertIn("${AIP_HTTP_PORT:-8081}", content)


if __name__ == "__main__":
    unittest.main()
