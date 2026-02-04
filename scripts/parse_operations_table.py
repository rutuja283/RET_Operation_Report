"""
Parse operations table data and generate CSV and LaTeX table
"""
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import re
import sys
import calendar

sys.path.insert(0, str(Path(__file__).parent))
from config import CSV_DIR, BASE_DIR

def parse_operations_data():
    """
    Parse the operations data provided by user
    Returns DataFrame with Date, On_Time, Off_Time, Status columns
    """
    # Raw data from user - January 2026
    data = [
        ("01-Jan-2026", "2157 off"),
        ("04-Jan-2026", "1939 on"),
        ("05-Jan-2026", "1134 off"),
        ("05-Jan-2026", "2354 on"),
        ("06-Jan-2026", "1159 off"),
        ("07-Jan-2026", "1605 on"),
        ("09-Jan-2026", "1243 off"),
    ]
    
    year = 2026
    month = 1
    
    rows = []
    
    for date_str, status_str in data:
        # Parse date - handle both "D-Mon" and "DD-Mon-YYYY" formats
        if " to " in date_str:
            # Date range
            start_str, end_str = date_str.split(" to ")
            # Try to parse as full date first
            try:
                start_date = datetime.strptime(start_str.strip(), "%d-%b-%Y")
                end_date = datetime.strptime(end_str.strip(), "%d-%b-%Y")
                # Generate all dates in range
                current = start_date
                days = []
                while current <= end_date:
                    days.append(current.day)
                    current += timedelta(days=1)
            except:
                # Fallback to old format
                start_day = int(re.search(r'\d+', start_str).group())
                end_day = int(re.search(r'\d+', end_str).group())
                days = list(range(start_day, end_day + 1))
        else:
            # Single date - try full format first
            try:
                date_obj = datetime.strptime(date_str.strip(), "%d-%b-%Y")
                days = [date_obj.day]
                # Update year and month from parsed date if needed
                if date_obj.year != year:
                    year = date_obj.year
                if date_obj.month != month:
                    month = date_obj.month
            except:
                # Fallback to old format
                day = int(re.search(r'\d+', date_str).group())
                days = [day]
        
        # Parse status
        on_time = None
        off_time = None
        is_on = False
        status_display = status_str  # Keep original for display
        
        # Check if status contains "on" or "off"
        status_lower = status_str.lower()
        
        if status_lower == "on":
            # Just "on" - all day
            is_on = True
            status_display = "on"
        elif status_lower == "off":
            # Just "off" - not operating
            is_on = False
            status_display = "off"
        elif " / " in status_str:
            # Has both on and off times (e.g., "1158 on / 2356 off")
            parts = status_str.split(" / ")
            for part in parts:
                time_match = re.search(r'(\d{4})', part)
                if time_match:
                    time_val = time_match.group(1)
                    if "on" in part.lower():
                        on_time = time_val
                        is_on = True
                    elif "off" in part.lower():
                        off_time = time_val
            status_display = status_str
        else:
            # Single time with on/off (e.g., "0134 off" means was on until 0134)
            time_match = re.search(r'(\d{4})', status_str)
            if time_match:
                time_val = time_match.group(1)
                if "off" in status_lower:
                    # Was on until this time, then off
                    off_time = time_val
                    is_on = True  # Was operating part of the day
                    status_display = status_str
                elif "on" in status_lower:
                    # Turned on at this time
                    on_time = time_val
                    is_on = True
                    status_display = status_str
        
        # Create row for each day
        for day in days:
            date = datetime(year, month, day)
            rows.append({
                'Date': date,
                'On_Time': on_time,
                'Off_Time': off_time,
                'Operating': is_on,
                'Status_Text': status_display
            })
    
    df = pd.DataFrame(rows)
    df = df.sort_values('Date')
    
    return df

def generate_operations_table_latex(df, month, year):
    """
    Generate LaTeX table in the format shown by user
    """
    # Group consecutive days with same status
    table_rows = []
    current_range = None
    current_status = None
    current_on_time = None
    current_off_time = None
    
    for idx, row in df.iterrows():
        date = row['Date']
        status = row['Operating']
        on_time = row['On_Time']
        off_time = row['Off_Time']
        
        # Format date as "D-Mon"
        date_str = date.strftime("%-d-%b")
        
        # Use the original status text from the data
        status_text = row['Status_Text']
        
        # Check if we can merge with previous row
        if (current_range is not None and 
            current_status == status and
            current_on_time == on_time and
            current_off_time == off_time):
            # Extend range
            current_range = (current_range[0], date)
        else:
            # Save previous range if exists
            if current_range is not None:
                start_date, end_date = current_range
                if start_date == end_date:
                    date_col = start_date.strftime("%-d-%b")
                else:
                    date_col = f"{start_date.strftime('%-d-%b')} to {end_date.strftime('%-d-%b')}"
                
                table_rows.append({
                    'date': date_col,
                    'status': current_status_text,
                    'is_on': current_status
                })
            
            # Start new range
            current_range = (date, date)
            current_status = status
            current_status_text = status_text
            current_on_time = on_time
            current_off_time = off_time
    
    # Add last range
    if current_range is not None:
        start_date, end_date = current_range
        if start_date == end_date:
            date_col = start_date.strftime("%-d-%b")
        else:
            date_col = f"{start_date.strftime('%-d-%b')} to {end_date.strftime('%-d-%b')}"
        
        table_rows.append({
            'date': date_col,
            'status': current_status_text,
            'is_on': current_status
        })
    
    # Generate LaTeX
    latex_lines = []
    latex_lines.append("\\begin{longtable}{|p{5cm}|p{10cm}|}")
    latex_lines.append("\\hline")
    latex_lines.append("\\textbf{DATE(S)} & \\textbf{WETA on/off} \\\\")
    latex_lines.append("\\hline")
    latex_lines.append("\\endfirsthead")
    latex_lines.append("\\hline")
    latex_lines.append("\\textbf{DATE(S)} & \\textbf{WETA on/off} \\\\")
    latex_lines.append("\\hline")
    latex_lines.append("\\endhead")
    latex_lines.append("\\hline")
    latex_lines.append("\\endfoot")
    latex_lines.append("\\hline")
    latex_lines.append("\\endlastfoot")
    
    for row in table_rows:
        date_col = row['date']
        status_col = row['status']
        is_on = row['is_on']
        
        # Add green highlighting if WETA is on
        if is_on:
            latex_lines.append("\\rowcolor{greenhighlight}")
        
        latex_lines.append(f"{date_col} & {status_col} \\\\")
        latex_lines.append("\\hline")
    
    latex_lines.append("\\end{longtable}")
    
    return "\n".join(latex_lines)

if __name__ == "__main__":
    # Parse data
    df = parse_operations_data()
    
    # Save to CSV
    csv_path = CSV_DIR / "operations_schedule.csv"
    # Convert to format expected by existing code
    df_export = df[['Date', 'Operating']].copy()
    df_export['Date'] = df_export['Date'].dt.strftime('%Y-%m-%d')
    df_export.to_csv(csv_path, index=False)
    print(f"Saved operations CSV to {csv_path}")
    
    # Determine month and year from data
    if len(df) > 0:
        data_month = df['Date'].dt.month.iloc[0]
        data_year = df['Date'].dt.year.iloc[0]
    else:
        data_month = 1
        data_year = 2026
    
    # Generate LaTeX table
    latex_table = generate_operations_table_latex(df, data_month, data_year)
    
    # Save LaTeX table to file
    latex_path = BASE_DIR / "operations_table.tex"
    with open(latex_path, 'w') as f:
        f.write(latex_table)
    print(f"Saved LaTeX table to {latex_path}")
    
    # Also print it
    print("\n" + "="*60)
    print("LaTeX Table:")
    print("="*60)
    print(latex_table)
