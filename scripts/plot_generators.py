"""
Plot generation functions for RET Operations Report
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Patch
from pathlib import Path
from datetime import datetime, timedelta
import calendar

import sys
from pathlib import Path
# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from config import (
    CSV_DIR, PLOTS_DIR, TREATMENT_STATIONS, CONTROL_STATIONS,
    WATER_YEAR_START_MONTH, WATER_YEAR_START_DAY, PLOT_DPI, PLOT_FORMAT
)

# Display labels for boxplot panel titles (camel casing for report)
STATION_DISPLAY_NAMES = {
    "La sal upper": "La sal Upper",
    "Lasal Mtn lower": "La sal Lower",
    "Camp jackson": "Camp Jackson",
    "Buckboard Flat": "Buckboard Flat",
    "Elke Ridge": "Elke Ridge",
    "Gold Basin": "Gold Basin",
}


def get_water_year(date):
    """Get water year for a date (starts Oct 1)"""
    if date.month >= WATER_YEAR_START_MONTH:
        return date.year + 1
    return date.year


def handle_snotel_cumulative(df, date_col, value_col):
    """
    Convert cumulative SNOTEL data to daily increments
    Handles water year reset on October 1st
    """
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.sort_values(date_col).reset_index(drop=True)
    
    # Add water year column
    df['water_year'] = df[date_col].apply(get_water_year)
    
    # Calculate daily differences within each water year
    df['daily_diff'] = df.groupby('water_year')[value_col].diff()
    
    # For first day of water year, use the value as-is (or 0 if reset)
    first_day_mask = df.groupby('water_year')[date_col].transform('min') == df[date_col]
    df.loc[first_day_mask, 'daily_diff'] = df.loc[first_day_mask, value_col]
    
    # Handle negative differences (sensor corrections/resets) - set to NaN
    df.loc[df['daily_diff'] < 0, 'daily_diff'] = np.nan
    
    return df[date_col], df['daily_diff']


def load_station_data(station_name, date_col=None, value_col=None):
    """Load CSV data for a station"""
    csv_file = CSV_DIR / f"{station_name}.csv"
    
    if not csv_file.exists():
        print(f"Warning: CSV file not found for {station_name}: {csv_file}")
        return None
    
    df = pd.read_csv(csv_file)
    
    # Auto-detect date column if not provided
    if date_col is None:
        for col in df.columns:
            col_lower = str(col).lower()
            if any(term in col_lower for term in ['date', 'time', 'timestamp']):
                date_col = col
                break
    
    if date_col is None or date_col not in df.columns:
        print(f"Warning: Could not find date column in {station_name}")
        return None
    
    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
    df = df[df[date_col].notna()].copy()
    
    return df, date_col


def plot_operations_schedule(operations_df, month, year, output_file=None):
    """
    Generate operations schedule plot with green shading for operating periods.
    Uses expanded daily ON state (including carry-over from prior months).
    """
    month_start = datetime(year, month, 1)
    if month == 12:
        month_end = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = datetime(year, month + 1, 1) - timedelta(days=1)

    daily = operations_df.copy()
    daily["Date"] = pd.to_datetime(daily["Date"], errors="coerce")
    daily = daily[(daily["Date"] >= month_start) & (daily["Date"] <= month_end)]
    daily = daily[daily["Operating"] == True]
    if daily.empty:
        print(f"Warning: No operations data for {month}/{year}")
        return None

    fig, ax = plt.subplots(figsize=(14, 4))
    dates = pd.date_range(start=month_start, end=month_end, freq="D")
    operating_days = set(pd.to_datetime(daily["Date"]).dt.date)

    for date in dates:
        if date.date() in operating_days:
            ax.axvspan(
                date - timedelta(hours=12),
                date + timedelta(hours=12),
                color="#2ecc71",
                alpha=0.45,
                edgecolor="#145a32",
                linewidth=0.6,
                zorder=0,
            )

    ax.set_xlim(dates[0] - timedelta(days=0.5), dates[-1] + timedelta(days=0.5))
    ax.set_xlabel("Date")
    ax.set_ylabel("")
    ax.set_yticks([])
    ax.set_title(f"WETA Operating Schedule — {calendar.month_name[month]} {year}")
    ax.grid(True, alpha=0.3, axis="x")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(dates) // 10)))
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    if output_file is None:
        output_file = PLOTS_DIR / f"{year}{month:02d}_OperatingSchedule_Report.{PLOT_FORMAT}"
    
    plt.savefig(output_file, dpi=PLOT_DPI, bbox_inches='tight')
    print(f"Saved: {output_file}")
    plt.close()
    
    return output_file


def _hhmm_token_to_day_fraction(token):
    """Map HHMM (digits only) to fraction of calendar day from midnight [0, 1)."""
    if token is None:
        return None
    s = str(token).strip()
    if not s or s in ("---", "--", "-") or s.lower() in ("nan", "none"):
        return None
    if s.endswith(".0"):
        s = s[:-2]
    if not s.isdigit():
        return None
    s = s.zfill(4)[-4:]
    h, m = int(s[:2]), int(s[2:4])
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return None
    return (h * 60 + m) / (24.0 * 60.0)


def _weta_on_day_x_span(day_index, on_frac, off_frac):
    """
    Map WETA ON interval within a calendar day to x coordinates.
    Day ``day_index`` spans [day_index - 0.5, day_index + 0.5] (bar centers at integers).
    Returns (x_left, x_right) or None if invalid.
    """
    day_lo = day_index - 0.5
    day_hi = day_index + 0.5
    if on_frac is None:
        return (day_lo, day_hi)
    left = day_lo + on_frac
    if off_frac is not None and off_frac > on_frac:
        right = day_lo + off_frac
    else:
        right = day_hi
    left = max(left, day_lo)
    right = min(right, day_hi)
    if right <= left:
        return None
    return (left, right)


def plot_precipitation_summary(stations_data, operations_df, month, year, output_file=None):
    """
    Bar chart of daily precipitation (from Precipitation Accumulation) in inches,
    with green vertical bands for WETA **ON** periods (sub-day when ON/OFF times are known).
    One bar per station per day. Uses numeric x (0..n_days) so bars and WETA bands align.
    Legend includes a green WETA operating swatch.
    """
    month_start = datetime(year, month, 1)
    if month == 12:
        month_end = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = datetime(year, month + 1, 1) - timedelta(days=1)
    
    dates = pd.date_range(start=month_start, end=month_end, freq='D')
    n_days = len(dates)
    
    fig, ax = plt.subplots(figsize=(14, 6))
    # Use numeric x so bars and axvspan share the same scale
    ax.set_xlim(-0.5, n_days - 0.5)
    
    weta_highlighted = False
    # Green bands: daily ON windows (CSV includes carry-over from prior month)
    if not operations_df.empty and "Date" in operations_df.columns:
        month_ops = operations_df.copy()
        month_ops["Date"] = pd.to_datetime(month_ops["Date"], errors="coerce").dt.normalize()
        month_ops = month_ops[
            (month_ops["Date"] >= month_start) & (month_ops["Date"] <= month_end)
        ]
        if not month_ops.empty:
            on_rows = month_ops[month_ops["Operating"] == True]
            n_spans = 0
            for _, row in on_rows.iterrows():
                d = row['Date'].date()
                day_indices = [j for j, dt in enumerate(dates) if dt.date() == d]
                if not day_indices:
                    continue
                j = day_indices[0]

                on_t = ''
                if 'On_Time' in row.index and pd.notna(row['On_Time']):
                    on_t = str(row['On_Time']).strip()
                off_t = ''
                if 'Off_Time' in row.index and pd.notna(row['Off_Time']):
                    off_t = str(row['Off_Time']).strip()
                f_on = _hhmm_token_to_day_fraction(on_t) if on_t else None
                f_off = _hhmm_token_to_day_fraction(off_t) if off_t else None
                span = _weta_on_day_x_span(j, f_on, f_off)
                if span:
                    x0, x1 = span
                    ax.axvspan(
                        x0, x1,
                        facecolor='#2ecc71',
                        alpha=0.45,
                        edgecolor='#145a32',
                        linewidth=0.9,
                        zorder=0,
                    )
                    n_spans += 1
                    weta_highlighted = True
            print(f"   WETA ON highlights: {len(on_rows)} day(s), {n_spans} time window(s)")
    
    # Bar chart: one bar per station per day (x = day index 0..n_days-1)
    n_stations = len(stations_data)
    width = 0.8 / max(n_stations, 1)
    colors = plt.cm.tab10(np.linspace(0, 1, n_stations))
    day_axis = np.arange(n_days)
    
    for i, (station_name, (station_dates, values)) in enumerate(stations_data.items()):
        if not isinstance(station_dates, pd.Series):
            station_dates = pd.Series(station_dates)
        station_dates = pd.to_datetime(station_dates, errors='coerce').dt.normalize().dt.date
        vals = np.asarray(values, dtype=float)
        if len(vals) != len(station_dates):
            vals = np.asarray(values, dtype=float)[: len(station_dates)]
        by_date = pd.Series(vals, index=station_dates)
        by_date = by_date[~by_date.index.duplicated(keep='first')]
        precip_per_day = np.zeros(n_days)
        for j, d in enumerate(dates):
            d_date = d.date()
            if d_date in by_date.index:
                precip_per_day[j] = float(by_date.loc[d_date])
        offset = (i - (n_stations - 1) / 2) * width
        label = STATION_DISPLAY_NAMES.get(station_name, station_name)
        ax.bar(
            day_axis + offset,
            precip_per_day,
            width,
            label=label,
            color=colors[i],
            edgecolor="gray",
            linewidth=0.3,
            zorder=1,
        )
    
    # Show x-ticks at readable interval (every 2–3 days) so labels don't overlap
    tick_step = max(1, (n_days + 6) // 10)
    tick_indices = list(range(0, n_days, tick_step))
    if tick_indices[-1] != n_days - 1:
        tick_indices.append(n_days - 1)
    ax.set_xticks(tick_indices)
    ax.set_xticklabels([f"{dates[j].day}-{dates[j].strftime('%b')}" for j in tick_indices], rotation=45, ha='right')
    ax.set_xlabel('Date')
    ax.set_ylabel('Precip (in)')
    ax.set_title(f"{calendar.month_name[month]} Precipitation Summary")
    handles, labels = ax.get_legend_handles_labels()
    if weta_highlighted:
        handles.append(
            Patch(facecolor="#2ecc71", edgecolor="#145a32", alpha=0.45, label="WETA operating")
        )
        labels.append("WETA operating")
    ax.legend(handles, labels, loc="upper right", ncol=2, framealpha=0.9)
    ax.set_ylim(0, None)
    ax.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()
    
    if output_file is None:
        output_file = PLOTS_DIR / f"{year}{month:02d}_PrecipSummary_Report_v02.{PLOT_FORMAT}"
    plt.savefig(output_file, dpi=PLOT_DPI, bbox_inches='tight')
    print(f"Saved: {output_file}")
    plt.close()
    return output_file


def _find_precip_accum_column(df):
    for col in df.columns:
        c = str(col).lower()
        if "precipitation accumulation" in c or ("precip" in c and "accum" in c):
            return col
    return None


def _month_precip_total(df, date_col, prec_col, year, month):
    """Calendar-month precip from SNOTEL accumulation: last day minus first day of month (inches)."""
    last_day = calendar.monthrange(year, month)[1]
    start_date = f"{year}-{month:02d}-01"
    end_date = f"{year}-{month:02d}-{last_day:02d}"
    start_row = df[df[date_col].dt.strftime("%Y-%m-%d") == start_date]
    end_row = df[df[date_col].dt.strftime("%Y-%m-%d") == end_date]
    if start_row.empty or end_row.empty:
        return None
    start_val = start_row.iloc[0][prec_col]
    end_val = end_row.iloc[0][prec_col]
    if pd.isna(start_val) or pd.isna(end_val):
        return None
    return float(end_val - start_val)


def _find_swe_or_snow_depth_column(df, prefer_swe=True):
    """Return column name for SWE (snow water equivalent) or snow depth. Prefer SWE when prefer_swe=True."""
    swe_col = None
    depth_col = None
    for col in df.columns:
        c = str(col).lower()
        if 'snow water equivalent' in c or ('water equivalent' in c and 'snow' in c) or (c.startswith('swe') or ' swe ' in c):
            swe_col = col
            break
    for col in df.columns:
        c = str(col).lower()
        if 'snow' in c and 'depth' in c:
            depth_col = col
            break
    if prefer_swe and swe_col is not None:
        return swe_col, 'swe'
    if depth_col is not None:
        return depth_col, 'depth'
    if swe_col is not None:
        return swe_col, 'swe'
    return None, None


def plot_snow_depth_boxplots(treatment_station, control_station, month, year, 
                             highlight_month=None, highlight_year=None, output_file=None, use_swe=True):
    """
    Generate three-panel boxplot: Treatment, Control, and Difference.
    Uses Snow Water Equivalent (SWE) by default to match February report; set use_swe=False for snow depth.
    Shows only the specified month (not all months).
    
    Args:
        treatment_station: Name of treatment station
        control_station: Name of control station
        month: Month number for the report (1-12)
        year: Year for the report
        highlight_month: Month to highlight (defaults to month)
        highlight_year: Year to highlight (defaults to year)
        output_file: Output file path (if None, auto-generates with station names)
        use_swe: If True (default), plot Snow Water Equivalent; else Snow Depth
    """
    # Load data
    treatment_df, date_col_t = load_station_data(treatment_station)
    control_df, date_col_c = load_station_data(control_station)
    
    if treatment_df is None or control_df is None:
        print(f"Warning: Could not load data for {treatment_station} or {control_station}")
        return None
    
    # Find SWE or snow depth column (prefer SWE to match February report)
    snow_col_t, var_t = _find_swe_or_snow_depth_column(treatment_df, prefer_swe=use_swe)
    snow_col_c, var_c = _find_swe_or_snow_depth_column(control_df, prefer_swe=use_swe)
    
    if snow_col_t is None or snow_col_c is None:
        print(f"Warning: Could not find SWE/snow depth column")
        return None
    
    var_label = "Snow Water Equivalent (in)" if (var_t == 'swe' or var_c == 'swe') else "Snow Depth (in)"
    var_short = "SWE" if (var_t == 'swe' or var_c == 'swe') else "Snow Depth"
    
    # Prepare data
    treatment_df = treatment_df[[date_col_t, snow_col_t]].copy()
    treatment_df.columns = ['Date', 'Value']
    treatment_df['Date'] = pd.to_datetime(treatment_df['Date'])
    treatment_df['month'] = treatment_df['Date'].dt.month
    treatment_df['year'] = treatment_df['Date'].dt.year
    
    control_df = control_df[[date_col_c, snow_col_c]].copy()
    control_df.columns = ['Date', 'Value']
    control_df['Date'] = pd.to_datetime(control_df['Date'])
    control_df['month'] = control_df['Date'].dt.month
    control_df['year'] = control_df['Date'].dt.year
    
    # Water-year start through report month: Dec (prev year), Jan, ..., report month.
    # Dec of previous year and Jan..report_month of report year highlighted.
    month_name = calendar.month_name[highlight_month] if highlight_month else calendar.month_name[month]
    target_month = highlight_month if highlight_month else month
    
    months_to_plot = [12] + list(range(1, target_month + 1))
    month_labels = [f"Dec {str(year-1)[-2:]}"] + [
        f"{calendar.month_abbr[m]} {str(year)[-2:]}" for m in range(1, target_month + 1)
    ]
    
    treatment_groups: list[np.ndarray] = []
    control_groups: list[np.ndarray] = []
    diff_groups: list[np.ndarray] = []
    labels: list[str] = []
    
    highlight_idxs: list[int] = []
    highlight_t: list[float] = []
    highlight_c: list[float] = []
    highlight_d: list[float] = []
    
    for idx, (m, label) in enumerate(zip(months_to_plot, month_labels), start=1):
        t_data = treatment_df[treatment_df['month'] == m]['Value'].dropna().values
        c_data = control_df[control_df['month'] == m]['Value'].dropna().values
        
        if len(t_data) == 0 or len(c_data) == 0:
            continue
        
        # Merge on date to get differences for all years for this month
        t_month = treatment_df[treatment_df['month'] == m].set_index('Date')['Value']
        c_month = control_df[control_df['month'] == m].set_index('Date')['Value']
        
        merged = pd.DataFrame({'Treatment': t_month, 'Control': c_month})
        merged = merged.dropna()
        merged['Diff'] = merged['Treatment'] - merged['Control']
        
        if len(merged) == 0:
            continue
        
        treatment_groups.append(t_data)
        control_groups.append(c_data)
        diff_groups.append(merged['Diff'].values)
        labels.append(label)
        
        # Highlight year: previous year for December, report year for January
        if m == 12:
            hy = year - 1
        else:
            hy = year
        
        merged_yr = merged[merged.index.year == hy]
        if len(merged_yr) > 0:
            highlight_idxs.append(idx)
            highlight_t.append(float(merged_yr['Treatment'].mean()))
            highlight_c.append(float(merged_yr['Control'].mean()))
            highlight_d.append(float(merged_yr['Diff'].mean()))
    
    if not labels:
        print("Warning: No overlapping data found for boxplot months")
        return None
    
    highlight_vals = None
    if highlight_idxs and highlight_t and highlight_c and highlight_d:
        highlight_vals = {
            't': highlight_t,
            'c': highlight_c,
            'd': highlight_d
        }
    
    # Create three-panel plot: [Treatment | Control | Difference] in one row.
    # Slightly wider to better fill the horizontal space in the report.
    fig, (ax1, ax2, ax3) = plt.subplots(
        1, 3, figsize=(8.8, 3.0), sharey=False
    )
    
    # Boxplot styling: light blue boxes, hollow light-blue outliers,
    # red circles for highlighted years, no gridlines.
    def style_boxplot(bp):
        for box in bp['boxes']:
            box.set_facecolor('#c6dbef')  # light blue fill
            box.set_edgecolor('#1f77b4')  # blue edge
            box.set_linewidth(1.2)
        for whisker in bp['whiskers']:
            whisker.set_color('#1f77b4')
            whisker.set_linewidth(1)
        for cap in bp['caps']:
            cap.set_color('#1f77b4')
            cap.set_linewidth(1)
        for median in bp['medians']:
            median.set_color('#1f77b4')
            median.set_linewidth(1.5)
        # Style fliers (outliers) as small hollow light-blue circles so that
        # they are de‑emphasized relative to the boxes.
        for flier in bp['fliers']:
            flier.set_marker('o')
            flier.set_markerfacecolor('none')
            flier.set_markeredgecolor('#1f77b4')
            flier.set_markersize(3)
            flier.set_alpha(0.9)

    bp1 = ax1.boxplot(
        treatment_groups, labels=labels,
        showfliers=True, patch_artist=True, widths=0.5
    )
    style_boxplot(bp1)
    treatment_display = STATION_DISPLAY_NAMES.get(treatment_station, treatment_station)
    ax1.set_title(f"{treatment_display}", fontsize=10, fontweight='bold')
    ax1.set_ylabel(var_label, fontsize=9)
    ax1.tick_params(axis="both", labelsize=8)
    ax1.tick_params(axis="x", rotation=0)

    bp2 = ax2.boxplot(
        control_groups, labels=labels,
        showfliers=True, patch_artist=True, widths=0.5
    )
    style_boxplot(bp2)
    control_display = STATION_DISPLAY_NAMES.get(control_station, control_station)
    ax2.set_title(f"{control_display}", fontsize=10, fontweight='bold')
    ax2.tick_params(axis="both", labelsize=8)
    ax2.tick_params(axis="x", rotation=0)

    bp3 = ax3.boxplot(
        diff_groups, labels=labels,
        showfliers=True, patch_artist=True, widths=0.5
    )
    style_boxplot(bp3)
    ax3.set_title(f"TREATMENT - CONTROL", fontsize=10, fontweight='bold')
    ax3.set_ylabel("Difference (in)", fontsize=9)
    ax3.tick_params(axis="both", labelsize=8)
    ax3.tick_params(axis="x", rotation=0)
    ax3.axhline(y=0, color='black', linestyle='--', linewidth=1, alpha=0.5)

    # Red circles = December (previous year) and January (current year);
    # blue fliers already set above = climatological outliers.
    if highlight_vals is not None:
        def annotate_dots(ax, xs, ys):
            for x, y in zip(xs, ys):
                if x is not None and y is not None and np.isfinite(y):
                    ax.scatter([x], [y], s=40, color='red', edgecolors='black',
                               linewidths=1.1, zorder=25, marker='o')

        annotate_dots(ax1, highlight_idxs, highlight_vals['t'])
        annotate_dots(ax2, highlight_idxs, highlight_vals['c'])
        annotate_dots(ax3, highlight_idxs, highlight_vals['d'])
    
    # Set dynamic y-limits for each panel based on their own data
    # Set dynamic y-limits for each panel based on all data points.
    # Treatment & Control panels share the same y-scale (0 to a rounded max),
    # similar to the screenshot, while the Difference panel can have its own.
    if treatment_groups and control_groups:
        t_values = np.concatenate(treatment_groups)
        c_values = np.concatenate(control_groups)
        all_tc = np.concatenate([t_values, c_values])
        if highlight_vals is not None:
            all_tc = np.append(all_tc, highlight_vals['t'])
            all_tc = np.append(all_tc, highlight_vals['c'])
        tc_max = float(np.nanmax(all_tc)) if all_tc.size else 0.0
        # Round up to a clean number (nearest 5)
        if tc_max <= 0:
            y_max_tc = 1.0
        else:
            y_max_tc = 5 * np.ceil(tc_max / 5.0)
        ax1.set_ylim(0, y_max_tc)
        ax2.set_ylim(0, y_max_tc)
    
    # Difference panel (ax3) - can be negative, so use full range
    if diff_groups:
        d_values = np.concatenate(diff_groups)
        if highlight_vals is not None:
            d_values = np.append(d_values, highlight_vals['d'])
        d_min = np.nanmin(d_values)
        d_max = np.nanmax(d_values)
        d_range = d_max - d_min
        d_padding = max(0.1 * d_range, 0.05 * (abs(d_min) + abs(d_max))) if d_range > 0 else 0.05 * max(abs(d_min), abs(d_max)) if max(abs(d_min), abs(d_max)) > 0 else 1
        ax3.set_ylim(d_min - d_padding, d_max + d_padding)
    
    try:
        plt.tight_layout()
    except:
        # If tight_layout fails, just adjust manually
        plt.subplots_adjust(bottom=0.18, top=0.92, hspace=0.45, wspace=0.25)
    
    if output_file is None:
        # Include station names; use SWE in filename when plotting SWE to match February report
        treatment_clean = treatment_station.replace(" ", "_").replace("/", "_")
        control_clean = control_station.replace(" ", "_").replace("/", "_")
        var_tag = "SWE" if (var_t == 'swe' or var_c == 'swe') else "SnowDepth"
        output_file = PLOTS_DIR / f"{year}{month:02d}_{var_tag}_{treatment_clean}_vs_{control_clean}.{PLOT_FORMAT}"
    
    plt.savefig(output_file, dpi=PLOT_DPI, bbox_inches='tight')
    print(f"Saved: {output_file}")
    plt.close()
    
    return output_file


def plot_month_precip_total_climatology_treatments(
    month,
    year,
    pairs=None,
    climatology_start_year=2013,
    output_file=None,
):
    """
    For each treatment–control pair, a row of three panels (like SWE boxplots):
    calendar-month precipitation total at treatment, at control, and treatment
    minus control. Month total = SNOTEL accumulation on last day minus first day
    of that month. Boxes = prior years (climatology_start_year .. year-1); red
    markers = report year (excluded from boxes).
    """
    if pairs is None:
        pairs = [
            ("La sal upper", "Buckboard Flat"),
            ("Lasal Mtn lower", "Camp jackson"),
        ]

    month_name = calendar.month_name[month]

    def style_boxplot(bp):
        for box in bp["boxes"]:
            box.set_facecolor("#c6dbef")
            box.set_edgecolor("#1f77b4")
            box.set_linewidth(1.2)
        for whisker in bp["whiskers"]:
            whisker.set_color("#1f77b4")
            whisker.set_linewidth(1)
        for cap in bp["caps"]:
            cap.set_color("#1f77b4")
            cap.set_linewidth(1)
        for median in bp["medians"]:
            median.set_color("#1f77b4")
            median.set_linewidth(1.5)
        for flier in bp["fliers"]:
            flier.set_marker("o")
            flier.set_markerfacecolor("none")
            flier.set_markeredgecolor("#1f77b4")
            flier.set_markersize(3)
            flier.set_alpha(0.9)

    # Load each station once
    station_ctx = {}

    def ensure_ctx(station):
        if station in station_ctx:
            return station_ctx[station]
        loaded = load_station_data(station)
        if loaded is None:
            station_ctx[station] = None
            return None
        df, date_col = loaded
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df[df[date_col].notna()].copy()
        pc = _find_precip_accum_column(df)
        if pc is None:
            station_ctx[station] = None
            return None
        station_ctx[station] = (df, date_col, pc)
        return station_ctx[station]

    def total_for(station, y):
        ctx = ensure_ctx(station)
        if ctx is None:
            return None
        df, date_col, pc = ctx
        return _month_precip_total(df, date_col, pc, y, month)

    n_rows = len(pairs)
    fig, axes = plt.subplots(n_rows, 3, figsize=(8.8, 3.0 * n_rows), squeeze=False)

    clim_years = [y for y in range(climatology_start_year, year) if y < year]
    box_label = month_name  # x-axis tick: calendar month only (e.g. April)

    for row, (treat, ctrl) in enumerate(pairs):
        ax_t = axes[row, 0]
        ax_c = axes[row, 1]
        ax_d = axes[row, 2]

        t_clim, c_clim, d_clim = [], [], []
        for y in clim_years:
            t = total_for(treat, y)
            c = total_for(ctrl, y)
            if t is not None and c is not None:
                t_clim.append(t)
                c_clim.append(c)
                d_clim.append(t - c)

        t_rep = total_for(treat, year)
        c_rep = total_for(ctrl, year)
        d_rep = None
        if t_rep is not None and c_rep is not None:
            d_rep = t_rep - c_rep

        lab_t = STATION_DISPLAY_NAMES.get(treat, treat)
        lab_c = STATION_DISPLAY_NAMES.get(ctrl, ctrl)

        if len(t_clim) == 0:
            for ax in (ax_t, ax_c, ax_d):
                ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
            continue

        for ax, vals, hi, title in (
            (ax_t, t_clim, t_rep, lab_t),
            (ax_c, c_clim, c_rep, lab_c),
            (ax_d, d_clim, d_rep, "TREATMENT − CONTROL"),
        ):
            bp = ax.boxplot(
                [vals],
                positions=[1],
                widths=0.45,
                labels=[box_label],
                showfliers=True,
                patch_artist=True,
            )
            style_boxplot(bp)
            if hi is not None and np.isfinite(hi):
                ax.scatter(
                    [1],
                    [hi],
                    s=42,
                    color="red",
                    edgecolors="black",
                    linewidths=1.1,
                    zorder=25,
                    marker="o",
                )
            ax.set_title(title, fontsize=10, fontweight="bold")
            ax.tick_params(axis="both", labelsize=8)

        ax_t.set_ylabel("Accum precip (in)", fontsize=9)
        ax_c.set_ylabel("Accum precip (in)", fontsize=9)
        ax_d.set_ylabel("Difference (in)", fontsize=9)
        ax_d.axhline(0.0, color="black", linestyle="--", linewidth=1, alpha=0.5)

        # Shared y-scale for treatment and control in this row
        tc = np.array(t_clim + c_clim + ([t_rep, c_rep] if t_rep is not None and c_rep is not None else []), dtype=float)
        tc = tc[np.isfinite(tc)]
        if tc.size:
            pad = 0.08 * max(float(np.nanmax(tc) - np.nanmin(tc)), 0.05)
            y0 = max(0.0, float(np.nanmin(tc)) - pad)
            y1 = float(np.nanmax(tc)) + pad
            ax_t.set_ylim(y0, y1)
            ax_c.set_ylim(y0, y1)

        dd = np.array(d_clim + ([d_rep] if d_rep is not None else []), dtype=float)
        dd = dd[np.isfinite(dd)]
        if dd.size:
            d_pad = 0.1 * max(float(np.nanmax(dd) - np.nanmin(dd)), 0.05)
            ax_d.set_ylim(float(np.nanmin(dd)) - d_pad, float(np.nanmax(dd)) + d_pad)

    fig.suptitle(
        f"{month_name} precipitation total (SNOTEL) — treatment, control, and difference vs prior years",
        fontsize=10,
        y=1.01,
    )
    try:
        plt.tight_layout(rect=[0, 0, 1, 0.96])
    except Exception:
        plt.subplots_adjust(hspace=0.4, wspace=0.3, top=0.92)

    if output_file is None:
        output_file = PLOTS_DIR / f"{year}{month:02d}_PrecipMonthTotal_LaSalTreatments.{PLOT_FORMAT}"

    plt.savefig(output_file, dpi=PLOT_DPI, bbox_inches="tight")
    print(f"Saved: {output_file}")
    plt.close()
    return output_file


def _precip_accum_daily_series(df, date_col, prec_col):
    """Normalized-date index -> numeric accumulation (in)."""
    d = df[[date_col, prec_col]].copy()
    d[date_col] = pd.to_datetime(d[date_col], errors="coerce")
    d = d[d[date_col].notna()]
    d[prec_col] = pd.to_numeric(d[prec_col], errors="coerce")
    d = d.drop_duplicates(subset=[date_col], keep="first")
    d["_d"] = d[date_col].dt.normalize()
    return d.set_index("_d")[prec_col]


def plot_precip_accum_timeseries_vs_climatology(
    month,
    year,
    pairs=None,
    climatology_start_year=2013,
    output_file=None,
):
    """
    Daily **month-to-date** precipitation (in) for the report calendar month,
    anchored to the 1st of the month: each day shows SNOTEL accumulation that
    day minus accumulation on the 1st (same as the boxplot's monthly total when
    evaluated on the last day). Solid = report year; dashed = day-of-month median
    across climatology years. Right column: treatment minus control.
    """
    if pairs is None:
        pairs = [
            ("La sal upper", "Buckboard Flat"),
            ("Lasal Mtn lower", "Camp jackson"),
        ]

    last_day = calendar.monthrange(year, month)[1]
    report_dates = pd.date_range(
        pd.Timestamp(year, month, 1),
        pd.Timestamp(year, month, last_day),
        freq="D",
    )
    clim_years = [y for y in range(climatology_start_year, year) if y < year]

    def load_series(station):
        loaded = load_station_data(station)
        if loaded is None:
            return None
        df, date_col = loaded
        pc = _find_precip_accum_column(df)
        if pc is None:
            return None
        return _precip_accum_daily_series(df, date_col, pc)

    def value_on(ser, y, m, dom):
        ts = pd.Timestamp(y, m, dom)
        if ser is None:
            return np.nan
        return float(ser.get(ts.normalize(), np.nan))

    def anchored_on(ser, y, m, dom):
        """Precip within month through day `dom`: accum(dom) - accum(1st)."""
        v0 = value_on(ser, y, m, 1)
        v1 = value_on(ser, y, m, dom)
        if not (np.isfinite(v0) and np.isfinite(v1)):
            return np.nan
        return float(v1 - v0)

    def median_anchored(ser, m, dom):
        vals = [anchored_on(ser, y, m, dom) for y in clim_years]
        vals = [v for v in vals if np.isfinite(v)]
        if not vals:
            return np.nan
        return float(np.nanmedian(vals))

    n_rows = len(pairs)
    fig, axes = plt.subplots(
        n_rows, 2, figsize=(11.5, 3.4 * n_rows), sharex=True, squeeze=False
    )

    month_name = calendar.month_name[month]
    wy_short = f"{str(year - 1)[-2:]}-{str(year)[-2:]}"
    clim_label = f"Median ({climatology_start_year}–{year - 1})"

    for row, (treat, ctrl) in enumerate(pairs):
        ax_l = axes[row, 0]
        ax_r = axes[row, 1]
        ser_t = load_series(treat)
        ser_c = load_series(ctrl)

        x_num = mdates.date2num(report_dates.to_pydatetime())

        v_t_cur = np.array([anchored_on(ser_t, year, month, d.day) for d in report_dates])
        v_c_cur = np.array([anchored_on(ser_c, year, month, d.day) for d in report_dates])
        v_t_med = np.array([median_anchored(ser_t, month, d.day) for d in report_dates])
        v_c_med = np.array([median_anchored(ser_c, month, d.day) for d in report_dates])

        lab_t = STATION_DISPLAY_NAMES.get(treat, treat)
        lab_c = STATION_DISPLAY_NAMES.get(ctrl, ctrl)

        ax_l.plot(x_num, v_t_cur, "b-", linewidth=1.8, label=f"{lab_t} ({str(year)[-2:]})")
        ax_l.plot(x_num, v_t_med, "b--", linewidth=1.2, label=f"{lab_t} {clim_label}")
        ax_l.plot(x_num, v_c_cur, "r-", linewidth=1.8, label=f"{lab_c} ({str(year)[-2:]})")
        ax_l.plot(x_num, v_c_med, "r--", linewidth=1.2, label=f"{lab_c} {clim_label}")

        ax_l.set_ylabel("Accum precip (in)", fontsize=9)
        ax_l.grid(True, alpha=0.35)
        ax_l.legend(loc="upper left", fontsize=7, framealpha=0.92)
        ax_l.set_title(
            f"Station values — {month_name} {year} vs climatology\n{lab_t} vs {lab_c}",
            fontsize=9,
        )

        d_cur = v_t_cur - v_c_cur
        d_med_list = []
        for d in report_dates:
            diffs = []
            for y in clim_years:
                a = anchored_on(ser_t, y, month, d.day)
                b = anchored_on(ser_c, y, month, d.day)
                if np.isfinite(a) and np.isfinite(b):
                    diffs.append(a - b)
            d_med_list.append(float(np.nanmedian(diffs)) if diffs else np.nan)
        d_med = np.array(d_med_list)

        ax_r.plot(x_num, d_cur, "g-", linewidth=1.8, label=wy_short)
        ax_r.plot(x_num, d_med, "g--", linewidth=1.2, label=clim_label)
        ax_r.axhline(0.0, color="black", linewidth=0.9, linestyle="-", alpha=0.45)
        ax_r.set_ylabel("Δ Accum precip (in)", fontsize=9)
        ax_r.grid(True, alpha=0.35)
        ax_r.legend(loc="upper left", fontsize=7, framealpha=0.92)
        ax_r.set_title(
            f"Difference (treatment − control)\n{lab_t} − {lab_c}",
            fontsize=9,
        )

        for ax in (ax_l, ax_r):
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=5))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right", fontsize=8)
            ax.tick_params(axis="y", labelsize=8)

    axes[-1, 0].set_xlabel("Date", fontsize=9)
    axes[-1, 1].set_xlabel("Date", fontsize=9)

    fig.suptitle(
        f"SNOTEL precipitation in {month_name}, month-to-date from 1st — {year} vs climatology",
        fontsize=11,
        y=1.01,
    )
    try:
        plt.tight_layout(rect=[0, 0, 1, 0.97])
    except Exception:
        plt.subplots_adjust(hspace=0.45, wspace=0.28, top=0.93)

    if output_file is None:
        output_file = (
            PLOTS_DIR / f"{year}{month:02d}_PrecipAccum_DailyVsClimatology.{PLOT_FORMAT}"
        )

    plt.savefig(output_file, dpi=PLOT_DPI, bbox_inches="tight")
    print(f"Saved: {output_file}")
    plt.close()
    return output_file
