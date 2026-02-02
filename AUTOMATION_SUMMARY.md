# Automation Pipeline Summary

## What Was Created

### 1. Directory Structure
```
RET_Operation_Report/
├── data/
│   ├── csv/          # Converted CSV files
│   └── raw/          # Raw data (optional)
├── scripts/          # Automation scripts
├── plots/            # Generated plots
└── output/           # Final outputs
```

### 2. Core Scripts

#### `scripts/config.py`
- Station mappings (treatment vs control)
- Path configurations
- Plot settings

#### `scripts/pdf_to_csv.py`
- Converts PDF station data to CSV
- Removes metadata
- Handles multiple PDF extraction methods (tabula-py, pdfplumber)

#### `scripts/plot_generators.py`
- `plot_operations_schedule()` - Operations schedule with green shading
- `plot_precipitation_summary()` - Precipitation time series
- `plot_snow_depth_boxplots()` - Three-panel boxplots (Treatment/Control/Difference)

#### `scripts/generate_report.py`
- Main script to generate all plots for a month/year
- Handles SNOTEL cumulative data conversion
- Supports custom station selections

#### `scripts/update_latex.py`
- Updates main.tex with new plot references
- Updates dates, captions, document names

#### `scripts/complete_pipeline.py`
- End-to-end automation:
  1. Convert PDFs to CSV
  2. Generate all plots
  3. Update LaTeX file

### 3. Documentation
- `README.md` - Full documentation
- `QUICKSTART.md` - Quick start guide
- `SETUP_GUIDE.md` - Detailed setup instructions

### 4. Configuration Files
- `requirements.txt` - Python dependencies
- `.gitignore` - Git ignore rules
- `data/csv/operations_schedule_template.csv` - Template for operations data

## Key Features

### Automated Plot Generation
- **Operations Schedule**: Green shading for operating periods
- **Precipitation Summary**: Time series with operating periods highlighted
- **Snow Depth Boxplots**: Treatment vs control comparisons with current month highlighted

### SNOTEL Data Handling
- Automatically detects cumulative data
- Converts to daily increments
- Handles water year resets (October 1st)

### LaTeX Integration
- Automatically updates plot file references
- Updates dates and captions
- Updates document metadata

## Usage Example

```bash
# Generate report for December 2025
cd scripts
python complete_pipeline.py 12 2025
```

This will:
1. Convert any new PDFs to CSV
2. Generate all plots
3. Update main.tex

## Station Configuration

Treatment stations (from config.py):
- La Sal Mtn
- Lasal Mtn lower
- Gold Basin

Control stations:
- Camp jackson
- Buckboard Flat
- Elke Ridge

## Plot Outputs

For month=12, year=2025:
- `202512_OperatingSchedule_Report.png`
- `202512_PrecipSummary_Report_v02.png`
- `202512_SnowDepthSummary_Report.png`

## GitHub + Overleaf Integration

### Manual Workflow
1. Generate plots locally
2. Commit and push to GitHub
3. Pull in Overleaf (Menu > GitHub)

### Automated (Future)
- GitHub Actions can be set up to:
  - Watch for new data
  - Generate plots automatically
  - Update LaTeX
  - Create pull requests

## Google Drive Integration

### Current: Manual Upload
1. Download PDFs from Drive
2. Place in project directory
3. Run pipeline

### Future: API Integration
- Google Drive API script can:
  - Download new PDFs automatically
  - Upload generated plots
  - Sync with GitHub

## Next Steps

1. **Convert existing PDFs:**
   ```bash
   cd scripts
   python pdf_to_csv.py
   ```

2. **Create operations schedule CSV:**
   - Use template: `data/csv/operations_schedule_template.csv`
   - Fill in dates and operating status

3. **Generate first report:**
   ```bash
   python complete_pipeline.py 12 2025
   ```

4. **Review generated plots** in `plots/` directory

5. **Compile LaTeX** in Overleaf or locally

## Notes

- Radiometer plots are skipped in automation (as requested)
- Snow depth boxplots generate for all treatment-control pairs
- Current month/year is automatically highlighted in boxplots
- Operations schedule shows full month with daily resolution
- Precipitation plot includes all stations with operating periods highlighted
