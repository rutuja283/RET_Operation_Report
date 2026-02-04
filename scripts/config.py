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

# Station mappings
TREATMENT_STATIONS = [
    "La Sal Mtn",
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
    "lasal Mtn.pdf": "La Sal Mtn",
    "Lasal Mtn lower.pdf": "Lasal Mtn lower",
    "Gold Basin.pdf": "Gold Basin",
    "Camp jackson.pdf": "Camp jackson",
    "Buckboard Flat.pdf": "Buckboard Flat",
    "Elke Ridge.pdf": "Elke Ridge"
}

# SNOTEL cumulative handling
# Water year starts October 1st
WATER_YEAR_START_MONTH = 10
WATER_YEAR_START_DAY = 1

# Plot settings
PLOT_DPI = 300
PLOT_FORMAT = "png"

# Report settings
REPORT_TITLE_PREFIX = "La Sal Operations Report"
