"""
Update main.tex with new plot references for a given month/year
"""
import re
import subprocess
import sys
from pathlib import Path
import calendar

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
    
    # Report month/year prefix for all plot filenames (YYYYMM)
    plot_prefix = f"{year}{month:02d}"
    
    # Replace ALL plot paths that contain a YYYYMM pattern so latest figures are used
    content = re.sub(r'plots/(\d{6})_', f'plots/{plot_prefix}_', content)
    
    # Generate plot filenames for the rest of the logic
    plot_files = {
        'operations': f"{plot_prefix}_OperatingSchedule_Report.png",
        'precipitation': f"{plot_prefix}_PrecipSummary_Report_v02.png",
    }
    
    # Handle snow depth plot - use specified one or find first available
    if snowdepth_plot:
        plot_files['snowdepth'] = snowdepth_plot
    else:
        # Prefer new station-specific files over old default name
        # Default to La sal upper vs Camp jackson if available (matches report text)
        # Prefer SWE (snow water equivalent) plots to match February report
        preferred_swe = f"{year}{month:02d}_SWE_La_sal_upper_vs_Camp_jackson.png"
        preferred_depth = f"{year}{month:02d}_SnowDepth_La_sal_upper_vs_Camp_jackson.png"
        if (PLOTS_DIR / preferred_swe).exists():
            plot_files['snowdepth'] = preferred_swe
            print(f"Using preferred SWE plot: {plot_files['snowdepth']}")
        elif (PLOTS_DIR / preferred_depth).exists():
            plot_files['snowdepth'] = preferred_depth
            print(f"Using preferred snow depth plot: {plot_files['snowdepth']}")
        else:
            # Find first available SWE or snow depth plot for this month/year
            snow_plots = list(PLOTS_DIR.glob(f"{year}{month:02d}_SWE_*.png")) or list(PLOTS_DIR.glob(f"{year}{month:02d}_SnowDepth_*.png"))
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
        return r'\includegraphics[width=0.85\textwidth]{plots/' + plot_files["operations"] + '}'
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
        precip_replacement = r'\includegraphics[width=0.85\textwidth]{plots/' + plot_files["precipitation"] + '}'
        content = content[:start] + precip_replacement + content[end:]
    
    # Update precipitation caption
    precip_caption_pattern = r'\\caption\{Summary of daily accumulated precipitation[^}]+\}'
    # Use function to return properly escaped string
    def precip_caption_replacer(match):
        return r'\caption{Summary of daily accumulated precipitation at reporting weather and SNOTEL stations.}'
    content = re.sub(precip_caption_pattern, precip_caption_replacer, content, count=1)
    
    # Replace all boxplot figures with ONLY La sal upper vs Camp jackson
    # Find the specific boxplot file (plot names use underscores: La_sal_upper)
    target_boxplot = f"{year}{month:02d}_SWE_La_sal_upper_vs_Camp_jackson.png"
    boxplot_path = PLOTS_DIR / target_boxplot
    if not boxplot_path.exists():
        target_boxplot = f"{year}{month:02d}_SnowDepth_La_sal_upper_vs_Camp_jackson.png"
        boxplot_path = PLOTS_DIR / target_boxplot

    if boxplot_path.exists():
        # Create LaTeX code for only this boxplot
        treatment = "La sal upper"
        control = "Camp jackson"
        
        figure_code = (r'\begin{figure}[h!]' + '\n' +
                     r'  \centering' + '\n' +
                     r'  \includegraphics[width=0.95\textwidth]{plots/' + target_boxplot + '}' + '\n' +
                     r'  \caption{Box and whisker plots demonstrating SNOTEL-measured climatological December and January snow water content (SWE) at (top left) La sal Upper, (top middle) Buckboard Flat, (bottom left) La sal Lower, and (bottom middle) Camp Jackson. The differences are shown in the right-most column. The red circles in each panel indicate values for the current year.}' + '\n' +
                     r'\end{figure}' + '\n\n')
        
        # Find the section from first SnowDepth figure to before Radiometer subsection
        # This pattern matches all consecutive SnowDepth figures
        snow_section_pattern = r'(\\begin\{figure\}\[h!\]\s*\\centering\s*\\includegraphics\[width=0\.95\\textwidth\]\{[^}]*SnowDepth[^}]+\}\s*\\caption\{[^}]+\}\s*\\end\{figure\}(?:\s*\\begin\{figure\}[^}]*SnowDepth[^}]*\\end\{figure\})*)\s*(?=\\subsection\{Analysis of Radiometer Data\})'
        
        matches = list(re.finditer(snow_section_pattern, content, re.DOTALL))
        if matches:
            # Replace the entire boxplot section with just one boxplot
            start, end = matches[0].span()
            content = content[:start] + figure_code + content[end:]
            print(f"Replaced boxplot section with La sal upper vs Camp jackson only")
        else:
            # Fallback: find just the first SnowDepth figure
            snow_figure_pattern = r'\\begin\{figure\}\[h!\]\s*\\centering\s*\\includegraphics\[width=0\.95\\textwidth\]\{[^}]*SnowDepth[^}]+\}\s*\\caption\{[^}]+\}\s*\\end\{figure\}'
            matches = list(re.finditer(snow_figure_pattern, content, re.DOTALL))
            if matches:
                start, end = matches[0].span()
                content = content[:start] + figure_code + content[end:]
                print(f"Replaced single boxplot with La sal upper vs Camp jackson")
    else:
        print(f"Warning: Target boxplot not found: {target_boxplot}")
    
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

    # Generate enhancement table and update subsection placeholders
    try:
        subprocess.run(
            [
                sys.executable,
                str(Path(__file__).parent / "enhancement_table.py"),
                "--month", str(month),
                "--year", str(year),
                "-o", str(BASE_DIR / "enhancement_table.tex"),
            ],
            cwd=str(BASE_DIR),
            check=True,
            capture_output=True,
        )
        analog_path = BASE_DIR / "enhancement_analog_years.txt"
        if analog_path.exists():
            analog_years_str = analog_path.read_text(encoding="utf-8").strip()
            content = content.replace("ENHANCEMENT_ANALOG_YEARS", analog_years_str)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"Warning: Could not run enhancement_table.py: {e}")
        content = content.replace("ENHANCEMENT_ANALOG_YEARS", "---")
    report_month_year = f"{month_name} {year}"
    content = content.replace("REPORT_MONTH_YEAR", report_month_year)
    content = content.replace("REPORT_YEAR", str(year))
    content = content.replace("REPORT_PRIOR_YEAR_END", str(year - 1))

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
