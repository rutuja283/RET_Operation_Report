"""
Configuration file for RET Operations Report automation
Last updated: February 2026
"""
import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
CSV_DIR = DATA_DIR / "csv"
RAW_DIR = DATA_DIR / "raw"
PLOTS_DIR = BASE_DIR / "plots"
OUTPUT_DIR = BASE_DIR / "output"

# Station mappings (La sal upper = La Sal Mtn station ID 572)
TREATMENT_STATIONS = [
    "La sal upper",
    "Lasal Mtn lower",
    "Gold Basin"
]

CONTROL_STATIONS = [
    "Camp jackson",
    "Buckboard Flat",
    "Elke Ridge"
]

# Station name mappings (PDF filename -> standardized name)
STATION_NAME_MAP = {
    "lasal Mtn.pdf": "La sal upper",
    "La Sal Mtn.pdf": "La sal upper",
    "Lasal Mtn lower.pdf": "Lasal Mtn lower",
    "Gold Basin.pdf": "Gold Basin",
    "Camp jackson.pdf": "Camp jackson",
    "Buckboard Flat.pdf": "Buckboard Flat",
    "Elke Ridge.pdf": "Elke Ridge"
}

# SNOTEL fetch date range: start 1 Jan this year; end = last day of report month (from pipeline command)
SNOTEL_FETCH_START_YEAR = 2012  # default start; end = last date of month/year passed to pipeline

# SNOTEL stations that can be fetched from USDA (id, state, name must match pipeline station names)
SNOTEL_STATIONS = [
    {"id": "572", "state": "UT", "name": "La sal upper"},
    {"id": "1304", "state": "UT", "name": "Gold Basin"},
    {"id": "1153", "state": "UT", "name": "Buckboard Flat"},
    {"id": "383", "state": "UT", "name": "Camp jackson"},
    {"id": "1215", "state": "UT", "name": "Lasal Mtn lower"},
]

# SNOTEL cumulative handling
# Water year starts October 1st
WATER_YEAR_START_MONTH = 10
WATER_YEAR_START_DAY = 1

# Plot settings
PLOT_DPI = 300
PLOT_FORMAT = "png"

# Report settings
REPORT_TITLE_PREFIX = "La Sal Operations Report"
