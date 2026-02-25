"""
Plot generation functions for RET Operations Report
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
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
    Generate operations schedule plot with green shading for operating periods
    
    Args:
        operations_df: DataFrame with columns 'Date' (datetime) and 'Operating' (bool)
        month: Month number (1-12)
        year: Year
        output_file: Output file path
    """
    # Filter to the specified month
    month_start = datetime(year, month, 1)
    if month == 12:
        month_end = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = datetime(year, month + 1, 1) - timedelta(days=1)
    
    month_df = operations_df[
        (operations_df['Date'] >= month_start) & 
        (operations_df['Date'] <= month_end)
    ].copy()
    
    if month_df.empty:
        print(f"Warning: No operations data for {month}/{year}")
        return None
    
    fig, ax = plt.subplots(figsize=(14, 4))
    
    # Create date range for the month
    dates = pd.date_range(start=month_start, end=month_end, freq='D')
    
    # Create operating status array
    operating = []
    for date in dates:
        day_data = month_df[month_df['Date'].dt.date == date.date()]
        if not day_data.empty:
            # If any part of the day was operating, mark as operating
            operating.append(day_data['Operating'].any() if 'Operating' in day_data.columns else False)
        else:
            operating.append(False)
    
    # Plot green shading for operating periods
    for i, (date, is_operating) in enumerate(zip(dates, operating)):
        if is_operating:
            ax.axvspan(date - timedelta(hours=12), date + timedelta(hours=12), 
                      color='green', alpha=0.3, zorder=0)
    
    # Formatting
    ax.set_xlim(dates[0] - timedelta(days=0.5), dates[-1] + timedelta(days=0.5))
    ax.set_xlabel('Date')
    ax.set_ylabel('Operating Status')
    ax.set_title(f'WETA Operating Schedule - {calendar.month_name[month]} {year}')
    ax.grid(True, alpha=0.3)
    
    # Format x-axis dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(dates)//10)))
    plt.xticks(rotation=45)
    
    plt.tight_layout()
    
    if output_file is None:
        output_file = PLOTS_DIR / f"{year}{month:02d}_OperatingSchedule_Report.{PLOT_FORMAT}"
    
    plt.savefig(output_file, dpi=PLOT_DPI, bbox_inches='tight')
    print(f"Saved: {output_file}")
    plt.close()
    
    return output_file


def plot_precipitation_summary(stations_data, operations_df, month, year, output_file=None):
    """
    Generate precipitation summary plot with operating periods highlighted
    
    Args:
        stations_data: Dict of {station_name: (dates, values)} tuples
        operations_df: DataFrame with operating periods
        month: Month number
        year: Year
        output_file: Output file path
    """
    month_start = datetime(year, month, 1)
    if month == 12:
        month_end = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = datetime(year, month + 1, 1) - timedelta(days=1)
    
    fig, ax = plt.subplots(figsize=(14, 6))
    
    # Plot operating periods as green background
    # Only highlight dates that are explicitly in the operations table
    dates = pd.date_range(start=month_start, end=month_end, freq='D')
    
    if not operations_df.empty and 'Date' in operations_df.columns:
        # Ensure Date is datetime
        operations_df['Date'] = pd.to_datetime(operations_df['Date'], errors='coerce')
        month_ops = operations_df[
            (operations_df['Date'] >= month_start) & 
            (operations_df['Date'] <= month_end)
        ].copy()
        
        # Get unique dates that have WETA operating
        # Only dates explicitly in the operations table should be highlighted
        if not month_ops.empty and pd.api.types.is_datetime64_any_dtype(month_ops['Date']):
            # Get unique dates where Operating is True
            # Filter out any NaN dates first
            month_ops_clean = month_ops[month_ops['Date'].notna()].copy()
            if not month_ops_clean.empty:
                operating_dates = set(month_ops_clean[month_ops_clean['Operating'] == True]['Date'].dt.date.unique())
                
                print(f"   Highlighting {len(operating_dates)} dates: {sorted(operating_dates)}")
                
                for date in dates:
                    # Only highlight if date is explicitly in the operations table and Operating is True
                    if date.date() in operating_dates:
                        ax.axvspan(date - timedelta(hours=12), date + timedelta(hours=12),
                                  color='green', alpha=0.2, zorder=0)
            else:
                print("   Warning: No valid operating dates found in operations data")
        else:
            print("   Warning: Operations data is empty or Date column is not datetime")
    
    # Plot precipitation for each station
    colors = plt.cm.tab10(np.linspace(0, 1, len(stations_data)))
    for (station_name, (station_dates, values)), color in zip(stations_data.items(), colors):
        # Ensure dates is datetime Series
        if not isinstance(station_dates, pd.Series):
            station_dates = pd.Series(station_dates)
        station_dates = pd.to_datetime(station_dates, errors='coerce')
        
        # Filter to month
        mask = (station_dates >= month_start) & (station_dates <= month_end)
        month_dates = station_dates[mask]
        month_values = values[mask] if isinstance(values, pd.Series) else pd.Series(values)[mask]
        
        # Convert from inches to millimeters (1 inch = 25.4 mm)
        month_values_mm = month_values * 25.4
        
        if len(month_dates) > 0:
            ax.plot(month_dates, month_values_mm, marker='o', label=station_name, 
                   color=color, linewidth=2, markersize=4)
    
    ax.set_xlabel('Date')
    ax.set_ylabel('Daily Precipitation (mm)')
    ax.set_title(f'Daily Precipitation Summary - {calendar.month_name[month]} {year}')
    ax.legend(loc='best', ncol=2)
    ax.grid(True, alpha=0.3)
    
    # Format x-axis
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(dates)//10)))
    plt.xticks(rotation=45)
    
    plt.tight_layout()
    
    if output_file is None:
        output_file = PLOTS_DIR / f"{year}{month:02d}_PrecipSummary_Report_v02.{PLOT_FORMAT}"
    
    plt.savefig(output_file, dpi=PLOT_DPI, bbox_inches='tight')
    print(f"Saved: {output_file}")
    plt.close()
    
    return output_file


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
    
    # Only show the month of interest
    month_name = calendar.month_name[highlight_month] if highlight_month else calendar.month_name[month]
    target_month = highlight_month if highlight_month else month
    
    treatment_groups = []
    control_groups = []
    diff_groups = []
    labels = []
    
    highlight_idx = None
    highlight_vals = None
    highlight_label = None
    
    # Only process the target month
    t_data = treatment_df[treatment_df['month'] == target_month]['Value'].dropna().values
    c_data = control_df[control_df['month'] == target_month]['Value'].dropna().values
    
    if len(t_data) > 0 and len(c_data) > 0:
        # Merge on date to calculate differences
        t_month = treatment_df[treatment_df['month'] == target_month].set_index('Date')['Value']
        c_month = control_df[control_df['month'] == target_month].set_index('Date')['Value']
        
        merged = pd.DataFrame({'Treatment': t_month, 'Control': c_month})
        merged = merged.dropna()
        merged['Diff'] = merged['Treatment'] - merged['Control']
        
        if len(merged) > 0:
            treatment_groups.append(t_data)
            control_groups.append(c_data)
            diff_groups.append(merged['Diff'].values)
            labels.append(month_name)
            
            # Set highlight for current month/year
            if highlight_year:
                highlight_idx = 1  # Only one box, so index is 1
                highlight_vals = {
                    't': float(merged['Treatment'].mean()),
                    'c': float(merged['Control'].mean()),
                    'd': float(merged['Diff'].mean())
                }
                highlight_label = None  # Remove label
    
    if not labels:
        print("Warning: No overlapping data found")
        return None
    
    # Create three-panel plot
    fig = plt.figure(figsize=(12, 7))
    gs = fig.add_gridspec(2, 2, height_ratios=[1, 1.2], hspace=0.45, wspace=0.25)
    
    ax1 = fig.add_subplot(gs[0, 0])  # Treatment
    ax2 = fig.add_subplot(gs[0, 1])  # Control
    ax3 = fig.add_subplot(gs[1, :])  # Difference (spans both columns)
    
    # Create boxplots (labels match February report: SWE / snow water content)
    bp1 = ax1.boxplot(treatment_groups, labels=labels, showfliers=True)
    ax1.set_title(f"{var_short}: {treatment_station} (TREATMENT)")
    ax1.set_ylabel(var_label)
    ax1.tick_params(axis="x", rotation=45)
    ax1.grid(axis="y", alpha=0.35)
    
    bp2 = ax2.boxplot(control_groups, labels=labels, showfliers=True)
    ax2.set_title(f"{var_short}: {control_station} (CONTROL)")
    ax2.tick_params(axis="x", rotation=45)
    ax2.grid(axis="y", alpha=0.35)
    
    bp3 = ax3.boxplot(diff_groups, labels=labels, showfliers=True)
    ax3.set_title(f"{var_short}: TREATMENT - CONTROL")
    ax3.set_ylabel("Difference (in)")
    ax3.tick_params(axis="x", rotation=45)
    ax3.grid(axis="y", alpha=0.35)
    ax3.axhline(y=0, color='black', linestyle='--', linewidth=1, alpha=0.5)
    
    # Add highlight marker if specified (smaller dot, no label)
    if highlight_idx is not None and highlight_vals is not None:
        def annotate_dot(ax, x, y):
            if x is not None and y is not None and np.isfinite(y):
                # Smaller dot: s=40 instead of 80, thinner edge
                ax.scatter([x], [y], s=40, color="red", edgecolors="black", 
                          linewidths=1, zorder=20, marker='o')
        
        annotate_dot(ax1, highlight_idx, highlight_vals['t'])
        annotate_dot(ax2, highlight_idx, highlight_vals['c'])
        annotate_dot(ax3, highlight_idx, highlight_vals['d'])
    
    # Set dynamic y-limits for each panel based on their own data
    # Treatment panel (ax1) - snow depth can't be negative, so start at 0
    if treatment_groups and len(treatment_groups[0]) > 0:
        t_values = treatment_groups[0]
        if highlight_vals and highlight_vals['t'] is not None:
            t_values = np.append(t_values, highlight_vals['t'])
        t_min = max(0, np.nanmin(t_values))  # Ensure non-negative
        t_max = np.nanmax(t_values)
        t_range = t_max - t_min
        t_padding = max(0.1 * t_range, 0.05 * t_max) if t_range > 0 else 0.05 * t_max if t_max > 0 else 1
        ax1.set_ylim(max(0, t_min - t_padding), t_max + t_padding)
    
    # Control panel (ax2) - snow depth can't be negative, so start at 0
    if control_groups and len(control_groups[0]) > 0:
        c_values = control_groups[0]
        if highlight_vals and highlight_vals['c'] is not None:
            c_values = np.append(c_values, highlight_vals['c'])
        c_min = max(0, np.nanmin(c_values))  # Ensure non-negative
        c_max = np.nanmax(c_values)
        c_range = c_max - c_min
        c_padding = max(0.1 * c_range, 0.05 * c_max) if c_range > 0 else 0.05 * c_max if c_max > 0 else 1
        ax2.set_ylim(max(0, c_min - c_padding), c_max + c_padding)
    
    # Difference panel (ax3) - can be negative, so use full range
    if diff_groups and len(diff_groups[0]) > 0:
        d_values = diff_groups[0]
        if highlight_vals and highlight_vals['d'] is not None:
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
