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
from config import BASE_DIR, PLOTS_DIR, TREATMENT_STATIONS, CONTROL_STATIONS


def update_latex_plots(month, year, main_tex_path=None, snowdepth_plot=None):
    """
    Update main.tex with new plot file references
    
    Args:
        month: Month number (1-12)
        year: Year
        main_tex_path: Path to main.tex (default: BASE_DIR/main.tex)
        snowdepth_plot: Specific snow depth plot filename to use (if None, uses default or finds first available)
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
    }
    
    # Handle snow depth plot - use specified one or find first available
    if snowdepth_plot:
        plot_files['snowdepth'] = snowdepth_plot
    else:
        # Prefer new station-specific files over old default name
        # Default to La Sal Mtn vs Camp jackson if available (matches report text)
        preferred = f"{year}{month:02d}_SnowDepth_La_Sal_Mtn_vs_Camp_jackson.png"
        if (PLOTS_DIR / preferred).exists():
            plot_files['snowdepth'] = preferred
            print(f"Using preferred snow depth plot: {plot_files['snowdepth']}")
        else:
            # Find first available snow depth plot for this month/year
            snow_plots = list(PLOTS_DIR.glob(f"{year}{month:02d}_SnowDepth_*.png"))
            if snow_plots:
                plot_files['snowdepth'] = snow_plots[0].name
                print(f"Using first available snow depth plot: {plot_files['snowdepth']}")
            else:
                # Fallback to old default name
                default_snow = f"{year}{month:02d}_SnowDepthSummary_Report.png"
                plot_files['snowdepth'] = default_snow
    
    # Check if plots exist
    for plot_type, filename in plot_files.items():
        plot_path = PLOTS_DIR / filename
        if not plot_path.exists():
            print(f"Warning: Plot not found: {plot_path}")
    
    # Update operations schedule plot
    ops_pattern = r'\\includegraphics\[width=0\.85\\textwidth\]\{[^}]+\}'
    # Use lambda to return properly escaped string
    def ops_replacer(match):
        return r'\includegraphics[width=0.85\textwidth]{' + plot_files["operations"] + '}'
    content = re.sub(ops_pattern, ops_replacer, content, count=1)
    
    # Update caption for operations schedule
    ops_caption_pattern = r'\\caption\{WETA operating schedule during [^}]+\}'
    # Use lambda to return properly escaped string
    def ops_caption_replacer(match):
        return (r'\caption{WETA operating schedule during ' + 
                month_name + ' ' + str(year) + r'. Green shading indicates periods of operation.}}')
    content = re.sub(ops_caption_pattern, ops_caption_replacer, content, count=1)
    
    # Update precipitation plot
    precip_pattern = r'\\includegraphics\[width=0\.85\\textwidth\]\{[^}]+\}'
    # Find the second occurrence (precipitation plot)
    matches = list(re.finditer(precip_pattern, content))
    if len(matches) >= 2:
        start, end = matches[1].span()
        # Use lambda to avoid regex escape interpretation
        precip_replacement = r'\includegraphics[width=0.85\textwidth]{' + plot_files["precipitation"] + '}'
        content = content[:start] + precip_replacement + content[end:]
    
    # Update precipitation caption
    precip_caption_pattern = r'\\caption\{Summary of daily accumulated precipitation[^}]+\}'
    # Use function to return properly escaped string
    def precip_caption_replacer(match):
        return r'\caption{Summary of daily accumulated precipitation at reporting weather and SNOTEL stations.}'
    content = re.sub(precip_caption_pattern, precip_caption_replacer, content, count=1)
    
    # Replace all boxplot figures with all boxplot combinations
    # Find all boxplot files for this month/year
    boxplot_files = sorted(list(PLOTS_DIR.glob(f"{year}{month:02d}_SnowDepth_*.png")))
    
    if boxplot_files:
        # Create LaTeX code for all boxplots
        boxplot_figures = []
        for boxplot_file in boxplot_files:
            filename = boxplot_file.name
            # Extract station names from filename
            parts = filename.replace(f"{year}{month:02d}_SnowDepth_", "").replace(".png", "").split("_vs_")
            if len(parts) == 2:
                treatment = parts[0].replace("_", " ")
                control = parts[1].replace("_", " ")
                
                figure_code = (r'\begin{figure}[h!]' + '\n' +
                             r'  \centering' + '\n' +
                             r'  \includegraphics[width=0.95\textwidth]{' + filename + '}' + '\n' +
                             r'  \caption{Box and whisker plots demonstrating SNOTEL-measured climatological ' +
                             month_name + r' snow depth at (top left) ' + treatment + 
                             r', and (top right) ' + control + 
                             r'. The difference in monthly snow depth is shown in the bottom panel. ' +
                             r'The red circle in each panel indicates values for ' + month_name + ' ' + str(year) + r'.}' + '\n' +
                             r'\end{figure}' + '\n\n')
                boxplot_figures.append(figure_code)
        
        # Find the section from first SnowDepth figure to before Radiometer subsection
        # This pattern matches all consecutive SnowDepth figures
        snow_section_pattern = r'(\\begin\{figure\}\[h!\]\s*\\centering\s*\\includegraphics\[width=0\.95\\textwidth\]\{[^}]*SnowDepth[^}]+\}\s*\\caption\{[^}]+\}\s*\\end\{figure\}(?:\s*\\begin\{figure\}[^}]*SnowDepth[^}]*\\end\{figure\})*)\s*(?=\\subsection\{Analysis of Radiometer Data\})'
        
        matches = list(re.finditer(snow_section_pattern, content, re.DOTALL))
        if matches:
            # Replace the entire boxplot section
            start, end = matches[0].span()
            replacement = ''.join(boxplot_figures)
            content = content[:start] + replacement + content[end:]
            print(f"Replaced boxplot section with {len(boxplot_figures)} boxplot combinations")
        else:
            # Fallback: find just the first SnowDepth figure
            snow_figure_pattern = r'\\begin\{figure\}\[h!\]\s*\\centering\s*\\includegraphics\[width=0\.95\\textwidth\]\{[^}]*SnowDepth[^}]+\}\s*\\caption\{[^}]+\}\s*\\end\{figure\}'
            matches = list(re.finditer(snow_figure_pattern, content, re.DOTALL))
            if matches:
                start, end = matches[0].span()
                replacement = ''.join(boxplot_figures)
                content = content[:start] + replacement + content[end:]
                print(f"Replaced single boxplot with {len(boxplot_figures)} boxplot combinations")
    
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
    focus_replacement = 'the focus of this report is on the ' + month_name + ' ' + str(year) + ' operating period.'
    content = re.sub(focus_pattern, focus_replacement, content, flags=re.IGNORECASE, count=1)
    
    # Update document name in Control Page
    doc_pattern = r'PI25003\\_La\\_Sal\\_OpsReport\\_[^}]+\.pdf'
    month_abbr_upper = month_abbr.upper()
    doc_replacement = r'PI25003\_La\_Sal\_OpsReport\_' + month_abbr_upper + str(year) + r'\_v01.pdf'
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
    snowdepth_plot = sys.argv[3] if len(sys.argv) > 3 else None
    
    if not (1 <= month <= 12):
        print("Error: Month must be between 1 and 12")
        sys.exit(1)
    
    update_latex_plots(month, year, snowdepth_plot=snowdepth_plot)
