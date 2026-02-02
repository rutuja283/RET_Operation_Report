"""
Complete pipeline: Convert PDFs, generate plots, update LaTeX
"""
import sys
from pathlib import Path
# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from pdf_to_csv import convert_all_pdfs
from generate_report import generate_all_plots
from update_latex import update_latex_plots


def run_complete_pipeline(month, year, operations_csv=None):
    """
    Run the complete pipeline:
    1. Convert PDFs to CSV (if needed)
    2. Generate all plots
    3. Update LaTeX file
    
    Args:
        month: Month number (1-12)
        year: Year
        operations_csv: Path to operations schedule CSV
    """
    print("="*60)
    print("RET Operations Report - Complete Pipeline")
    print("="*60)
    
    # Step 1: Convert PDFs to CSV
    print("\nStep 1: Converting PDF station data to CSV...")
    print("(Skipping if CSVs already exist)")
    try:
        convert_all_pdfs()
    except Exception as e:
        print(f"Warning: PDF conversion had issues: {e}")
        print("Continuing with existing CSV files...")
    
    # Step 2: Generate plots
    print("\nStep 2: Generating plots...")
    try:
        generate_all_plots(month, year, operations_csv=operations_csv)
    except Exception as e:
        print(f"Error generating plots: {e}")
        return False
    
    # Step 3: Update LaTeX
    print("\nStep 3: Updating LaTeX file...")
    try:
        update_latex_plots(month, year)
    except Exception as e:
        print(f"Error updating LaTeX: {e}")
        return False
    
    print("\n" + "="*60)
    print("Pipeline complete! Check plots/ directory and main.tex")
    print("="*60)
    
    return True


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python complete_pipeline.py <month> <year> [operations_csv]")
        print("Example: python complete_pipeline.py 12 2025")
        print("Example: python complete_pipeline.py 12 2025 ../data/csv/operations.csv")
        sys.exit(1)
    
    month = int(sys.argv[1])
    year = int(sys.argv[2])
    operations_csv = sys.argv[3] if len(sys.argv) > 3 else None
    
    if not (1 <= month <= 12):
        print("Error: Month must be between 1 and 12")
        sys.exit(1)
    
    success = run_complete_pipeline(month, year, operations_csv=operations_csv)
    sys.exit(0 if success else 1)
