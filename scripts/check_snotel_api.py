"""
One-off check: Test if USDA SNOTEL API returns data for Gold Basin, Buckboard Flat, Camp Jackson, La Sal.
"""
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import pandas as pd
import requests

from fetch_snotel import (
    REPORT_BASE,
    HEADERS,
    build_report_url,
    fetch_station_csv,
    normalize_columns,
)

# SNOTEL station IDs (from USDA NWCC site info)
STATIONS_TO_TEST = [
    {"id": "572", "state": "UT", "name": "La sal upper"},
    {"id": "1304", "state": "UT", "name": "Gold Basin"},
    {"id": "1153", "state": "UT", "name": "Buckboard Flat"},
    {"id": "383", "state": "UT", "name": "Camp jackson"},
    {"id": "1215", "state": "UT", "name": "Lasal Mtn lower"},
]
# Short date range for quick test
START_DATE = "2025-10-01"
END_DATE = "2026-02-28"


def main():
    print("Testing USDA SNOTEL API for report period", START_DATE, "to", END_DATE)
    print("=" * 60)
    for st in STATIONS_TO_TEST:
        sid, state, name = st["id"], st["state"], st["name"]
        url = build_report_url(sid, state, START_DATE, END_DATE)
        print(f"\n{name} (ID {sid}, {state})")
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            print(f"  HTTP status: {r.status_code}")
            if r.status_code != 200:
                print(f"  Response (first 300 chars): {r.text[:300]!r}")
                continue
            text = r.text
            lines = text.strip().splitlines()
            print(f"  Response lines: {len(lines)}")
            if not lines:
                continue
            # Find data start (skip # comment lines; first non-comment header line)
            start_row = 0
            for i, line in enumerate(lines):
                if line.startswith("#"):
                    continue
                if line.startswith("Date") or "WTEQ" in line or "Snow" in line or "Precipitation" in line or "Snow Water" in line:
                    start_row = i
                    break
            content = "\n".join(lines[start_row:])
            df = pd.read_csv(io.StringIO(content), on_bad_lines="skip", low_memory=False)
            print(f"  Parsed columns: {list(df.columns)[:5]}{'...' if len(df.columns) > 5 else ''}")
            print(f"  Parsed rows (raw): {len(df)}")
            if len(df) > 0:
                df = normalize_columns(df, name, sid)
                print(f"  After normalize: {len(df)} rows, date range: {df['Date'].min()} to {df['Date'].max()}")
                print(f"  -> API data is coming in for {name}")
            else:
                print(f"  -> No data rows (check CSV format). First 2 lines:\n  {repr(lines[:2])}")
        except Exception as e:
            print(f"  Error: {e}")
    print("\n" + "=" * 60)
    print("Done.")


if __name__ == "__main__":
    main()
