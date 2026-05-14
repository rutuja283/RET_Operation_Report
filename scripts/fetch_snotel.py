"""
Fetch SNOTEL data from USDA/NRCS Report Generator (same source as manual downloads).
Writes daily WTEQ, SNWD, PREC to data/csv in the format expected by the pipeline.
"""
import argparse
import io
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import CSV_DIR, SNOTEL_STATIONS, SNOTEL_FETCH_START_YEAR

try:
    import pandas as pd
    import requests
except ImportError as e:
    print(f"Required package missing: {e}. Install with: pip install pandas requests")
    sys.exit(1)

# Base URL for CSV export (view_csv is faster than view)
REPORT_BASE = "https://wcc.sc.egov.usda.gov/reportGenerator/view_csv/customMultiTimeSeriesGroupByStationReport"
# Avoid 403 from some servers when no User-Agent
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; RET-Report/1.0; +https://github.com)",
    "Accept": "text/csv, text/plain",
}


def build_report_url(station_id, state, start_date, end_date):
    """Build Report Generator CSV URL for one station and date range."""
    # Station filter: 1304:UT:SNTL|id=""|name
    station_filter = f"{station_id}:{state}:SNTL%7Cid=%22%22%7Cname"
    # Date range in path (YYYY-MM-DD,YYYY-MM-DD)
    date_range = f"{start_date},{end_date}"
    # Elements: WTEQ, SNWD, PREC (value = start of period)
    columns = "WTEQ::value,SNWD::value,PREC::value"
    url = f"{REPORT_BASE}/daily/start_of_period/{station_filter}/{date_range}/{columns}?fitToScreen=false"
    return url


def fetch_station_csv(station_id, state, start_date, end_date, station_name=None):
    """
    Fetch CSV for one SNOTEL station from USDA. Returns (raw_text, success).
    """
    url = build_report_url(station_id, state, start_date, end_date)
    try:
        r = requests.get(url, headers=HEADERS, timeout=60)
        r.raise_for_status()
        return r.text, True
    except requests.RequestException as e:
        return str(e), False


def normalize_columns(df, station_name, station_id):
    """
    Ensure output has Date plus columns matching existing pipeline CSVs:
    '{name} ({id}) Snow Water Equivalent (in) Start of Day Values', etc.
    """
    df = df.copy()
    # Normalize date column (USDA may use "Date", "date", or first column as date)
    date_col = None
    for c in df.columns:
        if "date" in str(c).lower() or c == "Date":
            date_col = c
            break
    if date_col is None and len(df.columns) > 0:
        date_col = df.columns[0]  # assume first column is date
    if date_col is not None:
        if date_col != "Date":
            df = df.rename(columns={date_col: "Date"})
        if "Date" not in df.columns:
            df["Date"] = df[date_col].copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"])

    # Map common USDA column patterns to pipeline format
    suffix_swe = " Snow Water Equivalent (in) Start of Day Values"
    suffix_snwd = " Snow Depth (in) Start of Day Values"
    suffix_prec = " Precipitation Accumulation (in) Start of Day Values"
    target_swe = f"{station_name} ({station_id}){suffix_swe}"
    target_snwd = f"{station_name} ({station_id}){suffix_snwd}"
    target_prec = f"{station_name} ({station_id}){suffix_prec}"

    renames = {}
    for c in df.columns:
        if c == "Date":
            continue
        c_lower = str(c).lower()
        if "wteq" in c_lower or "snow water" in c_lower or "swe" in c_lower:
            renames[c] = target_swe
        elif "snwd" in c_lower or "snow depth" in c_lower:
            renames[c] = target_snwd
        elif "prec" in c_lower or "precipitation" in c_lower:
            renames[c] = target_prec
    if renames:
        df = df.rename(columns=renames)

    return df


def fetch_snotel_for_report(month, year):
    """
    Fetch USDA SNOTEL data for all configured SNOTEL_STATIONS from SNOTEL_FETCH_START_YEAR
    through end of report month. Writes to data/csv/<name>.csv.
    For example, month=4 and year=2026 fetches through 2026-04-30, so March and April 2026
    are included in the daily series (along with all prior years from the start date).
    Returns list of (station_name, success, message).
    """
    start_date = f"{SNOTEL_FETCH_START_YEAR}-01-01"
    # End of report month (last day)
    if month == 12:
        end_dt = datetime(year, 12, 31)
    else:
        end_dt = datetime(year, month + 1, 1) - timedelta(days=1)
    end_date = end_dt.strftime("%Y-%m-%d")

    results = []
    for st in SNOTEL_STATIONS:
        station_id = st["id"]
        state = st["state"]
        station_name = st["name"]
        text, ok = fetch_station_csv(station_id, state, start_date, end_date, station_name)
        if not ok:
            results.append((station_name, False, text))
            continue
        lines = text.strip().splitlines()
        if not lines:
            results.append((station_name, False, "Empty response"))
            continue
        # USDA response has # comment lines then "Date,..." header then data. Use first non-comment line that looks like CSV header.
        start_row = 0
        for i, line in enumerate(lines):
            if line.startswith("#"):
                continue
            if line.startswith("Date") or ("WTEQ" in line or "Snow" in line or "Precipitation" in line or "Snow Water" in line):
                start_row = i
                break
        content = "\n".join(lines[start_row:])
        try:
            df = pd.read_csv(io.StringIO(content), on_bad_lines="skip", low_memory=False)
        except Exception as e:
            results.append((station_name, False, str(e)))
            continue
        df = normalize_columns(df, station_name, station_id)
        if len(df) == 0:
            results.append((station_name, False, "no rows after parse (check USDA response format)"))
            continue
        out_path = CSV_DIR / f"{station_name}.csv"
        CSV_DIR.mkdir(parents=True, exist_ok=True)
        df.to_csv(out_path, index=False)
        results.append((station_name, True, f"{len(df)} rows to {out_path}"))
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Fetch SNOTEL data from USDA/NRCS Report Generator and save to data/csv."
    )
    parser.add_argument("station_id", type=str, help="Station ID (e.g. 1304 for Gold Basin UT)")
    parser.add_argument("state", type=str, help="State code (e.g. UT)")
    parser.add_argument(
        "--name",
        "-n",
        default=None,
        help="Station name for output file and column headers (default: Gold Basin for 1304)",
    )
    parser.add_argument(
        "--month",
        "-m",
        type=int,
        default=None,
        help="Report month (1-12); used with --year to set date range to that month",
    )
    parser.add_argument(
        "--year",
        "-y",
        type=int,
        default=None,
        help="Report year; used with --month",
    )
    parser.add_argument(
        "--start",
        default=None,
        help="Start date YYYY-MM-DD (alternative to --month/--year)",
    )
    parser.add_argument(
        "--end",
        default=None,
        help="End date YYYY-MM-DD (alternative to --month/--year)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output CSV path (default: data/csv/<station_name>.csv)",
    )
    args = parser.parse_args()

    station_id = str(args.station_id)
    state = str(args.state).upper()
    station_name = args.name or (station_id == "1304" and "Gold Basin") or f"Station_{station_id}"

    if args.start and args.end:
        start_date = args.start
        end_date = args.end
    elif args.month is not None and args.year is not None:
        start_date = datetime(args.year, args.month, 1).strftime("%Y-%m-%d")
        if args.month == 12:
            end_date = datetime(args.year + 1, 1, 1).strftime("%Y-%m-%d")
        else:
            end_date = datetime(args.year, args.month + 1, 1).strftime("%Y-%m-%d")
    else:
        # Default: current water year to today
        from datetime import date
        today = date.today()
        wy_start = today.month >= 10 and today.year or today.year - 1
        start_date = f"{wy_start}-10-01"
        end_date = today.strftime("%Y-%m-%d")

    text, ok = fetch_station_csv(station_id, state, start_date, end_date, station_name)
    if not ok:
        print(f"Fetch failed: {text}")
        print("You can download the same data from Report Generator and save as CSV.")
        sys.exit(1)

    # Parse CSV (USDA may use comma or tab; first line often has metadata)
    lines = text.strip().splitlines()
    if not lines:
        print("Empty response from server.")
        sys.exit(1)

    # Skip # comment lines; first non-comment line that looks like CSV header is the data table start
    start_row = 0
    for i, line in enumerate(lines):
        if line.startswith("#"):
            continue
        if line.startswith("Date") or ("WTEQ" in line or "Snow" in line or "Precipitation" in line or "Snow Water" in line):
            start_row = i
            break
    content = "\n".join(lines[start_row:])
    df = pd.read_csv(io.StringIO(content), on_bad_lines="skip", low_memory=False)

    df = normalize_columns(df, station_name, station_id)
    out_path = Path(args.output) if args.output else CSV_DIR / f"{station_name}.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"Saved {len(df)} rows to {out_path}")


if __name__ == "__main__":
    main()
