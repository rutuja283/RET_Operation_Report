#!/usr/bin/env python3
"""Remove duplicate boxplot figures from main.tex"""

with open('main.tex', 'r') as f:
    lines = f.readlines()

# Find the start and end of the boxplot section
start_idx = None
end_idx = None
radiometer_idx = None

for i, line in enumerate(lines):
    if 'SnowDepth' in line and 'includegraphics' in line and start_idx is None:
        # Go back to find the figure start
        for j in range(i, max(0, i-5), -1):
            if '\\begin{figure}' in lines[j]:
                start_idx = j
                break
    if '\\subsection{Analysis of Radiometer Data}' in line:
        radiometer_idx = i
        break

if start_idx is None or radiometer_idx is None:
    print("Could not find boxplot section boundaries")
    exit(1)

# Collect unique boxplot figures
seen_filenames = set()
unique_figures = []
current_figure = []
in_figure = False

for i in range(start_idx, radiometer_idx):
    line = lines[i]
    
    if '\\begin{figure}' in line:
        in_figure = True
        current_figure = [line]
    elif in_figure:
        current_figure.append(line)
        
        # Check if this line has a filename
        if 'SnowDepth' in line and '.png' in line:
            # Extract filename
            import re
            match = re.search(r'SnowDepth[^}]+\.png', line)
            if match:
                filename = match.group(0)
                if filename in seen_filenames:
                    # Skip this duplicate
                    current_figure = []
                    in_figure = False
                    continue
                else:
                    seen_filenames.add(filename)
        
        if '\\end{figure}' in line:
            if current_figure:
                unique_figures.extend(current_figure)
            current_figure = []
            in_figure = False

# Reconstruct the file
new_lines = lines[:start_idx] + unique_figures + ['\n'] + lines[radiometer_idx:]

with open('main.tex', 'w') as f:
    f.writelines(new_lines)

print(f"Removed duplicates, kept {len(seen_filenames)} unique boxplots")
