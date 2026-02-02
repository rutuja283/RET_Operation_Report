"""
Convert PDF station data files to CSV format, removing metadata
"""
import pandas as pd
import numpy as np
from pathlib import Path
import sys
import re

# Try to import PDF extraction libraries
try:
    import tabula
    HAS_TABULA = True
except ImportError:
    HAS_TABULA = False

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

import sys
from pathlib import Path
# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from config import BASE_DIR, CSV_DIR, STATION_NAME_MAP


def clean_column_names(df):
    """Clean and standardize column names"""
    # Remove extra whitespace
    df.columns = [str(col).strip() for col in df.columns]
    
    # Remove metadata rows (rows where most values are NaN or text)
    # Keep rows where at least one column has numeric data
    numeric_mask = df.apply(lambda row: pd.to_numeric(row, errors='coerce').notna().any(), axis=1)
    df = df[numeric_mask].copy()
    
    # Try to identify date column
    date_col = None
    for col in df.columns:
        col_lower = str(col).lower()
        if any(term in col_lower for term in ['date', 'time', 'timestamp', 'datetime']):
            date_col = col
            break
    
    # If no date column found, try first column
    if date_col is None and len(df.columns) > 0:
        # Try to parse first column as date
        first_col = df.columns[0]
        try:
            pd.to_datetime(df[first_col].iloc[:10], errors='coerce')
            date_col = first_col
        except:
            pass
    
    return df, date_col


def extract_with_tabula(pdf_path):
    """Extract tables using tabula-py"""
    try:
        # Extract all tables
        tables = tabula.read_pdf(str(pdf_path), pages='all', multiple_tables=True)
        if not tables:
            return None
        
        # Combine all tables
        df = pd.concat(tables, ignore_index=True)
        return df
    except Exception as e:
        print(f"Error with tabula: {e}")
        return None


def extract_with_pdfplumber(pdf_path):
    """Extract tables using pdfplumber"""
    try:
        all_tables = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    if table:
                        df = pd.DataFrame(table[1:], columns=table[0])
                        all_tables.append(df)
        
        if all_tables:
            df = pd.concat(all_tables, ignore_index=True)
            return df
        return None
    except Exception as e:
        print(f"Error with pdfplumber: {e}")
        return None


def convert_pdf_to_csv(pdf_path, output_dir=None):
    """
    Convert PDF to CSV, removing metadata and cleaning data
    
    Args:
        pdf_path: Path to PDF file
        output_dir: Directory to save CSV (default: CSV_DIR)
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        print(f"PDF file not found: {pdf_path}")
        return None
    
    if output_dir is None:
        output_dir = CSV_DIR
    else:
        output_dir = Path(output_dir)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Get station name
    pdf_name = pdf_path.name
    station_name = STATION_NAME_MAP.get(pdf_name, pdf_path.stem)
    output_file = output_dir / f"{station_name}.csv"
    
    print(f"Converting {pdf_name} to CSV...")
    
    # Try extraction methods in order
    df = None
    
    if HAS_TABULA:
        df = extract_with_tabula(pdf_path)
    
    if df is None and HAS_PDFPLUMBER:
        df = extract_with_pdfplumber(pdf_path)
    
    if df is None:
        print(f"Warning: Could not extract data from {pdf_name}. Install tabula-py or pdfplumber.")
        print("  pip install tabula-py pdfplumber")
        return None
    
    # Clean the dataframe
    df, date_col = clean_column_names(df)
    
    if df.empty:
        print(f"Warning: No data extracted from {pdf_name}")
        return None
    
    # Save to CSV
    df.to_csv(output_file, index=False)
    print(f"Saved: {output_file}")
    
    return output_file


def convert_all_pdfs(pdf_dir=None):
    """Convert all PDF files in directory"""
    if pdf_dir is None:
        pdf_dir = BASE_DIR
    
    pdf_dir = Path(pdf_dir)
    pdf_files = list(pdf_dir.glob("*.pdf"))
    
    # Filter out cover page
    pdf_files = [f for f in pdf_files if "cover" not in f.name.lower()]
    
    converted = []
    for pdf_file in pdf_files:
        # Check if it's a station data file (has mapping or matches pattern)
        if pdf_file.name in STATION_NAME_MAP or any(
            station.lower().replace(" ", "") in pdf_file.name.lower() 
            for station in STATION_NAME_MAP.values()
        ):
            result = convert_pdf_to_csv(pdf_file)
            if result:
                converted.append(result)
    
    print(f"\nConverted {len(converted)} PDF files to CSV")
    return converted


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Convert specific file
        pdf_path = Path(sys.argv[1])
        convert_pdf_to_csv(pdf_path)
    else:
        # Convert all PDFs
        convert_all_pdfs()
