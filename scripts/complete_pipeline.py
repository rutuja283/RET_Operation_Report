"""
Complete pipeline: Convert PDFs, generate plots, update LaTeX.
Run by month/year; optionally supply operations input file to refresh operations table.
"""
import sys
import argparse
from pathlib import Path
# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import CSV_DIR, SNOTEL_STATIONS
from pdf_to_csv import convert_all_pdfs
from generate_report import generate_all_plots
from update_latex import update_latex_plots
from parse_operations_table import _run as run_operations_parser
from fetch_snotel import fetch_snotel_for_report


def run_complete_pipeline(month, year, operations_csv=None, operations_input=None, snowdepth_plot=None, fetch_snotel=True):
    """
    Run the complete pipeline:
    1. If operations_input: parse operations file and write operations_schedule.csv + operations_table.tex
    2. If fetch_snotel: fetch SNOTEL data from USDA for report month (water year through report month) and update CSVs
    3. Convert PDFs to CSV (if needed)
    4. Generate all plots
    5. Update LaTeX file

    Args:
        month: Month number (1-12)
        year: Year
        operations_csv: Path to operations schedule CSV (used if operations_input not set)
        operations_input: Path to raw operations file; if set, parser runs and generated CSV is used
        snowdepth_plot: Specific snow depth plot filename to use in report (if None, auto-selects)
        fetch_snotel: If True, fetch USDA SNOTEL data for configured stations before generating plots
    """
    print("="*60)
    print("RET Operations Report - Complete Pipeline")
    print("="*60)

    if operations_input:
        print("\nStep 0: Parsing operations input and updating operations table...")
        operations_csv = run_operations_parser(operations_input=operations_input, month=month, year=year)

    if fetch_snotel and SNOTEL_STATIONS:
        print("\nStep 1: Fetching SNOTEL data from USDA for report period...")
        for name, ok, msg in fetch_snotel_for_report(month, year):
            if ok:
                print(f"   {name}: {msg}")
            else:
                print(f"   {name}: fetch failed - {msg}")
    else:
        if not fetch_snotel:
            print("\nStep 1: Skipping USDA fetch (--no-fetch-snotel).")

    # Step 2: Convert PDFs to CSV
    print("\nStep 2: Converting PDF station data to CSV...")
    print("(Skipping if CSVs already exist)")
    try:
        convert_all_pdfs()
    except Exception as e:
        print(f"Warning: PDF conversion had issues: {e}")
        print("Continuing with existing CSV files...")

    # Step 3: Generate plots
    print("\nStep 3: Generating plots...")
    try:
        generate_all_plots(month, year, operations_csv=operations_csv)
    except Exception as e:
        print(f"Error generating plots: {e}")
        return False
    
    # Step 4: Update LaTeX
    print("\nStep 4: Updating LaTeX file...")
    try:
        update_latex_plots(month, year, snowdepth_plot=snowdepth_plot)
    except Exception as e:
        print(f"Error updating LaTeX: {e}")
        return False
    
    print("\n" + "="*60)
    print("Pipeline complete! Check plots/ directory and main.tex")
    print("="*60)
    
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="RET Operations Report pipeline: month/year driven; optionally refresh operations from file."
    )
    parser.add_argument("month", type=int, help="Report month (1-12)")
    parser.add_argument("year", type=int, help="Report year")
    parser.add_argument(
        "operations_csv",
        nargs="?",
        default=None,
        help="Path to existing operations schedule CSV (ignored if --operations-input is set)",
    )
    parser.add_argument(
        "snowdepth_plot",
        nargs="?",
        default=None,
        help="Snow depth plot filename to reference in report",
    )
    parser.add_argument(
        "--operations-input",
        "-o",
        metavar="FILE",
        default=None,
        help="Path to raw operations file (date,status per line). Updates operations table for this report month/year.",
    )
    parser.add_argument(
        "--no-fetch-snotel",
        action="store_true",
        help="Do not fetch SNOTEL data from USDA; use existing CSVs only.",
    )
    args = parser.parse_args()

    month, year = args.month, args.year
    if not (1 <= month <= 12):
        print("Error: Month must be between 1 and 12")
        sys.exit(1)

    operations_csv = args.operations_csv
    if operations_csv and operations_csv.endswith(".png"):
        snowdepth_plot = operations_csv
        operations_csv = None
    else:
        snowdepth_plot = args.snowdepth_plot

    success = run_complete_pipeline(
        month,
        year,
        operations_csv=operations_csv,
        operations_input=args.operations_input,
        snowdepth_plot=snowdepth_plot,
        fetch_snotel=not args.no_fetch_snotel,
    )
    sys.exit(0 if success else 1)
