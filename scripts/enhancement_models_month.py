"""
Single-month Ridge and BSTS estimates for a La Sal report month (e.g. October 2026).

The Final_Model_Scripts package is locked to two windows: December-February SWE
and April-August precipitation. This driver applies the same model code to one
calendar month outside those windows. It imports the package's feature builders
and Gibbs samplers and does not modify or copy them:

  Ridge precip  two-part wet-day occurrence x amount model (package warm Ridge)
  Ridge SWE     daily target-minus-control SWE regression (package cold Ridge)
  BSTS precip   monthly-total sampler with control regression (package warm BSTS)
  BSTS SWE      daily SWE sampler with control regression (package cold BSTS)

Differences from the package, all forced by the single-month window:

  * A "season" is the report month of one calendar year. History is the same
    13 years as the package (2013-2025); the report year is never used in fitting.
  * Fitting and evaluation use only days (or the one monthly total) in the
    report month. The BSTS precip model therefore has one observation per season
    and a single month offset.
  * Precipitation convention. "full_month" (default) uses forward differences of
    the start-of-day accumulation, so the month total is PREC(1st of next month)
    - PREC(1st), as in the report figures. "package" uses the package's backward
    differences, which leave out rain on the last day of the month.
  * October starts the water year, so the two lagged-precipitation features have
    no prior day inside the water year on 1-3 October. They are set to zero,
    consistent with the package's rolling and cumulative features, which also
    start from zero on 1 October.
  * SWE is summarised as the mean over the days of the month.

Uncertainty follows the package's uncertainty.py: leave-one-season-out errors,
sample SD across the 13 seasons, departure +/- 1.96 SD, and the normal-reference
P(departure > 0). That probability is not a posterior probability of enhancement.

History comes from the package's frozen inputs. Only the report month itself is
appended, from a fresh NRCS download (see --daily-csv).
"""
import argparse
import calendar
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

POOL = list(range(2013, 2026))
PAIRS = {572: 1153, 1215: 383}
STATION = {572: "La Sal Upper", 1215: "La Sal Lower"}
CONTROL = {572: "Buckboard Flat", 1215: "Camp Jackson"}
KEEP = ["swe", "snowdepth", "precip", "temp_avg", "temp_max", "temp_min"]


def load_base(pkg, daily_csv, target, month, year):
    """Frozen package history before the report month + downloaded report month."""
    control = PAIRS[target]
    cols = ["date"] + [f"{side}_{k}" for side in ("treat", "ctrl") for k in KEEP]
    frozen = pd.read_csv(pkg / f"data/joined_accumulated_{target}.csv", parse_dates=["date"])[cols]
    start = pd.Timestamp(year, month, 1)
    end = start + pd.offsets.MonthBegin(1)  # first day of the next month closes the last day
    frozen = frozen[frozen.date < start]
    wide = pd.read_csv(daily_csv, parse_dates=["date"]).set_index("date").loc[start:end]
    assert wide.index[0] == start and wide.index[-1] == end, "download does not span the report month"
    new = pd.DataFrame({"date": wide.index})
    for side, sid in (("treat", target), ("ctrl", control)):
        for k in KEEP:
            new[f"{side}_{k}"] = wide[f"{sid}_{k}"].to_numpy()
    assert new[cols].notna().all().all(), "missing values in the report month"
    base = pd.concat([frozen, new[cols]], ignore_index=True)
    base["year"] = base.date.dt.year
    base["month"] = base.date.dt.month
    base["water_year"] = base.year + (base.month >= 10)
    return base


def month_days(frame, month, n_days):
    sub = frame[frame.month == month].copy()
    sub["season"] = sub.date.dt.year
    sub = sub[sub.season.isin(POOL + [REPORT_YEAR])]
    assert sub.groupby("season").size().eq(n_days).all(), "incomplete month in some season"
    return sub.sort_values("date")


def fit_ridge_precip(base, month, n_days, held_out, convention):
    from sklearn.linear_model import LogisticRegressionCV, RidgeCV
    from sklearn.preprocessing import StandardScaler
    from models.ridge_features import WARM_FEATURES, warm_features

    f = warm_features(base, "published" if convention == "package" else "forward")
    lags = ["ctrl_precip_lag1", "ctrl_precip_lag3"]
    f[lags] = f[lags].fillna(0.0)  # no prior day inside the water year on 1-3 October
    sub = month_days(f.dropna(subset=WARM_FEATURES + ["treat_precip", "ctrl_precip"]), month, n_days)
    training = [y for y in POOL if y != held_out]
    tr, te = sub[sub.season.isin(training)], sub[sub.season == held_out]
    scaler = StandardScaler()
    x, xt = scaler.fit_transform(tr[WARM_FEATURES].values), scaler.transform(te[WARM_FEATURES].values)
    wet = tr.treat_rain.to_numpy() == 1
    occurrence = LogisticRegressionCV(
        Cs=np.logspace(-3, 3, 30), cv=5, penalty="l2", scoring="roc_auc", max_iter=1000, random_state=42
    ).fit(x, tr.treat_rain)
    amount = RidgeCV(alphas=np.logspace(-3, 3, 50), cv=min(5, int(wet.sum()))).fit(
        x[wet], tr.treat_precip.to_numpy()[wet]
    )
    pred = occurrence.predict_proba(xt)[:, 1] * amount.predict(xt).clip(min=0)
    out = pd.DataFrame({"date": te.date.to_numpy(), "observed": te.treat_precip.to_numpy(),
                        "control": te.ctrl_precip.to_numpy(), "predicted": pred})
    return out, dict(alpha=float(amount.alpha_), logistic_C=float(occurrence.C_[0]),
                     n_training_days=len(tr), n_training_wet_days=int(wet.sum()))


def fit_ridge_swe(base, month, n_days, held_out):
    from sklearn.linear_model import RidgeCV
    from sklearn.preprocessing import StandardScaler
    from models.ridge_features import cold_features

    f, features = cold_features(base)
    sub = month_days(f.dropna(subset=features + ["treat_swe", "ctrl_swe"]), month, n_days)
    training = [y for y in POOL if y != held_out]
    tr, te = sub[sub.season.isin(training)], sub[sub.season == held_out]
    scaler = StandardScaler()
    x, xt = scaler.fit_transform(tr[features].values), scaler.transform(te[features].values)
    model = RidgeCV(alphas=np.logspace(-3, 3, 50), cv=5).fit(x, (tr.treat_swe - tr.ctrl_swe).values)
    pred = te.ctrl_swe.to_numpy() + model.predict(xt)
    out = pd.DataFrame({"date": te.date.to_numpy(), "observed": te.treat_swe.to_numpy(),
                        "control": te.ctrl_swe.to_numpy(), "predicted": pred})
    return out, dict(alpha=float(model.alpha_), n_training_days=len(tr))


def monthly_totals(base, month, n_days, convention):
    """One row per season: report-month precipitation total at target and control."""
    from models.ridge_features import warm_features

    f = warm_features(base, "published" if convention == "package" else "forward")
    sub = month_days(f, month, n_days)
    tot = sub.groupby("season")[["treat_precip", "ctrl_precip"]].sum(min_count=n_days)
    assert tot.notna().all().all()
    tot = tot.rename(columns={"treat_precip": "observed", "ctrl_precip": "control"}).reset_index()
    tot["date"] = [pd.Timestamp(int(s), month, 1) for s in tot.season]
    tot["month"] = month
    return tot


def fit_bsts_precip(base, month, n_days, held_out, convention, target):
    from models import bsts_warm_kernel as m

    m.TARGET_MONTHS = [month]  # one month offset; the sampler itself is unchanged
    f = monthly_totals(base, month, n_days, convention)
    training = [y for y in POOL if y != held_out]
    tr, te = f[f.season.isin(training)], f[f.season == held_out]
    starts = np.r_[True, np.diff(tr.season.to_numpy()) != 0]
    seed = 20261104 + target * 100 + held_out + 1000000 + month * 10000000
    np.random.seed(seed)
    n, burn = (m.N_ITER, m.N_BURNIN) if held_out == REPORT_YEAR else (m.LOSO_ITER, m.LOSO_BURNIN)
    dr = m.run_gibbs(tr.observed.to_numpy(), tr.month.to_numpy(), tr.control.to_numpy(), starts, n, burn,
                     verbose=False)
    coef = dr["coef"].mean(axis=0)
    X, names = m.design(te.month.to_numpy(), te.control.to_numpy())
    pred = m.nonneg(m.SEASON_START_MEAN + X @ coef)
    out = te[["date", "observed", "control"]].copy()
    out["predicted"] = pred
    return out, dict(seed=seed, iterations=n, burnin=burn, n_training_observations=len(tr),
                     coefficient_names=list(names), posterior_mean_coefficient=coef.tolist())


def fit_bsts_swe(base, month, n_days, held_out, target):
    from models import bsts_cold_kernel as m

    f = base[["date", "month", "treat_swe", "ctrl_swe"]].copy()
    for c in ("treat_swe", "ctrl_swe"):
        f[c] = f[c].astype(float).mask(lambda v: v < -50).clip(lower=0)
    f = month_days(f, month, n_days).rename(columns={"treat_swe": "observed", "ctrl_swe": "control"})
    assert f[["observed", "control"]].notna().all().all()
    training = [y for y in POOL if y != held_out]
    tr, te = f[f.season.isin(training)], f[f.season == held_out]
    starts = np.r_[True, np.diff(tr.season.to_numpy()) != 0]
    seed = 20261104 + target * 100 + held_out + month * 10000000
    np.random.seed(seed)
    n, burn = (m.N_ITER, m.N_BURNIN) if held_out == REPORT_YEAR else (m.LOSO_ITER, m.LOSO_BURNIN)
    dr = m.run_gibbs(tr.observed.to_numpy(), tr.control.to_numpy(), starts, n, burn, verbose=False)
    beta = float(dr["beta"].mean())
    out = te[["date", "observed", "control"]].copy()
    out["predicted"] = m.SEASON_START_MEAN + beta * te.control.to_numpy()
    return out, dict(seed=seed, iterations=n, burnin=burn, n_training_observations=len(tr),
                     posterior_mean_coefficient=beta)


def summarize(pred, outcome):
    """Package uncertainty.py logic for a single-month window."""
    agg = "mean" if outcome == "swe" else "sum"
    by = pred.groupby("season")[["observed", "control", "predicted", "departure"]].agg(agg)
    errors = by.loc[POOL, "departure"]
    assert len(errors) == len(POOL)
    c = by.loc[REPORT_YEAR]
    sd = float(errors.std(ddof=1))
    z = 1.96 if outcome == "swe" else float(norm.ppf(0.975))
    departure = float(c.observed - c.predicted)
    upper = departure + z * sd
    if outcome == "precip":
        upper = float(c.observed - max(0.0, c.predicted - z * sd))
    hist_ctrl = by.loc[POOL, "control"]
    return dict(
        observed=float(c.observed), control=float(c.control), predicted=float(c.predicted),
        departure=departure, lower95=departure - z * sd, upper95=upper,
        P_NR_positive=float(norm.cdf(departure / sd)) if sd > 0 else float("nan"),
        loso_error_sd=sd, loso_mean_error=float(errors.mean()),
        loso_error_min=float(errors.min()), loso_error_max=float(errors.max()),
        n_historical_errors_below_departure=int((errors < departure).sum()),
        n_historical_seasons=len(errors),
        control_historical_max=float(hist_ctrl.max()),
        control_ratio_to_historical_max=float(c.control / hist_ctrl.max()) if hist_ctrl.max() > 0 else float("nan"),
    ), errors


def main():
    global REPORT_YEAR
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--package", type=Path, required=True, help="Final_Model_Scripts folder")
    p.add_argument("--daily-csv", type=Path, required=True,
                   help="Wide daily download with <station>_<variable> columns covering the report month "
                        "and the first day of the next month")
    p.add_argument("--month", type=int, default=10)
    p.add_argument("--year", type=int, default=2026)
    p.add_argument("--precip-convention", choices=["full_month", "package", "both"], default="both")
    p.add_argument("--output-dir", type=Path, default=None)
    args = p.parse_args()
    REPORT_YEAR = args.year
    assert REPORT_YEAR not in POOL

    pkg = args.package.resolve()
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(pkg))
    # numpy/Accelerate emits spurious matmul RuntimeWarnings on this platform; results are checked below.
    warnings.filterwarnings("ignore")

    n_days = calendar.monthrange(args.year, args.month)[1]
    tag = f"{args.year}{args.month:02d}"
    dest = args.output_dir or Path(__file__).resolve().parent.parent / "output" / f"enhancement_{tag}"
    dest.mkdir(parents=True, exist_ok=True)
    conventions = ["full_month", "package"] if args.precip_convention == "both" else [args.precip_convention]

    jobs = [("Ridge", "precip", c) for c in conventions] + [("BSTS", "precip", c) for c in conventions]
    jobs += [("Ridge", "swe", "n/a"), ("BSTS", "swe", "n/a")]
    rows, frames, loso, settings = [], [], [], []
    for target in PAIRS:
        base = load_base(pkg, args.daily_csv, target, args.month, args.year)
        for model, outcome, conv in jobs:
            parts = []
            for held_out in [REPORT_YEAR] + POOL:
                if model == "Ridge" and outcome == "precip":
                    out, st = fit_ridge_precip(base, args.month, n_days, held_out, conv)
                elif model == "Ridge":
                    out, st = fit_ridge_swe(base, args.month, n_days, held_out)
                elif outcome == "precip":
                    out, st = fit_bsts_precip(base, args.month, n_days, held_out, conv, target)
                else:
                    out, st = fit_bsts_swe(base, args.month, n_days, held_out, target)
                assert np.isfinite(out.predicted).all(), (model, outcome, target, held_out)
                out["season"] = held_out
                parts.append(out)
                st.update(model=model, outcome=outcome, precip_convention=conv, target=target,
                          control=PAIRS[target], test_season=held_out,
                          training_seasons=[y for y in POOL if y != held_out])
                settings.append(st)
            pred = pd.concat(parts, ignore_index=True)
            pred["departure"] = pred.observed - pred.predicted
            result, errors = summarize(pred, outcome)
            key = dict(model=model, outcome=outcome, precip_convention=conv, target=target,
                       station=STATION[target], control_station=CONTROL[target])
            rows.append({**key, **result})
            frames.append(pred.assign(**key))
            loso.append(errors.rename("error").reset_index().assign(**key))
            print(f"{model:5s} {outcome:6s} {conv:10s} {STATION[target]}: observed {result['observed']:.2f}, "
                  f"predicted {result['predicted']:.2f}, departure {result['departure']:+.2f} "
                  f"[{result['lower95']:+.2f}, {result['upper95']:+.2f}], "
                  f"P_NR {result['P_NR_positive']:.3f}, LOSO SD {result['loso_error_sd']:.2f}", flush=True)

    pd.DataFrame(rows).to_csv(dest / "results.csv", index=False)
    pd.concat(frames, ignore_index=True).to_csv(dest / "predictions.csv", index=False)
    pd.concat(loso, ignore_index=True).to_csv(dest / "loso_errors.csv", index=False)
    (dest / "fit_settings.json").write_text(json.dumps(settings, indent=2))
    print(f"\nWrote {dest}")


if __name__ == "__main__":
    main()
