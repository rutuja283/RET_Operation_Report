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
    if not operations_df.empty and 'Date' in operations_df.columns:
        # Ensure Date is datetime
        operations_df['Date'] = pd.to_datetime(operations_df['Date'], errors='coerce')
        month_ops = operations_df[
            (operations_df['Date'] >= month_start) & 
            (operations_df['Date'] <= month_end)
        ]
        dates = pd.date_range(start=month_start, end=month_end, freq='D')
        
        for date in dates:
            if not month_ops.empty and pd.api.types.is_datetime64_any_dtype(month_ops['Date']):
                day_ops = month_ops[month_ops['Date'].dt.date == date.date()]
                if not day_ops.empty and day_ops['Operating'].any():
                    ax.axvspan(date - timedelta(hours=12), date + timedelta(hours=12),
                              color='green', alpha=0.2, zorder=0)
    else:
        dates = pd.date_range(start=month_start, end=month_end, freq='D')
    
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
        
        if len(month_dates) > 0:
            ax.plot(month_dates, month_values, marker='o', label=station_name, 
                   color=color, linewidth=2, markersize=4)
    
    ax.set_xlabel('Date')
    ax.set_ylabel('Daily Precipitation (in)')
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


def plot_snow_depth_boxplots(treatment_station, control_station, month, year, 
                             highlight_month=None, highlight_year=None, output_file=None):
    """
    Generate three-panel boxplot: Treatment, Control, and Difference
    Shows only the specified month (not all months)
    
    Args:
        treatment_station: Name of treatment station
        control_station: Name of control station
        month: Month number for the report (1-12)
        year: Year for the report
        highlight_month: Month to highlight (defaults to month)
        highlight_year: Year to highlight (defaults to year)
        output_file: Output file path (if None, auto-generates with station names)
    """
    """
    Generate three-panel boxplot: Treatment, Control, and Difference
    
    Args:
        treatment_station: Name of treatment station
        control_station: Name of control station
        month: Month number for highlighting (1-12)
        year: Year for highlighting
        output_file: Output file path
    """
    # Load data
    treatment_df, date_col_t = load_station_data(treatment_station)
    control_df, date_col_c = load_station_data(control_station)
    
    if treatment_df is None or control_df is None:
        print(f"Warning: Could not load data for {treatment_station} or {control_station}")
        return None
    
    # Find snow depth column (usually contains "snow" or "depth")
    snow_col_t = None
    snow_col_c = None
    
    for col in treatment_df.columns:
        if 'snow' in str(col).lower() and 'depth' in str(col).lower():
            snow_col_t = col
            break
    
    for col in control_df.columns:
        if 'snow' in str(col).lower() and 'depth' in str(col).lower():
            snow_col_c = col
            break
    
    if snow_col_t is None or snow_col_c is None:
        print(f"Warning: Could not find snow depth column")
        return None
    
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
    
    # Create boxplots
    bp1 = ax1.boxplot(treatment_groups, labels=labels, showfliers=True)
    ax1.set_title(f"Snow Depth: {treatment_station} (TREATMENT)")
    ax1.set_ylabel("Snow Depth (in)")
    ax1.tick_params(axis="x", rotation=45)
    ax1.grid(axis="y", alpha=0.35)
    
    bp2 = ax2.boxplot(control_groups, labels=labels, showfliers=True)
    ax2.set_title(f"Snow Depth: {control_station} (CONTROL)")
    ax2.tick_params(axis="x", rotation=45)
    ax2.grid(axis="y", alpha=0.35)
    
    bp3 = ax3.boxplot(diff_groups, labels=labels, showfliers=True)
    ax3.set_title(f"Snow Depth: TREATMENT - CONTROL")
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
    
    # Set consistent y-limits
    all_values = []
    for groups in [treatment_groups, control_groups, diff_groups]:
        for group in groups:
            all_values.extend(group)
    
    if highlight_vals:
        all_values.extend([highlight_vals['t'], highlight_vals['c'], highlight_vals['d']])
    
    if all_values:
        y_min = np.nanmin(all_values)
        y_max = np.nanmax(all_values)
        y_range = y_max - y_min
        padding = max(0.1 * y_range, 0.05 * (abs(y_min) + abs(y_max)))
        
        y_min_final = max(0, y_min - padding) if y_min >= 0 else y_min - padding
        y_max_final = y_max + padding
        
        ax1.set_ylim(y_min_final, y_max_final)
        ax2.set_ylim(y_min_final, y_max_final)
        ax3.set_ylim(y_min_final, y_max_final)
    
    try:
        plt.tight_layout()
    except:
        # If tight_layout fails, just adjust manually
        plt.subplots_adjust(bottom=0.18, top=0.92, hspace=0.45, wspace=0.25)
    
    if output_file is None:
        # Include station names in filename for multiple combinations
        treatment_clean = treatment_station.replace(" ", "_").replace("/", "_")
        control_clean = control_station.replace(" ", "_").replace("/", "_")
        output_file = PLOTS_DIR / f"{year}{month:02d}_SnowDepth_{treatment_clean}_vs_{control_clean}.{PLOT_FORMAT}"
    
    plt.savefig(output_file, dpi=PLOT_DPI, bbox_inches='tight')
    print(f"Saved: {output_file}")
    plt.close()
    
    return output_file
