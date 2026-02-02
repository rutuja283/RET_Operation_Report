"""
Main script to generate all plots for a given month/year report
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import sys
import argparse

import sys
from pathlib import Path
# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from config import (
    CSV_DIR, PLOTS_DIR, TREATMENT_STATIONS, CONTROL_STATIONS,
    STATION_NAME_MAP
)
from plot_generators import (
    plot_operations_schedule, plot_precipitation_summary, 
    plot_snow_depth_boxplots, load_station_data, handle_snotel_cumulative
)


def load_operations_data(operations_csv=None):
    """
    Load operations schedule data
    
    Expected CSV format:
    Date, Operating (or similar boolean column)
    """
    if operations_csv is None:
        # Look for operations CSV in data directory
        ops_files = list(CSV_DIR.glob("*operation*.csv")) + list(CSV_DIR.glob("*schedule*.csv"))
        if ops_files:
            operations_csv = ops_files[0]
        else:
            print("Warning: No operations schedule CSV found. Creating empty DataFrame.")
            return pd.DataFrame(columns=['Date', 'Operating'])
    
    operations_csv = Path(operations_csv)
    if not operations_csv.exists():
        print(f"Warning: Operations file not found: {operations_csv}")
        return pd.DataFrame(columns=['Date', 'Operating'])
    
    df = pd.read_csv(operations_csv)
    
    # Find date column
    date_col = None
    for col in df.columns:
        if 'date' in str(col).lower():
            date_col = col
            break
    
    if date_col is None:
        print("Warning: Could not find date column in operations file")
        return pd.DataFrame(columns=['Date', 'Operating'])
    
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.rename(columns={date_col: 'Date'})
    
    # Find operating column
    op_col = None
    for col in df.columns:
        if 'operat' in str(col).lower() or 'active' in str(col).lower():
            op_col = col
            break
    
    if op_col:
        df['Operating'] = df[op_col].astype(bool)
    else:
        # Assume all dates are operating if column not found
        df['Operating'] = True
    
    return df[['Date', 'Operating']]


def generate_all_plots(month, year, operations_csv=None, 
                      treatment_stations=None, control_stations=None):
    """
    Generate all plots for a given month/year
    
    Args:
        month: Month number (1-12)
        year: Year
        operations_csv: Path to operations schedule CSV
        treatment_stations: List of treatment station names (default: from config)
        control_stations: List of control station names (default: from config)
    """
    if treatment_stations is None:
        treatment_stations = TREATMENT_STATIONS
    if control_stations is None:
        control_stations = CONTROL_STATIONS
    
    print(f"\n{'='*60}")
    print(f"Generating plots for {month}/{year}")
    print(f"{'='*60}\n")
    
    # Load operations data
    operations_df = load_operations_data(operations_csv)
    
    # 1. Generate operations schedule plot
    print("1. Generating operations schedule plot...")
    try:
        plot_operations_schedule(operations_df, month, year)
    except Exception as e:
        print(f"   Error: {e}")
    
    # 2. Generate precipitation summary
    print("\n2. Generating precipitation summary plot...")
    try:
        stations_data = {}
        
        # Load all station data
        all_stations = treatment_stations + control_stations
        for station_name in all_stations:
            result = load_station_data(station_name)
            if result is not None:
                df, date_col = result
                
                # Find precipitation column
                precip_col = None
                for col in df.columns:
                    col_lower = str(col).lower()
                    if 'precip' in col_lower or 'prcp' in col_lower:
                        precip_col = col
                        break
                
                if precip_col:
                    # Check if cumulative (SNOTEL)
                    is_cumulative = 'snotel' in station_name.lower() or 'accum' in str(precip_col).lower()
                    
                    if is_cumulative:
                        dates, values = handle_snotel_cumulative(df, date_col, precip_col)
                    else:
                        dates = pd.to_datetime(df[date_col])
                        values = pd.to_numeric(df[precip_col], errors='coerce')
                    
                    stations_data[station_name] = (dates, values)
        
        if stations_data:
            plot_precipitation_summary(stations_data, operations_df, month, year)
        else:
            print("   Warning: No precipitation data found")
    except Exception as e:
        print(f"   Error: {e}")
    
    # 3. Generate snow depth boxplots for ALL treatment-control combinations
    print("\n3. Generating snow depth boxplots for all combinations...")
    try:
        plot_count = 0
        for treatment in treatment_stations:
            for control in control_stations:
                print(f"   {treatment} vs {control}...")
                try:
                    result = plot_snow_depth_boxplots(
                        treatment, control, month, year,
                        highlight_month=month, highlight_year=year
                    )
                    if result:
                        plot_count += 1
                except Exception as e:
                    print(f"      Error: {e}")
        print(f"   Generated {plot_count} boxplot combinations")
    except Exception as e:
        print(f"   Error: {e}")
    
    print(f"\n{'='*60}")
    print("Plot generation complete!")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description='Generate RET Operations Report plots for a given month/year'
    )
    parser.add_argument('month', type=int, help='Month number (1-12)')
    parser.add_argument('year', type=int, help='Year (e.g., 2025)')
    parser.add_argument('--operations-csv', type=str, 
                       help='Path to operations schedule CSV file')
    parser.add_argument('--treatment', nargs='+', 
                       help='Treatment station names (overrides config)')
    parser.add_argument('--control', nargs='+',
                       help='Control station names (overrides config)')
    
    args = parser.parse_args()
    
    if not (1 <= args.month <= 12):
        print("Error: Month must be between 1 and 12")
        sys.exit(1)
    
    generate_all_plots(
        args.month, args.year,
        operations_csv=args.operations_csv,
        treatment_stations=args.treatment,
        control_stations=args.control
    )


if __name__ == "__main__":
    if len(sys.argv) == 1:
        # Interactive mode - ask for month/year
        print("RET Operations Report Plot Generator")
        print("=" * 60)
        try:
            month = int(input("Enter month (1-12): "))
            year = int(input("Enter year (e.g., 2025): "))
            
            if not (1 <= month <= 12):
                print("Error: Month must be between 1 and 12")
                sys.exit(1)
            
            ops_csv = input("Enter path to operations CSV (or press Enter to auto-detect): ").strip()
            if not ops_csv:
                ops_csv = None
            
            generate_all_plots(month, year, operations_csv=ops_csv)
        except KeyboardInterrupt:
            print("\nCancelled.")
            sys.exit(0)
        except ValueError:
            print("Error: Invalid input")
            sys.exit(1)
    else:
        main()
