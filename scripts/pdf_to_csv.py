"""
Convert PDF station data files to CSV format, removing metadata
Handles USDA SNOTEL CSV exports that have been saved as PDFs
"""
import pandas as pd
import numpy as np
from pathlib import Path
import sys
import re
import io

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
    """Extract tables using pdfplumber, handling USDA SNOTEL CSV exports"""
    try:
        all_tables = []
        all_text = []
        
        with pdfplumber.open(pdf_path) as pdf:
            # Extract all text from all pages
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    all_text.append(text)
            
            # Combine all text
            full_text = '\n'.join(all_text)
            lines = full_text.split('\n')
            
            # Find where the actual CSV data starts (skip metadata)
            # Look for common CSV header patterns
            csv_start_idx = None
            for i, line in enumerate(lines):
                line_lower = line.lower().strip()
                # Look for CSV header indicators
                if any(indicator in line_lower for indicator in [
                    'date,', 'date ,', 'date\t',  # Date column
                    'station,', 'station name,',  # Station column
                    'precipitation', 'snow', 'temperature',  # Data columns
                ]):
                    # Check if it looks like a header (has commas or tabs)
                    if ',' in line or '\t' in line:
                        csv_start_idx = i
                        break
            
            # If no clear header found, look for first line with date-like pattern
            if csv_start_idx is None:
                for i, line in enumerate(lines):
                    # Look for date patterns (YYYY-MM-DD, MM/DD/YYYY, etc.)
                    if re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', line):
                        # Check if previous line might be header
                        if i > 0 and (',' in lines[i-1] or '\t' in lines[i-1]):
                            csv_start_idx = i - 1
                        else:
                            csv_start_idx = i
                        break
            
            if csv_start_idx is None:
                print(f"  Could not find CSV data start in {pdf_path.name}")
                return None
            
            # Extract CSV data (skip metadata)
            csv_lines = lines[csv_start_idx:]
            
            # Try to parse as CSV
            import io
            csv_text = '\n'.join(csv_lines)
            
            # Try comma-separated first
            try:
                df = pd.read_csv(io.StringIO(csv_text), on_bad_lines='skip', engine='python')
                if len(df) > 0 and len(df.columns) > 1:
                    return df
            except:
                pass
            
            # Try tab-separated
            try:
                df = pd.read_csv(io.StringIO(csv_text), sep='\t', on_bad_lines='skip', engine='python')
                if len(df) > 0 and len(df.columns) > 1:
                    return df
            except:
                pass
            
            # Fallback: try extracting tables
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    if table and len(table) > 1:
                        try:
                            df = pd.DataFrame(table[1:], columns=table[0])
                            all_tables.append(df)
                        except:
                            continue
            
            if all_tables:
                df = pd.concat(all_tables, ignore_index=True)
                return df
            
            return None
    except Exception as e:
        print(f"Error with pdfplumber: {e}")
        import traceback
        traceback.print_exc()
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
    
    # Try extraction methods in order (prefer pdfplumber - no Java needed)
    df = None
    
    if HAS_PDFPLUMBER:
        df = extract_with_pdfplumber(pdf_path)
        if df is None:
            print(f"  pdfplumber: No tables found in {pdf_name}")
    
    if df is None and HAS_TABULA:
        print(f"  Trying tabula as fallback...")
        df = extract_with_tabula(pdf_path)
    
    if df is None:
        print(f"Warning: Could not extract data from {pdf_name}.")
        print(f"  pdfplumber: {'Available' if HAS_PDFPLUMBER else 'Not installed'}")
        print(f"  tabula-py: {'Available' if HAS_TABULA else 'Not installed'}")
        if not HAS_PDFPLUMBER:
            print("  Install pdfplumber: pip install pdfplumber")
        if HAS_TABULA and not HAS_PDFPLUMBER:
            print("  Note: tabula-py requires Java. Install: brew install openjdk")
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
        # Check raw folder first, then root directory
        raw_dir = BASE_DIR / "data" / "raw"
        if raw_dir.exists() and list(raw_dir.glob("*.pdf")):
            pdf_dir = raw_dir
        else:
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
