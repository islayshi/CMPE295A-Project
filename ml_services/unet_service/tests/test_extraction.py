"""Tests for notebook cell extraction for the U-Net service."""
import os
import py_compile
import unittest
from pathlib import Path

SERVING_DIR = Path(__file__).resolve().parent.parent
EXPECTED_FILES = [
    "settings.py",
    "postprocessing.py",
    "native_ingestion.py",
    "inference.py",
    "serve.py",
    "requirements.txt",
    "Dockerfile",
]


class TestExtraction(unittest.TestCase):
    def test_serving_directory_and_files_exist(self):
        self.assertTrue(SERVING_DIR.is_dir(), f"Directory {SERVING_DIR} does not exist")
        for filename in EXPECTED_FILES:
            file_path = SERVING_DIR / filename
            self.assertTrue(file_path.is_file(), f"Missing expected file {filename} in {SERVING_DIR}")
            self.assertGreater(file_path.stat().st_size, 0, f"File {filename} is empty")

    def test_python_files_syntax(self):
        py_files = [f for f in EXPECTED_FILES if f.endswith(".py")]
        for filename in py_files:
            file_path = SERVING_DIR / filename
            py_compile.compile(str(file_path), doraise=True)

    def test_serve_py_contract_routes(self):
        serve_file = SERVING_DIR / "serve.py"
        content = serve_file.read_text()
        self.assertIn("app = FastAPI", content)
        self.assertIn("HEALTH_ROUTE", content)
        self.assertIn("PREDICT_ROUTE", content)

    def test_dockerfile_contents(self):
        dockerfile = SERVING_DIR / "Dockerfile"
        content = dockerfile.read_text()
        self.assertIn("EXPOSE 8081", content)
        self.assertIn("uvicorn serve:app", content)
        self.assertIn("${AIP_HTTP_PORT:-8081}", content)

    def test_requirements_contents(self):
        reqs_file = SERVING_DIR / "requirements.txt"
        content = reqs_file.read_text()
        for pkg in ["fastapi", "uvicorn", "tensorflow-cpu", "keras", "xarray", "scikit-learn", "numpy"]:
            self.assertIn(pkg, content)


if __name__ == "__main__":
    unittest.main()
