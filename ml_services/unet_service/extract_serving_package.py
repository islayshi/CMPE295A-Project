"""Extracts the U-Net inference service package from deploy_unet_wildfirepinn.ipynb.

This script parses the notebook's %%writefile cells and package setup logic
to generate the complete serving directory at ml_services/unet_service/serving.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

NOTEBOOK_PATH = Path(__file__).resolve().parent / "deploy_unet_wildfirepinn.ipynb"
OUTPUT_DIR = Path(__file__).resolve().parent


def extract_package(notebook_path: Path = NOTEBOOK_PATH, output_dir: Path = OUTPUT_DIR) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    with notebook_path.open("r", encoding="utf-8") as f:
        nb = json.load(f)

    extracted_files = []

    # Extract all cells with %%writefile {SERVING_DIR}/<filename>
    pattern = re.compile(r"^%%writefile\s+\{SERVING_DIR\}/([a-zA-Z0-9_\-\.]+)")
    for cell in nb.get("cells", []):
        src = "".join(cell.get("source", []))
        match = pattern.match(src)
        if match:
            filename = match.group(1)
            # Remove the first %%writefile line
            code = src[src.find("\n") + 1 :]
            out_file = output_dir / filename
            out_file.write_text(code, encoding="utf-8")
            extracted_files.append(filename)

    # Extract requirements.txt from Cell 11 specification
    requirements = [
        "tensorflow-cpu>=2.15.0",
        "keras>=3.0.0",
        "scikit-learn>=1.3.0",
        "numpy>=1.26.0",
        "pandas",
        "scipy",
        "xarray",
        "h5netcdf",
        "pyproj",
        "requests",
        "joblib",
        "fastapi",
        "uvicorn",
        "earthengine-api",
        "google-auth",
    ]
    reqs_file = output_dir / "requirements.txt"
    reqs_file.write_text("\n".join(requirements) + "\n", encoding="utf-8")
    extracted_files.append("requirements.txt")

    # Extract Dockerfile from Cell 11 specification
    dockerfile_lines = [
        "FROM python:3.12-slim",
        "WORKDIR /app",
        "COPY requirements.txt .",
        "RUN pip install --no-cache-dir -r requirements.txt",
        "COPY . .",
        "ENV PYTHONUNBUFFERED=1",
        "EXPOSE 8081",
        "CMD exec uvicorn serve:app --host 0.0.0.0 --port ${AIP_HTTP_PORT:-8081}",
    ]
    dockerfile = output_dir / "Dockerfile"
    dockerfile.write_text("\n".join(dockerfile_lines) + "\n", encoding="utf-8")
    extracted_files.append("Dockerfile")

    return extracted_files


if __name__ == "__main__":
    files = extract_package()
    print(f"Extracted {len(files)} files to {OUTPUT_DIR}: {files}")
