"""
Update main.tex with new plot references for a given month/year
"""
import re
from pathlib import Path
from datetime import datetime
import calendar

import sys
from pathlib import Path
# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from config import BASE_DIR, PLOTS_DIR


def update_latex_plots(month, year, main_tex_path=None):
    """
    Update main.tex with new plot file references
    
    Args:
        month: Month number (1-12)
        year: Year
        main_tex_path: Path to main.tex (default: BASE_DIR/main.tex)
    """
    if main_tex_path is None:
        main_tex_path = BASE_DIR / "main.tex"
    
    main_tex_path = Path(main_tex_path)
    if not main_tex_path.exists():
        print(f"Error: main.tex not found at {main_tex_path}")
        return False
    
    # Read current content
    with open(main_tex_path, 'r') as f:
        content = f.read()
    
    month_name = calendar.month_name[month]
    month_abbr = calendar.month_abbr[month]
    
    # Generate plot filenames
    plot_files = {
        'operations': f"{year}{month:02d}_OperatingSchedule_Report.png",
        'precipitation': f"{year}{month:02d}_PrecipSummary_Report_v02.png",
        'snowdepth': f"{year}{month:02d}_SnowDepthSummary_Report.png"
    }
    
    # Check if plots exist
    for plot_type, filename in plot_files.items():
        plot_path = PLOTS_DIR / filename
        if not plot_path.exists():
            print(f"Warning: Plot not found: {plot_path}")
    
    # Update operations schedule plot
    ops_pattern = r'\\includegraphics\[width=0\.85\\textwidth\]\{[^}]+\}'
    ops_replacement = r'\includegraphics[width=0.85\textwidth]{' + plot_files["operations"] + '}'
    content = re.sub(ops_pattern, ops_replacement, content, count=1)
    
    # Update caption for operations schedule
    ops_caption_pattern = r'\\caption\{WETA operating schedule during [^}]+\}'
    ops_caption_replacement = (r'\caption{WETA operating schedule during ' + 
                              f'{month_name} {year}. Green shading indicates periods of operation.}}')
    content = re.sub(ops_caption_pattern, ops_caption_replacement, content, count=1)
    
    # Update precipitation plot
    precip_pattern = r'\\includegraphics\[width=0\.85\\textwidth\]\{[^}]+\}'
    # Find the second occurrence (precipitation plot)
    matches = list(re.finditer(precip_pattern, content))
    if len(matches) >= 2:
        start, end = matches[1].span()
        precip_replacement = r'\includegraphics[width=0.85\textwidth]{' + plot_files["precipitation"] + '}'
        content = content[:start] + precip_replacement + content[end:]
    
    # Update precipitation caption
    precip_caption_pattern = r'\\caption\{Summary of daily accumulated precipitation[^}]+\}'
    precip_caption_replacement = r'\caption{Summary of daily accumulated precipitation at reporting weather and SNOTEL stations.}'
    content = re.sub(precip_caption_pattern, precip_caption_replacement, content, count=1)
    
    # Update snow depth plot
    snow_pattern = r'\\includegraphics\[width=0\.95\\textwidth\]\{[^}]+\}'
    snow_matches = list(re.finditer(snow_pattern, content))
    if snow_matches:
        start, end = snow_matches[0].span()
        snow_replacement = r'\includegraphics[width=0.95\textwidth]{' + plot_files["snowdepth"] + '}'
        content = content[:start] + snow_replacement + content[end:]
    
    # Update snow depth caption
    snow_caption_pattern = r'\\caption\{Box and whisker plots demonstrating SNOTEL-measured climatological [^}]+\}'
    snow_caption_replacement = (r'\caption{Box and whisker plots demonstrating SNOTEL-measured climatological ' + 
                               f'{month_name} snow depth at (top left) La Sal Mountain, and (top right) Camp Jackson. ' +
                               f'The difference in monthly precipitation is shown in the bottom panel. ' +
                               f'The red circle in each panel indicates values for {month_name} {year}.}}')
    content = re.sub(snow_caption_pattern, snow_caption_replacement, content, count=1)
    
    # Update Executive Summary dates
    date_pattern = r'This report covers \d+ days from \d+/\d+/\d+ to \d+/\d+/\d+\.'
    from calendar import monthrange
    num_days = monthrange(year, month)[1]
    start_date = f"{month:02d}/01/{year}"
    end_date = f"{month:02d}/{num_days}/{year}"
    date_replacement = f'This report covers {num_days} days from {start_date} to {end_date}.'
    content = re.sub(date_pattern, date_replacement, content, count=1)
    
    # Update focus month in Executive Summary
    focus_pattern = r'the focus of this report is on the \w+ \d+ operating period\.'
    focus_replacement = f'the focus of this report is on the {month_name} {year} operating period.'
    content = re.sub(focus_pattern, focus_replacement, content, flags=re.IGNORECASE, count=1)
    
    # Update document name in Control Page
    doc_pattern = r'PI25003\\_La\\_Sal\\_OpsReport\\_[^}]+\.pdf'
    month_abbr_upper = month_abbr.upper()
    doc_replacement = f'PI25003\\_La\\_Sal\\_OpsReport\\_{month_abbr_upper}{year}\\_v01.pdf'
    content = re.sub(doc_pattern, doc_replacement, content, count=1)
    
    # Write updated content
    with open(main_tex_path, 'w') as f:
        f.write(content)
    
    print(f"Updated main.tex for {month_name} {year}")
    return True


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python update_latex.py <month> <year>")
        print("Example: python update_latex.py 12 2025")
        sys.exit(1)
    
    month = int(sys.argv[1])
    year = int(sys.argv[2])
    
    if not (1 <= month <= 12):
        print("Error: Month must be between 1 and 12")
        sys.exit(1)
    
    update_latex_plots(month, year)
