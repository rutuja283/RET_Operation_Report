"""
Run the Final_Model_Scripts package itself for one report month (e.g. October 2026).

The package's four entry scripts (ridge_cold.py, ridge_warm.py, bsts_cold.py,
bsts_warm.py) are locked to December-February SWE and April-August
precipitation. This script makes a working copy of the package, changes only
the evaluation window to the report month, extends the frozen inputs through
that month, and then runs the copy's own entry scripts. The original package
is never modified.

Everything else is the package's code as delivered: models/ (feature builders
and Gibbs samplers) is copied byte for byte, and the fits, seeds, CV grids and
uncertainty rules in analysis.py and uncertainty.py are untouched apart from
the edits listed in PATCHES below. Each edit must match the package source
exactly once, otherwise the build stops. The applied edits are written to
<dest>/changes_from_package.diff.

Edits, all forced by the single-month window:

  * Month lists and the expected-date checks become the report month.
  * A season is the report month of one calendar year, so that October 2026 is
    season 2026 and the history is the Octobers of 2013-2025. (The package
    labels by water year, which would make October 2025 the "2026" season.)
  * The SWE uncertainty summary uses the days of the month instead of 90 days.
  * The two lagged-precipitation features have no prior day inside the water
    year on 1-3 October and are set to zero there.
  * --precip-convention package keeps the package's backward differences (the
    month total leaves out rain on the last day of the month). full_month uses
    the package's forward-difference option, so the total is PREC(1st of next
    month) - PREC(1st), as in the report figures.

Inputs: history comes from the package's frozen files. Days after the frozen
record ends are appended from an NRCS download (--daily-csv, wide format with
<station>_<variable> columns through the first day of the following month).

Run outside a sandbox: the package uses a process pool.
"""
import argparse
import calendar
import difflib
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

PAIRS = {572: 1153, 1215: 383}
MODELS = ["ridge_cold", "ridge_warm", "bsts_cold", "bsts_warm"]
COPY = ["analysis.py", "uncertainty.py", "run_all.py", "requirements.txt"] + [m + ".py" for m in MODELS]

# (file, exact text in the package, replacement). {M} = month number, {N} = days in month,
# {CONV} = warm_features convention, {CONV_TEXT} = wording saved in fit_settings.json.
PATCHES = [
    ("analysis.py",
     "ROOT=Path(__file__).resolve().parent\n",
     "ROOT=Path(__file__).resolve().parent\nMONTH={M}  # single-month copy: evaluation window is this calendar month\n"),
    ("analysis.py",
     "f=f[f.index.month.isin([12,1,2])].copy();f.columns=['observed','control']",
     "f=f[f.index.month.isin([MONTH])].copy();f.columns=['observed','control']"),
    ("analysis.py",
     "f['season']=f.index.year+(f.index.month>=10)",
     "f['season']=f.index.year"),
    ("analysis.py",
     "                from models import bsts_warm_kernel as m\n",
     "                from models import bsts_warm_kernel as m\n                m.TARGET_MONTHS=[MONTH]\n"),
    ("analysis.py",
     "            f,F=cold_features(base) if cold else (warm_features(base,'published'),WARM_FEATURES)\n",
     "            f,F=cold_features(base) if cold else (warm_features(base,'{CONV}'),WARM_FEATURES)\n"
     "            if not cold:f[['ctrl_precip_lag1','ctrl_precip_lag3']]=f[['ctrl_precip_lag1','ctrl_precip_lag3']].fillna(0.0)\n"),
    ("analysis.py",
     "periods=[('winter',[12,1,2])] if cold else [('spring',[4,5,6]),('july',[7]),('august',[8])]",
     "periods=[('month',[MONTH])]"),
    ("analysis.py",
     "tr=sub[sub.water_year.isin(training)];te=sub[sub.water_year==year].sort_values('date')",
     "tr=sub[sub.year.isin(training)];te=sub[sub.year==year].sort_values('date')"),
    ("analysis.py",
     "'precipitation_convention':'backward differences in all months'",
     "'precipitation_convention':'{CONV_TEXT}'"),
    ("analysis.py",
     "        if cold:\n"
     "            expected=pd.date_range(pd.Timestamp(year-1,12,1),pd.Timestamp(year,3,1)-pd.Timedelta(days=1))\n"
     "        elif bsts:\n"
     "            expected=pd.date_range(f'{year}-04-01',f'{year}-08-01',freq='MS')\n"
     "        else:expected=pd.date_range(f'{year}-04-01',f'{year}-08-31')\n",
     "        if bsts and not cold:\n"
     "            expected=pd.date_range(pd.Timestamp(year,MONTH,1),periods=1)\n"
     "        else:expected=pd.date_range(pd.Timestamp(year,MONTH,1),pd.Timestamp(year,MONTH,1)+pd.offsets.MonthEnd(0))\n"),
    ("analysis.py",
     "cold_window='December–February',warm_window='April–August'",
     "cold_window=f'calendar month {MONTH}',warm_window=f'calendar month {MONTH}'"),
    ("uncertainty.py",
     "def summarize(predictions, cold):\n",
     "N_DAYS={N}  # single-month copy: days in the evaluation month\n\ndef summarize(predictions, cold):\n"),
    ("uncertainty.py", "        assert len(c)==90\n", "        assert len(c)==N_DAYS\n"),
    ("uncertainty.py",
     "        held=h.groupby('season').head(90)\n        assert held.groupby('season').size().eq(90).all()\n",
     "        held=h.groupby('season').head(N_DAYS)\n        assert held.groupby('season').size().eq(N_DAYS).all()\n"),
]


def build_code(pkg, dest, month, n_days, convention):
    conv = "published" if convention == "package" else "forward"
    conv_text = ("backward differences (package convention)" if convention == "package"
                 else "forward differences (month total = next-month-start minus 1st)")
    for name in COPY:
        shutil.copy2(pkg / name, dest / name)
    shutil.copytree(pkg / "models", dest / "models", ignore=shutil.ignore_patterns("__pycache__"))
    diff = []
    for name in ("analysis.py", "uncertainty.py"):
        original = (pkg / name).read_text()
        text = original
        for file, old, new in PATCHES:
            if file != name:
                continue
            assert text.count(old) == 1, f"{name}: expected exactly one match for {old!r}"
            new = new.replace("{M}", str(month)).replace("{N}", str(n_days))
            text = text.replace(old, new.replace("{CONV_TEXT}", conv_text).replace("{CONV}", conv))
        (dest / name).write_text(text)
        diff += difflib.unified_diff(original.splitlines(True), text.splitlines(True),
                                     f"package/{name}", f"single_month/{name}")
    (dest / "changes_from_package.diff").write_text("".join(diff))
    for path in sorted((pkg / "models").glob("*.py")):
        assert path.read_bytes() == (dest / "models" / path.name).read_bytes()


def build_data(pkg, dest, daily_csv, month, year, convention):
    start = pd.Timestamp(year, month, 1)
    after = start + pd.offsets.MonthBegin(1)  # first day of the next month closes the last day
    wide = pd.read_csv(daily_csv, parse_dates=["date"]).set_index("date").sort_index()
    assert wide.index[-1] >= after, "download must reach the first day of the following month"
    (dest / "data").mkdir()

    # Ridge inputs: frozen rows before the report month, then the download through `after`.
    joined = {}
    for target, control in PAIRS.items():
        name = f"data/joined_accumulated_{target}.csv"
        frozen = pd.read_csv(pkg / name, parse_dates=["date"])
        frozen = frozen[frozen.date < start]
        new = wide.loc[frozen.date.max() + pd.Timedelta(days=1):after]
        assert new.index[0] <= start and new.index.to_series().diff().dropna().eq(pd.Timedelta(days=1)).all()
        add = pd.DataFrame({"date": new.index})
        for col in frozen.columns[1:]:
            side, var = col.split("_", 1)
            add[col] = new[f"{target if side == 'treat' else control}_{var}"].to_numpy()
        need = [c for c in add.columns if not c.endswith("temp_obs")]
        assert add.loc[add.date >= start, need].notna().all().all(), f"missing values in report month ({target})"
        joined[target] = pd.concat([frozen, add], ignore_index=True)
        joined[target].to_csv(dest / name, index=False, date_format="%Y-%m-%d")

    # Cold BSTS input: frozen daily table, then the report month from the download.
    frozen = pd.read_csv(pkg / "data/station_daily.csv", parse_dates=["date"])
    frozen = frozen[frozen.date < start]
    assert frozen.date.max() == start - pd.Timedelta(days=1)
    rename = {"temp": "temp_avg", "tmax": "temp_max", "tmin": "temp_min"}
    new = wide.loc[start:after]
    add = pd.DataFrame({"date": new.index[:-1]})
    for col in frozen.columns[1:]:
        sid, var = col.split("_", 1)
        series = new[f"{sid}_{rename.get(var, var)}"]
        # station_daily precip is the daily increment (not used by the models); the rest are as observed
        add[col] = (series.diff().shift(-1).clip(lower=0).round(4) if var == "precip" else series).to_numpy()[:-1]
    assert add[[c for c in add.columns if c.endswith("_swe")]].notna().all().all()
    pd.concat([frozen, add], ignore_index=True).to_csv(dest / "data/station_daily.csv", index=False,
                                                       date_format="%Y-%m-%d")

    # Warm BSTS input: one total per year for the report month, from the Ridge inputs and the
    # package's own daily differencing, so that Ridge and BSTS use the same month totals.
    sys.path.insert(0, str(dest))
    from models.ridge_features import warm_features

    n_days = calendar.monthrange(year, month)[1]
    monthly = pd.DataFrame({"date": [pd.Timestamp(y, month, 1) for y in range(2013, year + 1)]})
    for target, control in PAIRS.items():
        base = joined[target].copy()
        base["year"] = base.date.dt.year
        base["month"] = base.date.dt.month
        base["water_year"] = base.year + (base.month >= 10)
        f = warm_features(base, "published" if convention == "package" else "forward")
        f = f[(f.month == month) & f.year.between(2013, year)]
        tot = f.groupby("year")[["treat_precip", "ctrl_precip"]].sum(min_count=n_days)
        assert tot.notna().all().all() and len(tot) == len(monthly)
        monthly[str(target)] = tot.treat_precip.round(4).to_numpy()
        monthly[str(control)] = tot.ctrl_precip.round(4).to_numpy()
    monthly[["date", "572", "1153", "1215", "383"]].to_csv(dest / "data/monthly_precipitation.csv", index=False,
                                                           date_format="%Y-%m-%d")

    names = json.loads((pkg / "input_sha256.json").read_text())
    (dest / "input_sha256.json").write_text(json.dumps(
        {n: hashlib.sha256((dest / n).read_bytes()).hexdigest() for n in names}, indent=2))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--package", type=Path, required=True, help="Final_Model_Scripts folder (read only)")
    p.add_argument("--daily-csv", type=Path, required=True)
    p.add_argument("--month", type=int, default=10)
    p.add_argument("--year", type=int, default=2026, help="Must be the package's campaign year (2026)")
    p.add_argument("--precip-convention", choices=["package", "full_month"], default="package")
    p.add_argument("--dest", type=Path, default=None)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--build-only", action="store_true", help="Create the working copy without running it")
    args = p.parse_args()
    assert args.year == 2026, "the package hard-codes 2013-2025 history and a 2026 campaign"

    pkg = args.package.resolve()
    repo = Path(__file__).resolve().parent.parent
    dest = (args.dest or repo / "output" / f"final_models_{args.year}{args.month:02d}_{args.precip_convention}").resolve()
    assert pkg not in [dest, *dest.parents], "destination must be outside the package"
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    n_days = calendar.monthrange(args.year, args.month)[1]
    build_code(pkg, dest, args.month, n_days, args.precip_convention)
    build_data(pkg, dest, args.daily_csv.resolve(), args.month, args.year, args.precip_convention)
    print(f"Working copy: {dest}")
    if args.build_only:
        return

    for model in MODELS:
        subprocess.run([sys.executable, "-W", "ignore", f"{model}.py", "--workers", str(args.workers)],
                       cwd=dest, check=True)
    out = pd.concat([pd.read_csv(dest / "outputs" / m / "campaign_results.csv") for m in MODELS], ignore_index=True)
    cols = ["model", "outcome", "station", "observed", "predicted", "departure", "lower95", "upper95",
            "P_NR_positive", "loso_error_sd", "loso_mean_error"]
    out[cols].to_csv(dest / "campaign_results_all.csv", index=False)
    print(out[cols].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
