"""
Update main.tex to include all boxplot combinations in the report
"""
import re
from pathlib import Path
import calendar

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from config import BASE_DIR, PLOTS_DIR, TREATMENT_STATIONS, CONTROL_STATIONS


def update_boxplots_section(month, year, main_tex_path=None):
    """
    Replace the single boxplot figure with all boxplot combinations
    
    Args:
        month: Month number (1-12)
        year: Year
        main_tex_path: Path to main.tex
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
    
    # Find all boxplot files for this month/year
    boxplot_files = sorted(list(PLOTS_DIR.glob(f"{year}{month:02d}_SnowDepth_*.png")))
    
    if not boxplot_files:
        print(f"Warning: No boxplot files found for {month}/{year}")
        return False
    
    # Create LaTeX code for all boxplots
    boxplot_figures = []
    for i, boxplot_file in enumerate(boxplot_files, start=1):
        # Extract station names from filename
        filename = boxplot_file.name
        # Format: YYYYMM_SnowDepth_Treatment_vs_Control.png
        parts = filename.replace(f"{year}{month:02d}_SnowDepth_", "").replace(".png", "").split("_vs_")
        if len(parts) == 2:
            treatment = parts[0].replace("_", " ")
            control = parts[1].replace("_", " ")
            
            figure_code = f"""\\begin{{figure}}[h!]
  \\centering
  \\includegraphics[width=0.95\\textwidth]{{{filename}}}
  \\caption{{Box and whisker plots demonstrating SNOTEL-measured climatological {month_name} snow depth at (top left) {treatment}, and (top right) {control}. The difference in monthly snow depth is shown in the bottom panel. The red circle in each panel indicates values for {month_name} {year}.}}
\\end{{figure}}

"""
            boxplot_figures.append(figure_code)
    
    # Find the boxplot section in main.tex
    # Look for the figure environment with SnowDepth
    pattern = r'\\begin\{figure\}\[h!\]\s*\\centering\s*\\includegraphics\[width=0\.95\\textwidth\]\{[^}]+\}\s*\\caption\{[^}]+\}\s*\\end\{figure\}'
    
    # More flexible pattern - find the figure block
    snow_pattern = r'(\\begin\{figure\}\[h!\]\s*\\centering\s*\\includegraphics\[width=0\.95\\textwidth\]\{[^}]+\}\s*\\caption\{[^}]+\}\s*\\end\{figure\})'
    
    matches = list(re.finditer(snow_pattern, content, re.DOTALL))
    
    if matches:
        # Replace the first match with all boxplots
        start, end = matches[0].span()
        replacement = '\n'.join(boxplot_figures)
        content = content[:start] + replacement + content[end:]
        
        print(f"Replaced single boxplot with {len(boxplot_figures)} boxplot combinations")
    else:
        # Try to find by looking for SnowDepth in filename
        snow_pattern2 = r'(\\begin\{figure\}\[h!\]\s*\\centering\s*\\includegraphics\[width=0\.95\\textwidth\]\{[^}]*SnowDepth[^}]+\}\s*\\caption\{[^}]+\}\s*\\end\{figure\})'
        matches2 = list(re.finditer(snow_pattern2, content, re.DOTALL))
        
        if matches2:
            start, end = matches2[0].span()
            replacement = '\n'.join(boxplot_figures)
            content = content[:start] + replacement + content[end:]
            print(f"Replaced single boxplot with {len(boxplot_figures)} boxplot combinations")
        else:
            print("Warning: Could not find boxplot figure to replace")
            return False
    
    # Write updated content
    with open(main_tex_path, 'w') as f:
        f.write(content)
    
    print(f"Updated main.tex with all {len(boxplot_figures)} boxplot combinations")
    return True


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python update_latex_boxplots.py <month> <year>")
        print("Example: python update_latex_boxplots.py 1 2026")
        sys.exit(1)
    
    month = int(sys.argv[1])
    year = int(sys.argv[2])
    
    if not (1 <= month <= 12):
        print("Error: Month must be between 1 and 12")
        sys.exit(1)
    
    update_boxplots_section(month, year)
