"""
Generate the enhancement table (Figure 4 style) for the report.
Uses February precipitation to select the 5 driest years since 2013,
then computes (Target - Control) for Feb of those years and for Feb 2026;
enhancement = (Feb 2026 difference) - mean(5 driest years' differences).
Pairs: La sal upper - Buckboard Flat (LA SAL UPPER), Lasal Mtn lower - Camp jackson (LA SAL LOWER).
"""
import calendar
from pathlib import Path

import pandas as pd

from config import CSV_DIR
from plot_generators import load_station_data, _find_swe_or_snow_depth_column


def _find_precip_accum_column(df):
    for col in df.columns:
        c = str(col).lower()
        if "precipitation accumulation" in c or ("precip" in c and "accum" in c):
            return col
    return None


def _get_february_metrics(df, date_col, swe_col, snwd_col, prec_col, year):
    """Return (swe, snwd, prec) on the last day of February for the given year. None if missing."""
    feb_last = 29 if calendar.isleap(year) else 28
    end_date = f"{year}-02-{feb_last:02d}"
    row = df[df[date_col].dt.strftime("%Y-%m-%d") == end_date]
    if row.empty:
        return None, None, None
    r = row.iloc[0]
    return (
        r[swe_col] if pd.notna(r[swe_col]) else None,
        r[snwd_col] if pd.notna(r[snwd_col]) else None,
        r[prec_col] if pd.notna(r[prec_col]) else None,
    )


def _february_precip_total(df, date_col, prec_col, year):
    """Total precipitation in February = accum at end of Feb - accum at start of Feb (or Jan 31)."""
    feb_last = 29 if calendar.isleap(year) else 28
    start_date = f"{year}-02-01"
    end_date = f"{year}-02-{feb_last:02d}"
    start_row = df[df[date_col].dt.strftime("%Y-%m-%d") == start_date]
    end_row = df[df[date_col].dt.strftime("%Y-%m-%d") == end_date]
    if start_row.empty or end_row.empty:
        return None
    start_val = start_row.iloc[0][prec_col]
    end_val = end_row.iloc[0][prec_col]
    if pd.isna(start_val) or pd.isna(end_val):
        return None
    return float(end_val - start_val)


def compute_enhancement_table(month=2, year=2026):
    """
    Compute enhancement table for the given report month/year.
    Uses that month's precipitation to select 5 driest years since 2013.
    Returns (table_dict, analog_years, latex_str).
    table_dict: rows 'LA SAL UPPER' and 'LA SAL LOWER', each with keys 'Snow Depth (in)', 'Snow-Water Eq (in)', 'Accum. Precip (in)'.
    """
    # Pairs: (target, control) -> row label
    pairs = [
        ("La sal upper", "Buckboard Flat", "LA SAL UPPER"),
        ("Lasal Mtn lower", "Camp jackson", "LA SAL LOWER"),
    ]
    stations_needed = set()
    for t, c, _ in pairs:
        stations_needed.add(t)
        stations_needed.add(c)

    # Load all four stations and detect columns
    data = {}
    for name in stations_needed:
        result = load_station_data(name)
        if result is None:
            raise FileNotFoundError(f"Station CSV not found: {name}")
        df, date_col = result
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df[df[date_col].notna()].copy()

        swe_col, _ = _find_swe_or_snow_depth_column(df, prefer_swe=True)
        snwd_col, _ = _find_swe_or_snow_depth_column(df, prefer_swe=False)
        prec_col = _find_precip_accum_column(df)
        if swe_col is None or snwd_col is None or prec_col is None:
            raise ValueError(f"Missing SWE/SNWD/Precip column for {name}")

        data[name] = {
            "df": df,
            "date_col": date_col,
            "swe_col": swe_col,
            "snwd_col": snwd_col,
            "prec_col": prec_col,
        }

    # Rank years by February precipitation (average across the four stations)
    years_to_rank = [y for y in range(2013, year) if y != year]
    feb_precip_by_year = {}
    for y in years_to_rank:
        vals = []
        for name in stations_needed:
            v = _february_precip_total(
                data[name]["df"],
                data[name]["date_col"],
                data[name]["prec_col"],
                y,
            )
            if v is not None:
                vals.append(v)
        if vals:
            feb_precip_by_year[y] = sum(vals) / len(vals)
    if len(feb_precip_by_year) < 5:
        raise ValueError("Fewer than 5 years with February precipitation data.")
    sorted_years = sorted(feb_precip_by_year.keys(), key=lambda y: feb_precip_by_year[y])
    analog_years = sorted_years[:5]

    # For each pair and each metric: differences for analog years and for report year.
    # Snow Depth and SWE: end-of-month (Target - Control). Accum. Precip: precip that fell during the month (Target - Control).
    all_years = analog_years + [year]
    diffs_by_pair_metric = {}
    for target, control, row_label in pairs:
        diffs_by_pair_metric[row_label] = {
            "Snow Depth (in)": [],
            "Snow-Water Eq (in)": [],
            "Accum. Precip (in)": [],
        }
        for y in all_years:
            t_swe, t_snwd, t_prec = _get_february_metrics(
                data[target]["df"],
                data[target]["date_col"],
                data[target]["swe_col"],
                data[target]["snwd_col"],
                data[target]["prec_col"],
                y,
            )
            c_swe, c_snwd, c_prec = _get_february_metrics(
                data[control]["df"],
                data[control]["date_col"],
                data[control]["swe_col"],
                data[control]["snwd_col"],
                data[control]["prec_col"],
                y,
            )
            if t_snwd is not None and c_snwd is not None:
                diffs_by_pair_metric[row_label]["Snow Depth (in)"].append((y, t_snwd - c_snwd))
            if t_swe is not None and c_swe is not None:
                diffs_by_pair_metric[row_label]["Snow-Water Eq (in)"].append((y, t_swe - c_swe))
            # Accum. Precip: use total precip that fell in February (increment), not cumulative
            t_feb_prec = _february_precip_total(
                data[target]["df"], data[target]["date_col"], data[target]["prec_col"], y
            )
            c_feb_prec = _february_precip_total(
                data[control]["df"], data[control]["date_col"], data[control]["prec_col"], y
            )
            if t_feb_prec is not None and c_feb_prec is not None:
                diffs_by_pair_metric[row_label]["Accum. Precip (in)"].append(
                    (y, t_feb_prec - c_feb_prec)
                )

    # Expected = mean of analog years; enhancement = current year diff - expected
    month_name = calendar.month_name[month]
    table_dict = {}
    for row_label in ["LA SAL UPPER", "LA SAL LOWER"]:
        table_dict[row_label] = {}
        for metric in ["Snow Depth (in)", "Snow-Water Eq (in)", "Accum. Precip (in)"]:
            entries = diffs_by_pair_metric[row_label][metric]
            analog_diffs = [v for (y, v) in entries if y in analog_years]
            year_diffs = [v for (y, v) in entries if y == year]
            if not analog_diffs:
                table_dict[row_label][metric] = None
                continue
            expected = sum(analog_diffs) / len(analog_diffs)
            current = year_diffs[0] if year_diffs else None
            if current is not None:
                enhancement = current - expected
                table_dict[row_label][metric] = enhancement
            else:
                table_dict[row_label][metric] = None

    # LaTeX table
    def fmt(v):
        if v is None:
            return "---"
        s = f"{v:+.2f}".rstrip("0").rstrip(".")
        if s.startswith("+") and "." not in s and s != "+":
            return s
        return s

    latex_lines = [
        "\\begin{table}[h!]",
        "  \\centering",
        "  \\begin{tabular}{lccc}",
        "    \\hline",
        "    & Snow Depth (in) & Snow-Water Eq (in) & Accum. Precip (in) \\\\",
        "    \\hline",
    ]
    for row_label in ["LA SAL UPPER", "LA SAL LOWER"]:
        row_vals = [
            fmt(table_dict[row_label]["Snow Depth (in)"]),
            fmt(table_dict[row_label]["Snow-Water Eq (in)"]),
            fmt(table_dict[row_label]["Accum. Precip (in)"]),
        ]
        latex_lines.append(f"    {row_label} & {row_vals[0]} & {row_vals[1]} & {row_vals[2]} \\\\")
    latex_lines.extend([
        "    \\hline",
        "  \\end{tabular}",
        f"  \\caption{{{month_name} {year} enhancement estimated by taking the difference between observations at sites in La Sal and Abajo compared to the difference observed in the driest five recent years ({', '.join(map(str, analog_years))}).}}",
        "  \\label{fig:enhancement}",
        "\\end{table}",
    ])
    latex_str = "\n".join(latex_lines)

    return table_dict, analog_years, latex_str


def main():
    import argparse
    p = argparse.ArgumentParser(description="Generate enhancement table for report.")
    p.add_argument("--month", type=int, default=2, help="Report month (default 2)")
    p.add_argument("--year", type=int, default=2026, help="Report year (default 2026)")
    p.add_argument("-o", "--output", type=str, default=None, help="Write LaTeX table to this file")
    args = p.parse_args()
    table_dict, analog_years, latex_str = compute_enhancement_table(month=args.month, year=args.year)
    print("Analog years (5 driest Februarys since 2013):", analog_years)
    print("Enhancement table:")
    for row in ["LA SAL UPPER", "LA SAL LOWER"]:
        print(f"  {row}:", table_dict[row])
    out_path = Path(args.output) if args.output else None
    if out_path is not None:
        out_path.write_text(latex_str, encoding="utf-8")
        print(f"Wrote LaTeX table to {out_path}")
        # Write analog years for update_latex to use in subsection text
        analog_path = out_path.parent / "enhancement_analog_years.txt"
        analog_path.write_text(", ".join(map(str, analog_years)), encoding="utf-8")
        print(f"Wrote analog years to {analog_path}")
    else:
        print("\nLaTeX:\n", latex_str)


if __name__ == "__main__":
    main()
