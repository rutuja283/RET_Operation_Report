"""
Generate the enhancement table (Figure 4 style) for the report.
Uses the report month's precipitation at **target stations only** (La sal upper, Lasal Mtn lower) averaged together to select the 5 driest years since 2013.

Enhancement follows MATLAB-style differencing (one value per site per year, not pooled daily diffs):
  - Snow depth & SWE: value on the **last calendar day** of the report month for target and control.
  - Accum. precip: **month total** = accumulation on last day minus accumulation on the 1st (same as dry-year ranking).
  - expecteddiff = mean(target over 5 analog years) - mean(control over 5 analog years)
    (equivalently mean of yearly (target - control) for those years).
  - actualdiff = target(report year) - control(report year)
  - Enhancement = actualdiff - expecteddiff
Pairs: La sal upper - Buckboard Flat (La sal Upper), Lasal Mtn lower - Camp jackson (La sal Lower).
"""
import calendar
from pathlib import Path

import pandas as pd

from plot_generators import load_station_data, _find_swe_or_snow_depth_column


def _find_precip_accum_column(df):
    for col in df.columns:
        c = str(col).lower()
        if "precipitation accumulation" in c or ("precip" in c and "accum" in c):
            return col
    return None


def _month_precip_total(df, date_col, prec_col, year, month):
    """Total precipitation in calendar month = accum at end of month - accum at start of month. Used for ranking years."""
    last_day = calendar.monthrange(year, month)[1]
    start_date = f"{year}-{month:02d}-01"
    end_date = f"{year}-{month:02d}-{last_day:02d}"
    start_row = df[df[date_col].dt.strftime("%Y-%m-%d") == start_date]
    end_row = df[df[date_col].dt.strftime("%Y-%m-%d") == end_date]
    if start_row.empty or end_row.empty:
        return None
    start_val = start_row.iloc[0][prec_col]
    end_val = end_row.iloc[0][prec_col]
    if pd.isna(start_val) or pd.isna(end_val):
        return None
    return float(end_val - start_val)


def _month_end_value(df, date_col, value_col, year, month):
    """Scalar on last calendar day of month (SWE or snow depth start-of-day row for that date)."""
    last_day = calendar.monthrange(year, month)[1]
    end_date = f"{year}-{month:02d}-{last_day:02d}"
    end_row = df[df[date_col].dt.strftime("%Y-%m-%d") == end_date]
    if end_row.empty:
        return None
    v = end_row.iloc[0][value_col]
    if pd.isna(v):
        return None
    return float(v)


def _matlab_style_metric(
    target_df,
    target_date_col,
    target_col,
    control_df,
    control_date_col,
    control_col,
    year,
    month,
    *,
    use_month_precip_total,
):
    """
    Return (target_value, control_value) for one calendar year/month.
    If use_month_precip_total, uses _month_precip_total for both; else month-end snapshot.
    """
    if use_month_precip_total:
        t = _month_precip_total(target_df, target_date_col, target_col, year, month)
        c = _month_precip_total(control_df, control_date_col, control_col, year, month)
    else:
        t = _month_end_value(target_df, target_date_col, target_col, year, month)
        c = _month_end_value(control_df, control_date_col, control_col, year, month)
    return t, c


def compute_enhancement_table(month=2, year=2026):
    """
    Compute enhancement table for the given report month/year.
    Uses that month's precipitation at target sites only to select 5 driest years since 2013.
    Enhancement uses MATLAB-style month-end (or month precip total) values per year, not pooled daily diffs.
    Returns (table_dict, analog_years, latex_str).
    table_dict: rows 'La sal Upper' and 'La sal Lower', each with keys 'Snow Depth (in)', 'Snow-Water Eq (in)', 'Accum. Precip (in)'.
    """
    # Pairs: (target, control) -> row label
    pairs = [
        ("La sal upper", "Buckboard Flat", "La sal Upper"),
        ("Lasal Mtn lower", "Camp jackson", "La sal Lower"),
    ]
    target_stations_for_ranking = {t for t, _, _ in pairs}
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

    # Rank years by report-month precipitation (average across target stations only)
    years_to_rank = [y for y in range(2013, year) if y != year]
    month_precip_by_year = {}
    for y in years_to_rank:
        vals = []
        for name in target_stations_for_ranking:
            v = _month_precip_total(
                data[name]["df"],
                data[name]["date_col"],
                data[name]["prec_col"],
                y,
                month,
            )
            if v is not None:
                vals.append(v)
        if vals:
            month_precip_by_year[y] = sum(vals) / len(vals)
    if len(month_precip_by_year) < 5:
        raise ValueError(
            f"Fewer than 5 years with {calendar.month_name[month]} precipitation data."
        )
    sorted_years = sorted(month_precip_by_year.keys(), key=lambda y: month_precip_by_year[y])
    analog_years = sorted_years[:5]

    # MATLAB-style: one target and one control value per year (month-end for SWE/SNWD;
    # month precip total for accum). expecteddiff = mean(T_analog) - mean(C_analog);
    # actualdiff = T_report - C_report; enhancement = actualdiff - expecteddiff.
    month_name = calendar.month_name[month]
    table_dict = {}
    for target, control, row_label in pairs:
        table_dict[row_label] = {}
        for metric, target_col, control_col, use_precip_total in [
            ("Snow Depth (in)", data[target]["snwd_col"], data[control]["snwd_col"], False),
            ("Snow-Water Eq (in)", data[target]["swe_col"], data[control]["swe_col"], False),
            ("Accum. Precip (in)", data[target]["prec_col"], data[control]["prec_col"], True),
        ]:
            analog_year_diffs = []
            for y in analog_years:
                t_v, c_v = _matlab_style_metric(
                    data[target]["df"],
                    data[target]["date_col"],
                    target_col,
                    data[control]["df"],
                    data[control]["date_col"],
                    control_col,
                    y,
                    month,
                    use_month_precip_total=use_precip_total,
                )
                if t_v is not None and c_v is not None:
                    analog_year_diffs.append(t_v - c_v)

            t_rep, c_rep = _matlab_style_metric(
                data[target]["df"],
                data[target]["date_col"],
                target_col,
                data[control]["df"],
                data[control]["date_col"],
                control_col,
                year,
                month,
                use_month_precip_total=use_precip_total,
            )

            if not analog_year_diffs or t_rep is None or c_rep is None:
                table_dict[row_label][metric] = None
                continue
            expecteddiff = sum(analog_year_diffs) / len(analog_year_diffs)
            actualdiff = t_rep - c_rep
            table_dict[row_label][metric] = actualdiff - expecteddiff

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
    for row_label in ["La sal Upper", "La sal Lower"]:
        row_vals = [
            fmt(table_dict[row_label]["Snow Depth (in)"]),
            fmt(table_dict[row_label]["Snow-Water Eq (in)"]),
            fmt(table_dict[row_label]["Accum. Precip (in)"]),
        ]
        latex_lines.append(f"    {row_label} & {row_vals[0]} & {row_vals[1]} & {row_vals[2]} \\\\")
    latex_lines.extend([
        "    \\hline",
        "  \\end{tabular}",
        f"  \\caption{{{month_name} {year} enhancement (MATLAB-style): month-end snow depth and SWE, and calendar-month precipitation totals, at each La Sal site minus its Abajo pair; expected gap $=$ mean of those gaps in the five driest {month_name}s since 2013 ({', '.join(map(str, analog_years))}), selected by average {month_name} precipitation at La sal upper and Lasal Mtn lower; enhancement $=$ report-year gap minus expected gap.}}",
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
    print(f"Analog years (5 driest {calendar.month_name[args.month]}s since 2013):", analog_years)
    print("Enhancement table:")
    for row in ["La sal Upper", "La sal Lower"]:
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
