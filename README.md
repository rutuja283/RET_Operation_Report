# RET Operations Report Automation

Automated pipeline for generating La Sal Operations Reports with plots and data analysis.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. For PDF to CSV conversion, you may also need Java (for tabula-py):
```bash
# macOS
brew install openjdk

# Linux
sudo apt-get install default-jre
```

## Directory Structure

```
RET_Operation_Report/
├── data/
│   ├── csv/          # Converted CSV files from PDFs
│   └── raw/          # Raw data files
├── scripts/
│   ├── config.py              # Configuration settings
│   ├── pdf_to_csv.py          # Convert PDF station data to CSV
│   ├── plot_generators.py     # Plot generation functions
│   └── generate_report.py     # Main automation script
├── plots/            # Generated plot images
├── output/           # Final report outputs
└── main.tex          # LaTeX report template
```

## Usage

### Step 1: Convert PDF Station Data to CSV

Convert all PDF station data files to CSV format:

```bash
cd scripts
python pdf_to_csv.py
```

Or convert a specific file:
```bash
python pdf_to_csv.py ../path/to/station.pdf
```

### Step 2: Prepare Operations Schedule CSV

Create a CSV file with operations schedule data. The file should have:
- A date column (any name with "date" in it)
- An operating column (boolean: True/False or 1/0)

Example `data/csv/operations_schedule.csv`:
```csv
Date,Operating
2025-12-01,True
2025-12-02,True
2025-12-03,False
...
```

### Step 3: Generate Plots for a Month/Year

Generate all plots for a specific month:

```bash
cd scripts
python generate_report.py 12 2025
```

Or with custom operations CSV:
```bash
python generate_report.py 12 2025 --operations-csv ../data/csv/operations_schedule.csv
```

This will generate:
- Operations schedule plot (green shading for operating periods)
- Precipitation summary plot (with operating periods highlighted)
- Snow depth boxplots (treatment vs control comparisons)

### Step 4: Update LaTeX Report

The generated plots will be saved in the `plots/` directory with naming convention:
- `{YYYY}{MM}_OperatingSchedule_Report.png`
- `{YYYY}{MM}_PrecipSummary_Report_v02.png`
- `{YYYY}{MM}_SnowDepthSummary_Report.png`

Update `main.tex` to reference these plots (or use the update script - see below).

## Station Configuration

Edit `scripts/config.py` to configure:
- Treatment stations (La Sal Mtn, Lasal Mtn lower, Gold Basin)
- Control stations (Camp jackson, Buckboard Flat, Elke Ridge)
- Station name mappings (PDF filename -> standardized name)

## SNOTEL Data Handling

SNOTEL precipitation data is cumulative and resets on October 1st (water year start). The scripts automatically:
- Detect cumulative data
- Convert to daily increments
- Handle water year resets

## GitHub Integration

### Option 1: Manual Upload
1. Convert PDFs to CSV locally
2. Generate plots
3. Commit and push to GitHub
4. Overleaf can sync with GitHub (see Overleaf documentation)

### Option 2: GitHub Actions (Recommended)
Set up a GitHub Action to:
1. Watch for new data files
2. Automatically convert PDFs to CSV
3. Generate plots
4. Update the report

### Option 3: Google Drive Integration
For Google Drive integration, you can:
1. Use Google Drive API to download files
2. Process them locally
3. Upload results back

See `scripts/drive_integration.py` (to be implemented) for Drive API setup.

## Plot Details

### Operations Schedule Plot
- Green shading indicates WETA operating periods
- Shows full month with daily resolution

### Precipitation Summary Plot
- Time series of daily precipitation at all stations
- Green background indicates operating periods
- Handles both weather station and SNOTEL data

### Snow Depth Boxplots
- Three-panel layout: Treatment, Control, Difference
- Monthly climatology with current month highlighted (red dot)
- Shows all treatment-control station pairs

## Troubleshooting

### PDF Conversion Issues
If PDF conversion fails:
1. Install Java (required for tabula-py)
2. Try alternative: `pip install pdfplumber` (pure Python)
3. Manually extract tables and save as CSV

### Missing Data
- Check CSV files in `data/csv/` directory
- Verify station names match config.py
- Ensure date columns are properly formatted

### Plot Generation Errors
- Check that CSV files have proper date columns
- Verify operating schedule CSV format
- Ensure all required columns exist in station data

## Next Steps

- [ ] Set up GitHub Actions for automation
- [ ] Implement Google Drive integration
- [ ] Add radiometer plot generation
- [ ] Create LaTeX auto-update script
- [ ] Add data validation checks
