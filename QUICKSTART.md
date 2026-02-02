# Quick Start Guide

## Initial Setup

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Convert PDF station data to CSV:**
```bash
cd scripts
python pdf_to_csv.py
```

This will convert all PDF station files (La Sal Mtn, Camp Jackson, etc.) to CSV format in `data/csv/`.

## Generate Report for a Month

### Option 1: Complete Pipeline (Recommended)
```bash
cd scripts
python complete_pipeline.py 12 2025
```

This will:
- Convert any new PDFs to CSV
- Generate all plots
- Update main.tex with new plot references

### Option 2: Step by Step

1. **Prepare operations schedule CSV:**
   Create `data/csv/operations_schedule.csv` with columns:
   ```csv
   Date,Operating
   2025-12-01,True
   2025-12-02,True
   2025-12-03,False
   ...
   ```

2. **Generate plots:**
   ```bash
   cd scripts
   python generate_report.py 12 2025 --operations-csv ../data/csv/operations_schedule.csv
   ```

3. **Update LaTeX:**
   ```bash
   python update_latex.py 12 2025
   ```

## Output Files

Generated plots will be in `plots/` directory:
- `202512_OperatingSchedule_Report.png`
- `202512_PrecipSummary_Report_v02.png`
- `202512_SnowDepthSummary_Report.png`

The `main.tex` file will be automatically updated with these plot references.

## Google Drive Integration

For manual upload to Google Drive:
1. Upload new PDF station data files to Drive
2. Download to local `data/raw/` directory
3. Run `pdf_to_csv.py` to convert
4. Run the pipeline

For automated Drive integration, see `scripts/drive_integration.py` (to be implemented).

## GitHub + Overleaf Integration

1. **Push to GitHub:**
   ```bash
   git add .
   git commit -m "Update report for Dec 2025"
   git push
   ```

2. **Sync with Overleaf:**
   - In Overleaf, go to Menu > GitHub
   - Connect your repository
   - Overleaf will sync automatically or you can pull manually

## Troubleshooting

- **PDF conversion fails:** Install Java and ensure tabula-py works, or use pdfplumber
- **Missing plots:** Check that CSV files exist and have proper date columns
- **LaTeX errors:** Ensure all plot files exist in `plots/` directory
