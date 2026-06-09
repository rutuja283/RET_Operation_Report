"""
Parse operations table data and generate CSV and LaTeX table.
Supports hardcoded data or file input (date, status per line or CSV).
"""
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import re
import sys
import argparse

sys.path.insert(0, str(Path(__file__).parent))
from config import CSV_DIR, BASE_DIR

_MDY = re.compile(r"^\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*$")


def _hhmm_display(raw):
    """Normalize time token to 4-digit HHMM for display (e.g. 352 -> 0352)."""
    s = str(raw).strip()
    if not s or s in ("---", "--", "-"):
        return None
    if s.isdigit():
        return s.zfill(4)[-4:]
    return s


def _tabular_line_to_status(parts):
    """
    Build WETA status string from tab row:
    Date, ON, OFF, ... optional trailing note (column 6+).
    """
    on_raw = parts[1].strip() if len(parts) > 1 else "---"
    off_raw = parts[2].strip() if len(parts) > 2 else "---"
    note_parts = [p.strip() for p in parts[5:] if p.strip()]
    note = " ".join(note_parts).strip()

    on_t = _hhmm_display(on_raw)
    off_t = _hhmm_display(off_raw)
    segs = []
    if on_t:
        segs.append(f"{on_t} on")
    if off_t:
        segs.append(f"{off_t} off")
    if not segs:
        status = "off"
    else:
        status = " / ".join(segs)
    if note:
        status = f"{status} / {note}"
    return status


def _parse_operations_rows(data, default_year, default_month):
    """
    Build DataFrame from list of (date_str, status_str) using same logic as parse_operations_data.
    default_year, default_month used when date string has no year (e.g. "5-Jan").
    """
    year = default_year
    month = default_month
    rows = []

    for date_str, status_str in data:
        if " to " in date_str:
            start_str, end_str = date_str.split(" to ")
            try:
                start_date = datetime.strptime(start_str.strip(), "%d-%b-%Y")
                end_date = datetime.strptime(end_str.strip(), "%d-%b-%Y")
                current = start_date
                days = []
                while current <= end_date:
                    days.append(current.day)
                    current += timedelta(days=1)
                year, month = start_date.year, start_date.month
            except Exception:
                start_day = int(re.search(r'\d+', start_str).group())
                end_day = int(re.search(r'\d+', end_str).group())
                days = list(range(start_day, end_day + 1))
        else:
            date_obj = None
            try:
                date_obj = datetime.strptime(date_str.strip(), "%m/%d/%Y")
            except Exception:
                pass
            if date_obj is not None:
                days = [date_obj.day]
                year, month = date_obj.year, date_obj.month
            else:
                try:
                    date_obj = datetime.strptime(date_str.strip(), "%d-%b-%Y")
                    days = [date_obj.day]
                    year, month = date_obj.year, date_obj.month
                except Exception:
                    day = int(re.search(r'\d+', date_str).group())
                    days = [day]

        on_time = None
        off_time = None
        is_on = False
        status_display = status_str
        status_lower = status_str.lower()

        if status_lower == "on":
            is_on = True
            status_display = "on"
        elif status_lower == "off":
            is_on = False
            status_display = "off"
        elif " / " in status_str:
            parts = status_str.split(" / ")
            for part in parts:
                time_match = re.search(r'(\d{4})', part)
                if time_match:
                    time_val = time_match.group(1)
                    if "on" in part.lower():
                        on_time = time_val
                        is_on = True
                    elif "off" in part.lower():
                        off_time = time_val
            status_display = status_str
        else:
            time_match = re.search(r"(\d{3,4})", status_str)
            if time_match:
                time_val = time_match.group(1)
                if "off" in status_lower:
                    off_time = time_val
                    is_on = False
                    status_display = status_str
                elif "on" in status_lower:
                    on_time = time_val
                    is_on = True
                    status_display = status_str

        # Operating / green highlight: explicit ON (plain or HHMM-on), not off-only lines
        is_on = status_lower.strip() == "on" or bool(
            re.search(r"\d{3,4}\s+on\b", status_lower)
        )
        for day in days:
            date = datetime(year, month, day)
            rows.append({
                'Date': date,
                'On_Time': on_time,
                'Off_Time': off_time,
                'Operating': is_on,
                'Status_Text': status_display
            })

    df = pd.DataFrame(rows)
    if len(df) > 0:
        df = df.sort_values('Date')
    return df


def _excel_time_token(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip()
    if not s or s in ("---", "--", "-", "nan"):
        return None
    if s.isdigit():
        return s.zfill(4)[-4:]
    return s


def parse_operations_from_excel(path, month=None, year=None):
    """
    Read WA25001-style operating record (.xlsx).
    Row 0 is title; row 1 is header: Date, On Time, Off Time, ...
    Returns the same DataFrame schema as parse_operations_from_file.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Operations Excel not found: {path}")
    raw = pd.read_excel(path, header=1)
    raw = raw.rename(
        columns={
            raw.columns[0]: "Date",
            raw.columns[1]: "On",
            raw.columns[2]: "Off",
        }
    )
    if len(raw.columns) > 5:
        raw = raw.rename(columns={raw.columns[5]: "Comment"})
    else:
        raw["Comment"] = ""
    raw["Date"] = pd.to_datetime(raw["Date"], errors="coerce")
    raw = raw[raw["Date"].notna()].copy()

    data = []
    for _, row in raw.iterrows():
        date_str = row["Date"].strftime("%m/%d/%Y")
        on_t = _excel_time_token(row.get("On"))
        off_t = _excel_time_token(row.get("Off"))
        note = ""
        if "Comment" in row.index and pd.notna(row.get("Comment")):
            note = str(row["Comment"]).strip()
        segs = []
        if on_t:
            segs.append(f"{on_t} on")
        if off_t:
            segs.append(f"{off_t} off")
        if not segs:
            continue
        status = " / ".join(segs)
        if note:
            status = f"{status} / {note}"
        data.append((date_str, status))

    default_year = year if year is not None else int(raw["Date"].dt.year.iloc[0])
    default_month = month if month is not None else int(raw["Date"].dt.month.iloc[0])
    return _parse_operations_rows(data, default_year, default_month)


def _sorted_on_off_events(df):
    """Chronological (timestamp, 'on'|'off') from parsed operations rows."""
    events = []
    for _, row in df.iterrows():
        d = pd.Timestamp(row["Date"]).normalize()
        for col, kind in (("On_Time", "on"), ("Off_Time", "off")):
            tok = row.get(col)
            if tok is None or (isinstance(tok, float) and pd.isna(tok)):
                continue
            s = str(tok).strip()
            if not s or s in ("---", "nan", "None"):
                continue
            if s.endswith(".0"):
                s = s[:-2]
            if s.isdigit():
                s = s.zfill(4)[-4:]
            events.append(
                (
                    d + pd.Timedelta(hours=int(s[:2]), minutes=int(s[2:])),
                    kind,
                )
            )
    events.sort(key=lambda x: x[0])
    return events


def build_on_intervals(events):
    """Return list of (start_ts, end_ts|None) for each WETA ON interval."""
    intervals = []
    on_start = None
    for ts, kind in events:
        if kind == "on":
            if on_start is None:
                on_start = ts
        elif on_start is not None:
            intervals.append((on_start, ts))
            on_start = None
    if on_start is not None:
        intervals.append((on_start, None))
    return intervals


def expand_operations_daily(df, month, year):
    """
    Expand event log into per-day rows for the report month, including carry-over
    ON state from before the month (e.g. April on continuing into May).
    """
    import calendar as cal

    events = _sorted_on_off_events(df)
    month_start = pd.Timestamp(year, month, 1)
    last_day = cal.monthrange(year, month)[1]
    month_end = pd.Timestamp(year, month, last_day) + pd.Timedelta(hours=23, minutes=59)

    rows = []
    for start, end in build_on_intervals(events):
        end_eff = end if end is not None else month_end + pd.Timedelta(days=365)
        if end_eff < month_start or start > month_end:
            continue
        cur_day = max(start.normalize(), month_start)
        while cur_day <= month_end.normalize():
            day_start = cur_day
            day_end = cur_day + pd.Timedelta(hours=23, minutes=59)
            seg_start = max(start, day_start)
            seg_end = min(end_eff, day_end)
            if seg_start <= seg_end:
                on_time = seg_start.strftime("%H%M")
                off_time = seg_end.strftime("%H%M")
                if seg_end >= day_end - pd.Timedelta(minutes=1):
                    off_time = ""
                if seg_start <= day_start + pd.Timedelta(minutes=1):
                    on_time = ""
                rows.append(
                    {
                        "Date": cur_day,
                        "On_Time": on_time,
                        "Off_Time": off_time,
                        "Operating": True,
                        "Status_Text": "on",
                    }
                )
            cur_day += pd.Timedelta(days=1)

    if not rows:
        return pd.DataFrame(
            columns=["Date", "On_Time", "Off_Time", "Operating", "Status_Text"]
        )
    out = pd.DataFrame(rows)
    out = out.drop_duplicates(subset=["Date"], keep="first")
    return out.sort_values("Date").reset_index(drop=True)


def parse_operations_from_file(path, month, year):
    """
    Read operations data from a file. Expects one record per line:
    - CSV: date,status (e.g. "01-Jan-2026,2157 off")
    - Or two columns separated by comma; date in DD-Mon-YYYY or DD-Mon format.
    Returns DataFrame with Date, On_Time, Off_Time, Operating, Status_Text.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Operations file not found: {path}")
    data = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "\t" in line:
                parts = [p.strip() for p in line.split("\t")]
                if len(parts) >= 3 and _MDY.match(parts[0]):
                    status = _tabular_line_to_status(parts)
                    data.append((parts[0], status))
                    continue
                parts_tab = [p.strip() for p in line.split("\t", 1)]
                if len(parts_tab) >= 2:
                    data.append((parts_tab[0], parts_tab[1]))
                    continue
            parts = [p.strip() for p in line.split(",", 1)]
            if len(parts) >= 2:
                data.append((parts[0], parts[1]))
    return _parse_operations_rows(data, year, month)


def parse_operations_data():
    """
    Parse the operations data (hardcoded default). Returns DataFrame with Date, On_Time, Off_Time, Operating, Status_Text.
    """
    data = [
        ("01-Jan-2026", "2157 off"),
        ("04-Jan-2026", "1939 on"),
        ("05-Jan-2026", "1134 off"),
        ("05-Jan-2026", "2354 on"),
        ("06-Jan-2026", "1159 off"),
        ("07-Jan-2026", "1605 on"),
        ("09-Jan-2026", "1243 off"),
    ]
    return _parse_operations_rows(data, default_year=2026, default_month=1)

def generate_operations_table_latex(df, month, year):
    """
    Generate LaTeX table in the format shown by user
    Consolidates multiple entries for the same day
    """
    # First, consolidate entries for the same day
    daily_entries = {}
    for idx, row in df.iterrows():
        date = row['Date']
        date_key = date.date()  # Use date as key
        
        if date_key not in daily_entries:
            daily_entries[date_key] = {
                'date': date,
                'status_texts': [],
                'is_on': False
            }
        
        # Add status text for this entry
        daily_entries[date_key]['status_texts'].append(row['Status_Text'])
        # Only mark as operating if status text explicitly contains "on"
        # (not just "off" which means it was on earlier but turned off)
        status_lower = row['Status_Text'].lower()
        if "on" in status_lower:
            daily_entries[date_key]['is_on'] = True
    
    # Convert to list and sort by date
    consolidated_rows = []
    for date_key in sorted(daily_entries.keys()):
        entry = daily_entries[date_key]
        # Combine multiple status texts for the same day with " / "
        combined_status = " / ".join(entry['status_texts'])
        consolidated_rows.append({
            'date': entry['date'],
            'status': combined_status,
            'is_on': entry['is_on']
        })
    
    # Now group consecutive days with same status text
    table_rows = []
    current_range_start = None
    current_range_end = None
    current_status_text = None
    current_is_on = None
    
    for row in consolidated_rows:
        date = row['date']
        status_text = row['status']
        is_on = row['is_on']
        
        # Check if we can merge with previous row
        if (current_range_start is not None and 
            current_status_text == status_text):
            # Extend range
            current_range_end = date
        else:
            # Save previous range if exists
            if current_range_start is not None:
                if current_range_start == current_range_end:
                    date_col = current_range_start.strftime("%m/%d/%Y")
                else:
                    date_col = f"{current_range_start.strftime('%m/%d/%Y')} -- {current_range_end.strftime('%m/%d/%Y')}"
                
                table_rows.append({
                    'date': date_col,
                    'status': current_status_text,
                    'is_on': current_is_on
                })
            
            # Start new range
            current_range_start = date
            current_range_end = date
            current_status_text = status_text
            current_is_on = is_on
    
    # Add last range
    if current_range_start is not None:
        if current_range_start == current_range_end:
            date_col = current_range_start.strftime("%m/%d/%Y")
        else:
            date_col = f"{current_range_start.strftime('%m/%d/%Y')} -- {current_range_end.strftime('%m/%d/%Y')}"
        
        table_rows.append({
            'date': date_col,
            'status': current_status_text,
            'is_on': current_is_on
        })
    
    # Generate LaTeX
    latex_lines = []
    latex_lines.append("\\begin{longtable}{|p{5cm}|p{10cm}|}")
    latex_lines.append("\\hline")
    latex_lines.append("\\textbf{DATE(S)} & \\textbf{WETA (ON/OFF)} \\\\")
    latex_lines.append("\\hline")
    latex_lines.append("\\endfirsthead")
    latex_lines.append("\\hline")
    latex_lines.append("\\textbf{DATE(S)} & \\textbf{WETA (ON/OFF)} \\\\")
    latex_lines.append("\\hline")
    latex_lines.append("\\endhead")
    latex_lines.append("\\hline")
    latex_lines.append("\\endfoot")
    latex_lines.append("\\hline")
    latex_lines.append("\\endlastfoot")
    
    for row in table_rows:
        date_col = row['date']
        status_col = row['status']
        is_on = row['is_on']
        
        # Add green highlighting if WETA is on
        if is_on:
            latex_lines.append("\\rowcolor{greenhighlight}")
        
        latex_lines.append(f"{date_col} & {status_col} \\\\")
        latex_lines.append("\\hline")
    
    latex_lines.append("\\end{longtable}")
    
    return "\n".join(latex_lines)

def _run(operations_input=None, month=None, year=None):
    """Parse operations, write CSV and LaTeX. Uses file if operations_input given else hardcoded data."""
    if operations_input and Path(operations_input).exists():
        if month is None or year is None:
            print("Error: --month and --year are required when using --input")
            sys.exit(1)
        src = Path(operations_input)
        if src.suffix.lower() in (".xlsx", ".xls"):
            df = parse_operations_from_excel(src, month=month, year=year)
        else:
            df = parse_operations_from_file(operations_input, month, year)
        data_month, data_year = month, year
    else:
        df = parse_operations_data()
        if len(df) > 0:
            data_month = int(df['Date'].dt.month.iloc[0])
            data_year = int(df['Date'].dt.year.iloc[0])
        else:
            data_month, data_year = 1, 2026

    csv_path = CSV_DIR / "operations_schedule.csv"
    if data_month is not None and data_year is not None:
        df_daily = expand_operations_daily(df, data_month, data_year)
        if not df_daily.empty:
            df_export = df_daily[["Date", "Operating", "On_Time", "Off_Time"]].copy()
        else:
            df_export = df[["Date", "Operating", "On_Time", "Off_Time"]].copy()
    else:
        df_export = df[["Date", "Operating", "On_Time", "Off_Time"]].copy()
    df_export["Date"] = df_export["Date"].dt.strftime("%Y-%m-%d")
    for col in ("On_Time", "Off_Time"):
        def _fmt_time(x):
            if x is None or (isinstance(x, float) and pd.isna(x)):
                return ""
            s = str(x).strip()
            if not s or s.lower() in ("nan", "none"):
                return ""
            if s.endswith(".0"):
                s = s[:-2]
            if s.isdigit():
                return s.zfill(4)[-4:]
            return s

        df_export[col] = df_export[col].apply(_fmt_time)
    df_export.to_csv(csv_path, index=False)
    print(f"Saved operations CSV to {csv_path}")

    # LaTeX schedule: only events in the report month (not carry-over shading rows)
    if data_month is not None and data_year is not None:
        month_start = datetime(data_year, data_month, 1)
        if data_month == 12:
            month_end = datetime(data_year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = datetime(data_year, data_month + 1, 1) - timedelta(days=1)
        df_month = df[(df["Date"] >= month_start) & (df["Date"] <= month_end)].copy()
    else:
        df_month = df
    latex_table = generate_operations_table_latex(df_month, data_month, data_year)
    latex_path = BASE_DIR / "operations_table.tex"
    with open(latex_path, 'w') as f:
        f.write(latex_table)
    print(f"Saved LaTeX table to {latex_path}")
    return csv_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse operations table and generate CSV + LaTeX")
    parser.add_argument("--input", "-i", help="Path to operations file (date,status per line or CSV)")
    parser.add_argument("--month", "-m", type=int, help="Report month (1-12), required with --input")
    parser.add_argument("--year", "-y", type=int, help="Report year, required with --input")
    args = parser.parse_args()

    _run(operations_input=args.input, month=args.month, year=args.year)
    print("\nDone.")
