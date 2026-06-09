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

def _note_from_status(status_text):
    parts = [p.strip() for p in str(status_text).split(" / ")]
    note_parts = [
        p
        for p in parts
        if p.lower() not in ("on", "off")
        and not re.search(r"^\d{3,4}\s+(on|off)\b", p, re.I)
    ]
    return " / ".join(note_parts).strip()


def _chronological_events(df):
    """Sorted on/off transitions from parsed operations rows."""
    events = []
    for _, row in df.sort_values("Date").iterrows():
        day = pd.Timestamp(row["Date"]).normalize()
        note = _note_from_status(row.get("Status_Text", ""))
        for col, kind in (("On_Time", "on"), ("Off_Time", "off")):
            tok = row.get(col)
            if tok is None or (isinstance(tok, float) and pd.isna(tok)):
                continue
            hhmm = _hhmm_display(tok)
            if not hhmm:
                continue
            ts = day + pd.Timedelta(hours=int(hhmm[:2]), minutes=int(hhmm[2:]))
            events.append(
                {
                    "ts": ts,
                    "kind": kind,
                    "hhmm": hhmm,
                    "note": note if kind == "on" else "",
                }
            )
    events.sort(key=lambda e: e["ts"])
    return events


def _fmt_mdy(d):
    return pd.Timestamp(d).strftime("%m/%d/%Y")


def _fmt_range(d0, d1):
    d0, d1 = pd.Timestamp(d0).normalize(), pd.Timestamp(d1).normalize()
    if d0 == d1:
        return _fmt_mdy(d0)
    return f"{_fmt_mdy(d0)} -- {_fmt_mdy(d1)}"


def _interior_full_days(period_start, period_end):
    """
    Calendar days fully contained in (period_start, period_end).
    Used to club multi-day off/on stretches between transition events.
    """
    start_day = pd.Timestamp(period_start).normalize()
    end_day = pd.Timestamp(period_end).normalize()
    if pd.Timestamp(period_start) > start_day:
        first = start_day + pd.Timedelta(days=1)
    else:
        first = start_day
    if pd.Timestamp(period_end) < end_day + pd.Timedelta(hours=23, minutes=59):
        last = end_day - pd.Timedelta(days=1)
    else:
        last = end_day
    if first > last:
        return None, None
    return first, last


def _append_interior_row(rows, period_start, period_end, *, is_on):
    first, last = _interior_full_days(period_start, period_end)
    if first is None:
        return
    span_days = (last - first).days + 1
    if is_on:
        if span_days >= 2:
            rows.append({"date": _fmt_range(first, last), "status": "on", "is_on": True})
        elif span_days == 1:
            rows.append({"date": _fmt_mdy(first), "status": "on", "is_on": True})
    else:
        if span_days >= 2:
            rows.append({"date": _fmt_range(first, last), "status": "off", "is_on": False})
        elif span_days == 1:
            rows.append({"date": _fmt_mdy(first), "status": "off", "is_on": False})


def _period_table_rows(events):
    """
    La Sal report style: transition rows with HHMM on/off; club multi-day off
    (and continuing on) stretches between transitions.
    """
    rows = []
    i = 0
    while i < len(events):
        ev = events[i]
        if ev["kind"] == "on":
            status = f"{ev['hhmm']} on"
            if ev.get("note"):
                status = f"{status} / {ev['note']}"
            rows.append({"date": _fmt_mdy(ev["ts"]), "status": status, "is_on": True})
            i += 1
            if i < len(events) and events[i]["kind"] == "off":
                off_ev = events[i]
                _append_interior_row(rows, ev["ts"], off_ev["ts"], is_on=True)
                rows.append(
                    {
                        "date": _fmt_mdy(off_ev["ts"]),
                        "status": f"{off_ev['hhmm']} off",
                        "is_on": False,
                    }
                )
                i += 1
                if i < len(events) and events[i]["kind"] == "on":
                    _append_interior_row(rows, off_ev["ts"], events[i]["ts"], is_on=False)
                    continue
            continue
        rows.append(
            {
                "date": _fmt_mdy(ev["ts"]),
                "status": f"{ev['hhmm']} off",
                "is_on": False,
            }
        )
        i += 1
        if i < len(events) and events[i]["kind"] == "on":
            _append_interior_row(rows, ev["ts"], events[i]["ts"], is_on=False)
    return rows


def _rows_within_report_month(rows, month, year):
    """Keep only rows that fall in the report calendar month; clip spanning ranges."""
    if month is None or year is None:
        return rows
    import calendar as cal

    month_start = pd.Timestamp(year, month, 1)
    month_end = pd.Timestamp(year, month, cal.monthrange(year, month)[1])
    kept = []
    for row in rows:
        date_col = row["date"]
        if " -- " in date_col:
            start_s, end_s = date_col.split(" -- ", 1)
            start_ts = pd.Timestamp(datetime.strptime(start_s.strip(), "%m/%d/%Y"))
            end_ts = pd.Timestamp(datetime.strptime(end_s.strip(), "%m/%d/%Y"))
            if end_ts < month_start or start_ts > month_end:
                continue
            clip_start = max(start_ts, month_start)
            clip_end = min(end_ts, month_end)
            row = {**row, "date": _fmt_range(clip_start, clip_end)}
        else:
            day_ts = pd.Timestamp(datetime.strptime(date_col.strip(), "%m/%d/%Y"))
            if day_ts < month_start or day_ts > month_end:
                continue
        kept.append(row)
    return kept


def generate_operations_table_latex(df, month, year):
    """
    Generate LaTeX operations schedule: transition events plus clubbed off/on
    stretches between them (La Sal monthly report format).
    Uses the full event log for state, then keeps only report-month dates.
    """
    events = _chronological_events(df)
    table_rows = _period_table_rows(events)
    table_rows = _rows_within_report_month(table_rows, month, year)

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


def _events_for_operations_table(df, month, year, *, lookback_days=30, lookahead_days=7):
    """
    Events for the LaTeX schedule table: report month plus nearby on/off rows
    that define carry-over periods (same convention as prior monthly reports).
    """
    month_start = datetime(year, month, 1)
    if month == 12:
        month_end = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = datetime(year, month + 1, 1) - timedelta(days=1)
    window_start = month_start - timedelta(days=lookback_days)
    window_end = month_end + timedelta(days=lookahead_days)
    out = df[(df["Date"] >= window_start) & (df["Date"] <= window_end)].copy()
    # After report month: include only through the first OFF (closes carry-over ON).
    post = out[out["Date"] > pd.Timestamp(month_end)].sort_values("Date")
    if not post.empty:
        cutoff = None
        for _, row in post.iterrows():
            st = str(row.get("Status_Text", "")).lower()
            if re.search(r"\d{3,4}\s+off\b", st) or st.strip() == "off":
                cutoff = row["Date"]
                break
        if cutoff is not None:
            out = out[out["Date"] <= cutoff]
    return out

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

    latex_table = generate_operations_table_latex(df, data_month, data_year)
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
