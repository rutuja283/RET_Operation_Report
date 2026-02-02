# Setup Guide: RET Operations Report Automation

## Overview

This automation pipeline generates monthly operations reports with:
- Operations schedule visualization
- Precipitation time series
- Snow depth boxplots (treatment vs control)

## Prerequisites

1. **Python 3.8+**
2. **Java** (for tabula-py PDF extraction)
   - macOS: `brew install openjdk`
   - Linux: `sudo apt-get install default-jre`
   - Windows: Download from Oracle/OpenJDK

## Installation

1. **Clone or download this repository**

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Verify installation:**
   ```bash
   python -c "import pandas, numpy, matplotlib; print('OK')"
   ```

## Data Preparation

### Step 1: Convert PDF Station Data

Place PDF station data files in the root directory (or `data/raw/`):
- `lasal Mtn.pdf`
- `Lasal Mtn lower.pdf`
- `Gold Basin.pdf`
- `Camp jackson.pdf`
- `Buckboard Flat.pdf`
- `Elke Ridge.pdf`

Convert to CSV:
```bash
cd scripts
python pdf_to_csv.py
```

Output CSV files will be in `data/csv/` with standardized names.

### Step 2: Create Operations Schedule CSV

Create `data/csv/operations_schedule.csv` with format:
```csv
Date,Operating
2025-12-01,True
2025-12-02,True
2025-12-03,False
...
```

Use `data/csv/operations_schedule_template.csv` as a template.

## Usage

### Generate Report for December 2025

```bash
cd scripts
python complete_pipeline.py 12 2025
```

Or with custom operations CSV:
```bash
python complete_pipeline.py 12 2025 ../data/csv/operations_schedule.csv
```

### What Gets Generated

1. **Plots** (in `plots/` directory):
   - `202512_OperatingSchedule_Report.png` - Operations schedule with green shading
   - `202512_PrecipSummary_Report_v02.png` - Precipitation time series
   - `202512_SnowDepthSummary_Report.png` - Snow depth boxplots

2. **Updated LaTeX** (`main.tex`):
   - Plot file references updated
   - Dates and month names updated
   - Document name updated

## Station Configuration

Edit `scripts/config.py` to customize:

```python
TREATMENT_STATIONS = [
    "La Sal Mtn",
    "Lasal Mtn lower", 
    "Gold Basin"
]

CONTROL_STATIONS = [
    "Camp jackson",
    "Buckboard Flat",
    "Elke Ridge"
]
```

## SNOTEL Data Handling

SNOTEL precipitation data is cumulative (water year starts Oct 1). The scripts automatically:
- Detect cumulative columns
- Convert to daily increments
- Handle water year resets

## GitHub Integration

### Manual Workflow

1. **Convert PDFs and generate plots locally**
2. **Commit and push:**
   ```bash
   git add plots/*.png main.tex
   git commit -m "Update report for Dec 2025"
   git push
   ```

### Overleaf Sync

1. In Overleaf project, go to **Menu > GitHub**
2. Connect your GitHub repository
3. Pull latest changes or enable auto-sync

## Google Drive Integration

### Option 1: Manual Download
1. Download new PDF files from Drive
2. Place in project directory
3. Run conversion and pipeline

### Option 2: Google Drive API (Future)
A `drive_integration.py` script can be created to:
- Authenticate with Google Drive
- Download new PDF files automatically
- Upload generated plots back to Drive

## Troubleshooting

### PDF Conversion Issues

**Error: "tabula-py not found"**
```bash
pip install tabula-py
# Also ensure Java is installed
```

**Error: "Could not extract data"**
- Try alternative: `pip install pdfplumber`
- Or manually extract tables and save as CSV

### Plot Generation Errors

**"CSV file not found"**
- Check that PDFs were converted successfully
- Verify station names match `config.py` mappings

**"Could not find date column"**
- Ensure CSV has a date column (any name with "date" in it)
- Check date format is parseable (YYYY-MM-DD preferred)

**"No overlapping data"**
- Verify both treatment and control stations have data for the same dates
- Check date ranges in CSV files

### LaTeX Errors

**"Plot file not found"**
- Ensure plots were generated successfully
- Check plot filenames match expected format

## File Structure

```
RET_Operation_Report/
├── data/
│   ├── csv/              # Converted CSV files
│   │   ├── La Sal Mtn.csv
│   │   ├── Camp jackson.csv
│   │   └── operations_schedule.csv
│   └── raw/              # Raw PDF files (optional)
├── scripts/
│   ├── config.py         # Configuration
│   ├── pdf_to_csv.py     # PDF conversion
│   ├── plot_generators.py # Plot functions
│   ├── generate_report.py # Main generator
│   ├── update_latex.py   # LaTeX updater
│   └── complete_pipeline.py # Full pipeline
├── plots/                # Generated plots
├── main.tex              # LaTeX report
├── requirements.txt      # Python dependencies
└── README.md            # Documentation
```

## Next Steps

- [ ] Set up GitHub Actions for CI/CD
- [ ] Implement Google Drive API integration
- [ ] Add data validation checks
- [ ] Create automated email reports
- [ ] Add radiometer plot generation

## Support

For issues or questions:
1. Check `README.md` for detailed documentation
2. Review error messages and troubleshoot section
3. Verify all dependencies are installed
4. Check that CSV files have correct format
