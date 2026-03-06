"""
Merge Lasal SNOTEL (snow depth, SWE) with Lasal Meteoblue (temperature, wind speed, wind direction).
Reports percentage of missing values per feature after merge.
"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Project root
SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR.parent
CSV_DIR = BASE_DIR / "data" / "csv"


def _find_column(df, keywords):
    """Return first column name where any keyword appears (case-insensitive)."""
    for c in df.columns:
        lower = str(c).lower()
        if any(kw.lower() in lower for kw in keywords):
            return c
    return None


def load_snotel(path):
    """Load SNOTEL CSV; keep Date, Snow Depth, SWE. Normalize date to date only."""
    df = pd.read_csv(path)
    df.columns = [str(c).strip() for c in df.columns]
    date_col = _find_column(df, ["date", "datetime", "time"])
    if not date_col:
        date_col = df.columns[0]
    swe_col = _find_column(df, ["snow water equivalent", "swe"])
    sd_col = _find_column(df, ["snow depth"])
    if not swe_col or not sd_col:
        raise ValueError(
            f"SNOTEL file must have Snow Water Equivalent and Snow Depth columns. Found: {list(df.columns)}"
        )
    out = df[[date_col, swe_col, sd_col]].copy()
    out.columns = ["Date", "SWE_in", "Snow_Depth_in"]
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce")
    out = out.dropna(subset=["Date"])
    out["Date"] = out["Date"].dt.normalize()
    return out


def load_meteoblue(path):
    """Load Meteoblue CSV; keep date, temperature, wind speed, wind direction."""
    df = pd.read_csv(path)
    date_col = _find_column(df, ["date", "datetime", "time"])
    if not date_col:
        date_col = df.columns[0]
    temp_col = _find_column(df, ["temperature", "temp", "air temperature", "t_2m"])
    ws_col = _find_column(df, ["wind speed", "wind_speed", "ws", "wind velocity"])
    wd_col = _find_column(df, ["wind direction", "wind_direction", "wd"])
    cols = [date_col]
    renames = ["Date"]
    if temp_col:
        cols.append(temp_col)
        renames.append("Temperature")
    if ws_col:
        cols.append(ws_col)
        renames.append("Wind_Speed")
    if wd_col:
        cols.append(wd_col)
        renames.append("Wind_Direction")
    out = df[cols].copy()
    out.columns = renames
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce")
    out = out.dropna(subset=["Date"])
    out["Date"] = out["Date"].dt.normalize()
    return out


def main():
    snotel_path = CSV_DIR / "La sal upper.csv"
    meteoblue_path = CSV_DIR / "Lasal_meteoblue.csv"
    if len(sys.argv) >= 2:
        meteoblue_path = Path(sys.argv[1])
    if not snotel_path.exists():
        print(f"SNOTEL file not found: {snotel_path}")
        sys.exit(1)
    if not meteoblue_path.exists():
        print(f"Meteoblue file not found: {meteoblue_path}")
        print("  Place your Lasal Meteoblue CSV there or pass path: python merge_lasal_snotel_meteoblue.py <path_to_meteoblue.csv>")
        sys.exit(1)

    snotel = load_snotel(snotel_path)
    meteo = load_meteoblue(meteoblue_path)
    merged = pd.merge(snotel, meteo, on="Date", how="outer")
    merged = merged.sort_values("Date").reset_index(drop=True)

    out_path = BASE_DIR / "Lasal_SNOTEL_Meteoblue_merged.csv"
    merged.to_csv(out_path, index=False)
    print(f"Merged CSV saved: {out_path}")
    print(f"Rows: {len(merged)}")

    n = len(merged)
    print("\n--- Missing value % by feature (after merge) ---")
    for col in merged.columns:
        if col == "Date":
            continue
        missing = merged[col].isna().sum()
        pct = 100.0 * missing / n if n else 0
        print(f"  {col}: {pct:.2f}% missing ({missing} / {n})")
    print("---")


if __name__ == "__main__":
    main()
