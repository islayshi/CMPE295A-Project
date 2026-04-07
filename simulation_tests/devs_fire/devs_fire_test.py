"""
devs_fire_test.py
-----------------
Quick test of the DEVS-FIRE wildfire spread simulation API
from Georgia State University's SIMS Lab.

API base: http://firesim.cs.gsu.edu:8084/api/
Docs:     https://sims.cs.gsu.edu/sims/research/DEVSFIRE_API.html

No registration or API key needed — just call /connectToServer to get
a session token, then use it for all subsequent calls.

Usage:
    python devs_fire_test.py

Output:
    - Prints simulation summary to console
    - Saves full results to devs_fire_results.json
    - Saves a simple ASCII grid visualization to devs_fire_grid.txt
"""

import requests
import json
import sys
import math
from datetime import datetime

# ── CONFIGURATION ──────────────────────────────────────────────────────────────
# Edit these to change what the simulation models.

# Ignition point — center of the 200x200 cell grid (grid units, not lat/lon)
# The default grid is 200x200 cells, so center is (100, 100).
IGNITION_X = 100
IGNITION_Y = 100

# Real-world location for the simulation area (used to pull LANDFIRE fuel data)
# These coords place the simulation in the Sierra Nevada foothills near Paradise, CA
# — an area with well-documented wildfire history (Camp Fire 2018).
# You can change these to any California location.
LOCATION_LAT = 39.7596   # Paradise, CA approximate
LOCATION_LNG = -121.6219

# Wind direction in degrees (0 = south, 90 = west, 180 = north, 270 = east)
# 45 degrees = southwest wind (blowing northeast) — typical during CA fire events
WIND_DIRECTION = 45.0

# Cell resolution in meters (each cell = this many meters on a side)
CELL_RESOLUTION = 30  # 30m matches LANDFIRE data resolution

# Grid dimensions (cells per row/column) — keep at 200 unless you have a reason
CELL_DIMENSION = 200

# Simulation time in minutes
SIM_TIME_MINUTES = 60  # Run 1 hour of simulated fire spread

# How many time steps to run (each step advances SIM_TIME_MINUTES)
# More steps = longer burn, more data
NUM_STEPS = 3  # Will simulate 3 hours total (3 x 60 min)

# ── API BASE URL ───────────────────────────────────────────────────────────────
#BASE_URL = "http://firesim.cs.gsu.edu:8084/api"
BASE_URL = "http://localhost:8084/api"  # Use this if running the mock server locally
TIMEOUT = 30  # seconds per request


# ── HELPERS ────────────────────────────────────────────────────────────────────

def post(endpoint, params=None, label=""):
    """POST to an API endpoint with query params. Returns parsed JSON or raises."""
    url = f"{BASE_URL}/{endpoint}"
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    try:
        resp = requests.post(url, timeout=TIMEOUT)
        resp.raise_for_status()
        # Some endpoints return plain strings, some return JSON
        try:
            return resp.json()
        except ValueError:
            return resp.text.strip()
    except requests.exceptions.ConnectionError:
        print(f"\n[ERROR] Could not connect to {BASE_URL}")
        print("The DEVS-FIRE server may be temporarily down.")
        print("Check http://firesim.cs.gsu.edu:8084/api/connectToServer in your browser.")
        sys.exit(1)
    except requests.exceptions.Timeout:
        print(f"\n[ERROR] Request timed out after {TIMEOUT}s for /{endpoint}")
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        print(f"\n[ERROR] HTTP {resp.status_code} on /{endpoint}: {e}")
        sys.exit(1)


def progress(msg):
    """Print a timestamped progress message."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


# ── GRID VISUALIZATION ─────────────────────────────────────────────────────────

def build_ascii_grid(operations, perimeter, grid_size, cell_dim):
    """
    Build a downsampled ASCII art grid showing:
      '#' = burned cell
      'P' = perimeter cell
      'I' = ignition point
      '.' = unburned

    We downsample to ~60 columns wide to fit in a terminal.
    """
    scale = max(1, cell_dim // 60)
    display_size = cell_dim // scale

    grid = [['.' for _ in range(display_size)] for _ in range(display_size)]

    # Mark burned cells
    for op in operations:
        try:
            x = int(op.get("x", -1)) // scale
            y = int(op.get("y", -1)) // scale
            if 0 <= x < display_size and 0 <= y < display_size:
                grid[y][x] = '#'
        except (ValueError, TypeError):
            pass

    # Mark perimeter cells (overwrite burned)
    if isinstance(perimeter, list):
        for i in range(0, len(perimeter) - 1, 2):
            try:
                x = int(perimeter[i]) // scale
                y = int(perimeter[i + 1]) // scale
                if 0 <= x < display_size and 0 <= y < display_size:
                    grid[y][x] = 'P'
            except (ValueError, TypeError, IndexError):
                pass

    # Mark ignition point
    ix = IGNITION_X // scale
    iy = IGNITION_Y // scale
    if 0 <= ix < display_size and 0 <= iy < display_size:
        grid[iy][ix] = 'I'

    return "\n".join("".join(row) for row in grid)


def parse_perimeter(raw):
    """
    getPerimeterCells returns either:
      - A flat list of alternating x,y integers: [84, 77, 83, 77, ...]
      - Or a list of "x,y" strings
    Returns list of (x, y) tuples.
    """
    if not raw:
        return []
    points = []
    if isinstance(raw, list):
        # Try flat int list first
        if all(isinstance(v, (int, float)) for v in raw):
            for i in range(0, len(raw) - 1, 2):
                points.append((int(raw[i]), int(raw[i + 1])))
        else:
            # List of "x,y" strings
            for item in raw:
                try:
                    parts = str(item).split(",")
                    if len(parts) == 2:
                        points.append((int(parts[0]), int(parts[1])))
                except ValueError:
                    pass
    elif isinstance(raw, str):
        # Could be a JSON string or comma-separated
        try:
            parsed = json.loads(raw)
            return parse_perimeter(parsed)
        except json.JSONDecodeError:
            pass
    return points


# ── MAIN ───────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  DEVS-FIRE Wildfire Spread Simulation — API Test")
    print("  Georgia State University SIMS Lab")
    print("=" * 60)
    print()

    results = {
        "config": {
            "ignition_x": IGNITION_X,
            "ignition_y": IGNITION_Y,
            "location_lat": LOCATION_LAT,
            "location_lng": LOCATION_LNG,
            "wind_direction_deg": WIND_DIRECTION,
            "cell_resolution_m": CELL_RESOLUTION,
            "cell_dimension": CELL_DIMENSION,
            "sim_time_per_step_min": SIM_TIME_MINUTES,
            "num_steps": NUM_STEPS,
        },
        "steps": [],
        "final_perimeter": [],
        "summary": {}
    }

    # ── STEP 1: Connect and get session token ───────────────────────────────
    progress("Connecting to DEVS-FIRE server...")
    token = post("connectToServer", label="connectToServer")
    if not token or not isinstance(token, str):
        print(f"[ERROR] Unexpected token response: {token}")
        sys.exit(1)
    progress(f"Session token received: {token[:20]}...")

    # ── STEP 2: Configure simulation parameters ─────────────────────────────
    progress("Setting simulation parameters...")
    post("setMultiParameters", {
        "userToken": token,
        "x": IGNITION_X,
        "y": IGNITION_Y,
        "lat": LOCATION_LAT,
        "lng": LOCATION_LNG,
        "windDirection": WIND_DIRECTION,
        "cellResolution": CELL_RESOLUTION,
        "cellDimension": CELL_DIMENSION,
    }, label="setMultiParameters")
    progress("Parameters set.")

    print()
    print("  Simulation configuration:")
    print(f"    Location    : {LOCATION_LAT}°N, {abs(LOCATION_LNG):.4f}°W (Paradise, CA area)")
    print(f"    Ignition    : grid cell ({IGNITION_X}, {IGNITION_Y})")
    print(f"    Wind        : {WIND_DIRECTION}° (0=south, 90=west, 180=north)")
    print(f"    Cell size   : {CELL_RESOLUTION}m × {CELL_RESOLUTION}m")
    print(f"    Grid size   : {CELL_DIMENSION} × {CELL_DIMENSION} cells")
    print(f"    Area        : {(CELL_DIMENSION * CELL_RESOLUTION / 1000):.1f}km × {(CELL_DIMENSION * CELL_RESOLUTION / 1000):.1f}km")
    print(f"    Steps       : {NUM_STEPS} × {SIM_TIME_MINUTES} min = {NUM_STEPS * SIM_TIME_MINUTES} min total")
    print()

    # ── STEP 3: Run simulation in time steps ────────────────────────────────
    all_operations = []
    total_cells_burned = set()

    for step in range(1, NUM_STEPS + 1):
        elapsed_min = step * SIM_TIME_MINUTES
        progress(f"Running step {step}/{NUM_STEPS} (t={elapsed_min} min simulated)...")

        endpoint = "runSimulation" if step == 1 else "continueSimulation"
        ops = post(endpoint, {
            "userToken": token,
            "time": SIM_TIME_MINUTES,
        }, label=endpoint)

        # Normalize ops to list
        if isinstance(ops, str):
            try:
                ops = json.loads(ops)
            except json.JSONDecodeError:
                ops = []
        if not isinstance(ops, list):
            ops = []

        # Track unique burned cells
        step_new_cells = 0
        for op in ops:
            if isinstance(op, dict):
                try:
                    cell_id = (int(op.get("x", -1)), int(op.get("y", -1)))
                    if cell_id not in total_cells_burned:
                        total_cells_burned.add(cell_id)
                        step_new_cells += 1
                except (ValueError, TypeError):
                    pass

        all_operations.extend(ops if isinstance(ops, list) else [])

        step_info = {
            "step": step,
            "elapsed_minutes": elapsed_min,
            "operations_count": len(ops),
            "new_cells_this_step": step_new_cells,
            "total_cells_burned": len(total_cells_burned),
        }
        results["steps"].append(step_info)

        # Estimate burned area in acres
        cell_area_sqm = CELL_RESOLUTION ** 2
        burned_area_acres = len(total_cells_burned) * cell_area_sqm / 4046.86

        progress(
            f"  Step {step} complete — "
            f"{step_new_cells} new cells, "
            f"{len(total_cells_burned)} total burned "
            f"(~{burned_area_acres:.1f} acres)"
        )

    # ── STEP 4: Get final fire perimeter ────────────────────────────────────
    print()
    progress("Fetching fire perimeter...")
    raw_perimeter = post("getPerimeterCells", {"userToken": token}, label="getPerimeterCells")
    perimeter_points = parse_perimeter(raw_perimeter)
    results["final_perimeter"] = [[p[0], p[1]] for p in perimeter_points]
    progress(f"Perimeter has {len(perimeter_points)} boundary cells.")

    # ── STEP 5: Compute summary statistics ──────────────────────────────────
    total_burned = len(total_cells_burned)
    cell_area_sqm = CELL_RESOLUTION ** 2
    burned_area_acres = total_burned * cell_area_sqm / 4046.86
    burned_area_ha = total_burned * cell_area_sqm / 10000
    burned_area_sqmi = total_burned * cell_area_sqm / 2_589_988

    # Approximate fire radius from center assuming circular spread
    approx_radius_m = math.sqrt(total_burned * cell_area_sqm / math.pi) if total_burned > 0 else 0

    results["summary"] = {
        "total_cells_burned": total_burned,
        "perimeter_cells": len(perimeter_points),
        "burned_area_acres": round(burned_area_acres, 2),
        "burned_area_hectares": round(burned_area_ha, 2),
        "burned_area_sq_miles": round(burned_area_sqmi, 4),
        "approx_fire_radius_m": round(approx_radius_m, 1),
        "total_sim_time_minutes": NUM_STEPS * SIM_TIME_MINUTES,
        "wind_direction_deg": WIND_DIRECTION,
        "location": f"{LOCATION_LAT}°N, {abs(LOCATION_LNG):.4f}°W",
    }

    # ── STEP 6: Print summary ────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("  SIMULATION RESULTS")
    print("=" * 60)
    print(f"  Total cells burned  : {total_burned:,}")
    print(f"  Perimeter cells     : {len(perimeter_points):,}")
    print(f"  Burned area         : {burned_area_acres:,.1f} acres")
    print(f"                      : {burned_area_ha:,.1f} hectares")
    print(f"                      : {burned_area_sqmi:.4f} sq miles")
    print(f"  Approx fire radius  : {approx_radius_m:.0f} m ({approx_radius_m/1000:.2f} km)")
    print(f"  Simulation duration : {NUM_STEPS * SIM_TIME_MINUTES} minutes")
    print()
    print("  Per-step breakdown:")
    for s in results["steps"]:
        ca = s["total_cells_burned"] * cell_area_sqm / 4046.86
        print(f"    t={s['elapsed_minutes']:3d}min — {s['total_cells_burned']:,} cells burned (~{ca:.1f} acres)")

    # ── STEP 7: Save JSON results ────────────────────────────────────────────
    out_json = "devs_fire_results.json"
    with open(out_json, "w") as f:
        json.dump(results, f, indent=2)
    progress(f"Full results saved to {out_json}")

    # ── STEP 8: Save ASCII grid ──────────────────────────────────────────────
    print()
    progress("Generating ASCII fire spread visualization...")
    # Convert total_cells_burned set to list of dicts for the grid builder
    ops_for_grid = [{"x": str(x), "y": str(y)} for x, y in total_cells_burned]
    flat_perimeter = [coord for p in perimeter_points for coord in [p[0], p[1]]]
    ascii_grid = build_ascii_grid(ops_for_grid, flat_perimeter, total_burned, CELL_DIMENSION)

    out_grid = "devs_fire_grid.txt"
    grid_header = (
        f"DEVS-FIRE Simulation — Fire Spread Grid\n"
        f"Location: {LOCATION_LAT}°N, {abs(LOCATION_LNG):.4f}°W (Paradise, CA area)\n"
        f"Wind: {WIND_DIRECTION}° | Duration: {NUM_STEPS * SIM_TIME_MINUTES} min\n"
        f"Legend: I=ignition  #=burned  P=perimeter  .=unburned\n"
        f"Grid: each char = {CELL_RESOLUTION * (CELL_DIMENSION // 60)}m\n"
        f"{'=' * 62}\n"
    )
    with open(out_grid, "w") as f:
        f.write(grid_header)
        f.write(ascii_grid)
    progress(f"ASCII grid saved to {out_grid}")

    # Also print a preview (top 20 lines of grid)
    print()
    print("  Fire spread preview (center section):")
    grid_lines = ascii_grid.split("\n")
    mid = len(grid_lines) // 2
    for line in grid_lines[max(0, mid - 10): mid + 10]:
        print("    " + line)

    print()
    print("=" * 60)
    print("  Done. Output files:")
    print(f"    {out_json}  — full JSON data (feed this to your React app)")
    print(f"    {out_grid} — ASCII visualization of fire spread")
    print("=" * 60)


if __name__ == "__main__":
    main()