"""
erc_meta.dynamics
=================
Competition dynamics of the ERC Starting Grant scheme.

1. Success-rate meta-analysis: the per-call success rate is pooled on the
   logit scale (REML random effects, HKSJ) and its between-call spread is
   summarised as a prediction interval and as pairwise "cohort odds ratios":
   the odds that an applicant of fixed quality is funded in call A relative
   to call B.  This quantifies "cohort luck".
2. Decomposition of consecutive changes in the success rate into the supply
   (grants) and demand (applications) components:
       dlog(SR) = dlog(G) - dlog(N).
3. Demand elasticity: dlog(N_t) regressed on dlog(SR_{t-1}) (the success rate
   of the previous call is public when the next call's proposals are written)
   with a permutation test, run on the fully verified series and on the
   extended series.
4. Application cost ("application tax"): person-years of proposal preparation
   per call under explicit assumptions about days per proposal, compared with
   the person-years of PI time the scheme funds.
5. Women's share of applicants: weighted linear trend with the rounding
   interval treated as measurement error; projected year at which the
   applicant pool would reach parity, with a delta-method interval; and the
   per-call representation gap (grantee share minus applicant share).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from . import core
from .data import COMPETITION_SERIES, CALLS

DAYS_PER_YEAR = 220.0


def series_frame(verified_only=False):
    df = pd.DataFrame(COMPETITION_SERIES, columns=["year", "apps", "grants", "budget_meur", "status"])
    df["verified"] = df.status.str.startswith("verified")
    if verified_only:
        df = df[df.verified].reset_index(drop=True)
    df["sr"] = df.grants / df.apps
    lo, hi = zip(*[_wilson(g, n) for g, n in zip(df.grants, df.apps)])
    df["sr_lo"], df["sr_hi"] = lo, hi
    return df


def _wilson(x, n, z=1.96):
    p = x / n
    den = 1 + z ** 2 / n
    ctr = (p + z ** 2 / (2 * n)) / den
    half = z * np.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / den
    return ctr - half, ctr + half


def success_rate_meta(df):
    y = np.log(df.grants / (df.apps - df.grants))
    v = 1 / df.grants + 1 / (df.apps - df.grants)
    r = core.pool(y.values, v.values, "REML", hksj=True)
    inv = lambda z: 1 / (1 + np.exp(-z))
    # pairwise cohort ORs
    yrs = df.year.values
    mat = pd.DataFrame(np.exp(y.values[:, None] - y.values[None, :]), index=yrs, columns=yrs)
    return dict(pooled=float(inv(r.est)), lo=float(inv(r.ci_lo)), hi=float(inv(r.ci_hi)), pi_lo=float(inv(r.pi_lo)),
                pi_hi=float(inv(r.pi_hi)), tau=float(np.sqrt(r.tau2)), I2=r.I2, Q=r.Q,
                cohort_or_max=float(mat.values.max()), cohort_or_min=float(mat.values.min()),
                cohort_or=mat, y=y.values, v=v.values)


def decomposition(df):
    d = df.copy()
    d["dlogN"] = np.log(d.apps).diff()
    d["dlogG"] = np.log(d.grants).diff()
    d["dlogSR"] = d.dlogG - d.dlogN
    d["demand_share_of_change"] = np.where(d.dlogSR.abs() > 1e-9, -d.dlogN / d.dlogSR, np.nan)
    return d.iloc[1:][["year", "apps", "grants", "sr", "dlogN", "dlogG", "dlogSR", "demand_share_of_change"]]


def demand_elasticity(df, n_perm=5000, seed=5):
    """dlog N_t = a + b * dlog SR_{t-1}; OLS with HC1 SE and a permutation test on b."""
    d = df.sort_values("year").reset_index(drop=True)
    dlogN = np.log(d.apps).diff().values
    dlogSR = np.log(d.sr).diff().values
    yv = dlogN[2:]
    xv = dlogSR[1:-1]           # previous call's change in success rate
    X = np.column_stack([np.ones_like(xv), xv])
    beta = np.linalg.lstsq(X, yv, rcond=None)[0]
    resid = yv - X @ beta
    n, p = X.shape
    XtX_inv = np.linalg.inv(X.T @ X)
    # HC1 robust covariance
    meat = (X * resid[:, None] ** 2).T @ X
    cov = XtX_inv @ meat @ XtX_inv * n / (n - p)
    se = np.sqrt(np.diag(cov))
    t = beta / se
    pval = 2 * stats.t.sf(np.abs(t), n - p)
    rng = np.random.default_rng(seed)
    cnt = 0
    for _ in range(n_perm):
        Xp = np.column_stack([np.ones_like(xv), rng.permutation(xv)])
        bp = np.linalg.lstsq(Xp, yv, rcond=None)[0]
        if abs(bp[1]) >= abs(beta[1]) - 1e-12:
            cnt += 1
    r2 = 1 - np.sum(resid ** 2) / np.sum((yv - yv.mean()) ** 2)
    return dict(elasticity=float(beta[1]), se=float(se[1]), t=float(t[1]), p=float(pval[1]),
                perm_p=(cnt + 1) / (n_perm + 1), n=int(n), r2=float(r2), intercept=float(beta[0]),
                x=xv, y=yv, years=d.year.values[2:])


def application_tax(df, days_per_proposal=(20, 34, 50), grant_years=5.0):
    rows = []
    for _, r in df.iterrows():
        for dpp in days_per_proposal:
            py = r.apps * dpp / DAYS_PER_YEAR
            rows.append(dict(year=int(r.year), days_per_proposal=dpp, applicant_person_years=py,
                             person_years_per_grant=py / r.grants, funded_pi_years=r.grants * grant_years,
                             tax_ratio=py / (r.grants * grant_years)))
    return pd.DataFrame(rows)


def women_share_trend(calls=None, target=0.5, n_boot=5000, seed=9):
    calls = CALLS if calls is None else calls
    yr = np.array([c.year for c in calls], float)
    mid = np.array([c.share_w for c in calls])
    half = np.array([(c.share_w_hi - c.share_w_lo) / 200 for c in calls])
    sd_me = half * 2 / np.sqrt(12)                 # uniform rounding interval -> sd
    X = np.column_stack([np.ones_like(yr), yr - yr.mean()])
    beta = np.linalg.lstsq(X, mid, rcond=None)[0]
    resid = mid - X @ beta
    s2 = np.sum(resid ** 2) / (len(yr) - 2)
    cov = np.linalg.inv(X.T @ X) * s2
    se_slope = np.sqrt(cov[1, 1])
    t = beta[1] / se_slope
    p = 2 * stats.t.sf(abs(t), len(yr) - 2)
    # bootstrap the parity year, adding rounding measurement error to each call's share
    rng = np.random.default_rng(seed)
    parity = []
    for _ in range(n_boot):
        yb = mid + rng.uniform(-half, half) + rng.normal(0, np.sqrt(s2), len(yr))
        bb = np.linalg.lstsq(X, yb, rcond=None)[0]
        if bb[1] > 0:
            parity.append(yr.mean() + (target - bb[0]) / bb[1])
    parity = np.array(parity)
    point = yr.mean() + (target - beta[0]) / beta[1] if beta[1] > 0 else np.nan
    # grantee share trend
    gsh = np.array([c.g_female / (c.g_female + c.g_male) for c in calls])
    bg = np.linalg.lstsq(X, gsh, rcond=None)[0]
    gap = gsh - mid
    gap_se = np.sqrt(gsh * (1 - gsh) / np.array([c.g_female + c.g_male for c in calls]) + sd_me ** 2)
    return dict(slope_pp_per_year=float(100 * beta[1]), slope_se_pp=float(100 * se_slope), p=float(p),
                intercept_at_mean_year=float(beta[0]), mean_year=float(yr.mean()), parity_year_point=float(point),
                parity_year_ci=[float(np.percentile(parity, 2.5)), float(np.percentile(parity, 97.5))],
                parity_prob_before_2035=float(np.mean(parity < 2035)),
                grantee_slope_pp_per_year=float(100 * bg[1]),
                gap_table=pd.DataFrame(dict(year=yr.astype(int), applicant_share=mid, grantee_share=gsh, gap_pp=100 * gap,
                                            gap_lo_pp=100 * (gap - 1.96 * gap_se), gap_hi_pp=100 * (gap + 1.96 * gap_se))),
                fitted=(yr, X @ beta), resid_sd=float(np.sqrt(s2)))


def run_dynamics(n_perm=5000):
    full = series_frame()
    ver = series_frame(verified_only=True)
    sr_meta = success_rate_meta(ver)
    dec = decomposition(full)
    el_ver = demand_elasticity(ver, n_perm=n_perm)
    el_full = demand_elasticity(full, n_perm=n_perm)
    tax = application_tax(full)
    wt = women_share_trend()
    last = dec.iloc[-1]
    return dict(series=full, verified=ver, sr_meta=sr_meta, decomposition=dec, elasticity_verified=el_ver,
                elasticity_full=el_full, tax=tax, women=wt,
                summary=dict(
                    success_rate_pooled=sr_meta["pooled"], success_rate_ci=[sr_meta["lo"], sr_meta["hi"]],
                    success_rate_pi=[sr_meta["pi_lo"], sr_meta["pi_hi"]], success_rate_tau_logit=sr_meta["tau"],
                    success_rate_I2=sr_meta["I2"], cohort_or_range=[sr_meta["cohort_or_min"], sr_meta["cohort_or_max"]],
                    cohort_or_2026_vs_2024=float(sr_meta["cohort_or"].loc[2026, 2024]),
                    cohort_or_2026_vs_2023=float(sr_meta["cohort_or"].loc[2026, 2023]),
                    last_change=dict(year=int(last.year), dlogN=float(last.dlogN), dlogG=float(last.dlogG),
                                     dlogSR=float(last.dlogSR), demand_share=float(last.demand_share_of_change)),
                    elasticity_verified={k: v for k, v in el_ver.items() if k not in ("x", "y", "years")},
                    elasticity_full={k: v for k, v in el_full.items() if k not in ("x", "y", "years")},
                    tax_2026=tax[(tax.year == 2026)].set_index("days_per_proposal")[["applicant_person_years", "person_years_per_grant", "tax_ratio"]].to_dict("index"),
                    women_share_slope_pp_per_year=wt["slope_pp_per_year"], women_share_slope_se=wt["slope_se_pp"],
                    women_share_trend_p=wt["p"], parity_year_point=wt["parity_year_point"], parity_year_ci=wt["parity_year_ci"],
                    parity_prob_before_2035=wt["parity_prob_before_2035"], grantee_share_slope_pp_per_year=wt["grantee_slope_pp_per_year"]))


def dynamics_fig(dyn, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    C_W, C_M, C_RE, C_FE, C_GREY = "#b23a48", "#1f5f8b", "#2a9d8f", "#e9c46a", "#7a7a7a"
    full, ver, sm = dyn["series"], dyn["verified"], dyn["sr_meta"]
    fig, axes = plt.subplots(2, 2, figsize=(9.5, 6.8))
    ax = axes[0, 0]
    ax2 = ax.twinx()
    cols = np.where(full.verified, C_M, C_GREY)
    ax2.bar(full.year, full.apps, color=cols, alpha=0.25, width=0.8)
    ax2.set_ylabel("evaluated proposals (bars; grey = partly recalled)", fontsize=7.5)
    ax.errorbar(full.year, 100 * full.sr, yerr=[100 * (full.sr - full.sr_lo), 100 * (full.sr_hi - full.sr)], fmt="o-",
                color=C_RE, ms=3.5, capsize=2, lw=1.2, zorder=3)
    ax.axhspan(100 * sm["pi_lo"], 100 * sm["pi_hi"], color=C_RE, alpha=0.12)
    ax.axhline(100 * sm["pooled"], color=C_RE, lw=0.8, ls="--")
    ax.set_ylabel("success rate (%) with 95% CI"); ax.set_xlabel("call year")
    ax.set_xticks([2007, 2010, 2013, 2016, 2019, 2022, 2025])
    ax.set_title(f"Success rate: pooled {100 * sm['pooled']:.1f}%, prediction interval {100 * sm['pi_lo']:.1f}–{100 * sm['pi_hi']:.1f}%", fontsize=8.5)
    ax.set_zorder(ax2.get_zorder() + 1); ax.patch.set_visible(False)
    ax = axes[0, 1]
    dec = dyn["decomposition"]
    ax.bar(dec.year - 0.2, 100 * dec.dlogG, width=0.4, color=C_FE, label="Δlog grants (supply)")
    ax.bar(dec.year + 0.2, -100 * dec.dlogN, width=0.4, color=C_M, label="−Δlog applications (demand)")
    ax.plot(dec.year, 100 * dec.dlogSR, "k.-", lw=1, ms=4, label="Δlog success rate")
    ax.axhline(0, color="black", lw=0.6)
    ax.set_ylabel("log change × 100 (≈ % change)"); ax.set_xlabel("call year")
    ax.set_xticks([2009, 2012, 2015, 2018, 2021, 2024])
    ax.set_title("What moves the success rate: supply vs demand", fontsize=8.5)
    ax.legend(frameon=False, fontsize=6.5)
    ax = axes[1, 0]
    el = dyn["elasticity_verified"]
    ax.scatter(100 * el["x"], 100 * el["y"], color=C_RE, edgecolor="black", s=30)
    for xx, yy, yr in zip(el["x"], el["y"], el["years"]):
        ax.annotate(str(int(yr)), (100 * xx, 100 * yy), fontsize=6, xytext=(3, 3), textcoords="offset points")
    xs = np.linspace(min(el["x"]), max(el["x"]), 50)
    ax.plot(100 * xs, 100 * (el["intercept"] + el["elasticity"] * xs), color=C_W, lw=1.3)
    ax.axhline(0, color="black", lw=0.6); ax.axvline(0, color="black", lw=0.6)
    ax.set_xlabel("previous call: Δlog success rate × 100"); ax.set_ylabel("this call: Δlog applications × 100")
    ax.set_title(f"Demand response: elasticity {el['elasticity']:+.2f} (perm. p = {el['perm_p']:.2f}, n = {el['n']})", fontsize=8.5)
    ax = axes[1, 1]
    wt = dyn["women"]
    yr, fit = wt["fitted"]
    mid = np.array([c.share_w for c in CALLS]); lo = np.array([c.share_w_lo / 100 for c in CALLS]); hi = np.array([c.share_w_hi / 100 for c in CALLS])
    ax.errorbar(yr, 100 * mid, yerr=[100 * (mid - lo), 100 * (hi - mid)], fmt="o", color=C_W, ms=4, capsize=2, label="women's share of proposals (interval = ERC rounding)")
    ax.plot(yr, 100 * fit, color=C_W, lw=1.2)
    gsh = wt["gap_table"].grantee_share.values
    ax.plot(yr, 100 * gsh, "s--", color=C_RE, ms=3.5, lw=1, label="women's share of grantees")
    ax.axhline(50, color=C_GREY, lw=0.8, ls=":")
    ax.set_ylim(30, 52); ax.set_xlabel("call year"); ax.set_ylabel("%")
    ax.set_title(f"Women's share: {wt['slope_pp_per_year']:+.2f} pp/yr; parity ≈ {wt['parity_year_point']:.0f} "
                 f"({wt['parity_year_ci'][0]:.0f}–{wt['parity_year_ci'][1]:.0f})", fontsize=8.5)
    ax.legend(frameon=False, fontsize=6.5, loc="upper left")
    fig.tight_layout(); fig.savefig(path, dpi=170); plt.close(fig)
