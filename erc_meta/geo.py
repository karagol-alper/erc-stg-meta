"""
erc_meta.geo
============
Geographic distribution of StG grants by country of host institution.

The ERC publishes grantee counts by host country for every call but not the
applicant counts by country; hence success rates by country cannot be
computed from the public per-call statistics.  We therefore analyse

1. the share of grants hosted in Horizon-Europe "widening" countries
   (proportion meta-analysis on the logit scale, exact Clopper-Pearson CIs,
   REML random effects with HKSJ, secular trend);
2. standardised grant ratios (SGR = observed / expected grants, the direct
   analogue of an SMR) under explicit scenarios for the widening countries'
   share of the applicant pool - a sensitivity analysis over the unobserved
   denominator - with Poisson (Garwood) exact CIs and log-SGR pooling;
3. concentration of grants across host countries (Gini, Herfindahl-Hirschman
   index, top-3 / top-5 shares).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from . import core
from .data import host_country_frame


def clopper_pearson(x, n, alpha=0.05):
    lo = stats.beta.ppf(alpha / 2, x, n - x + 1) if x > 0 else 0.0
    hi = stats.beta.ppf(1 - alpha / 2, x + 1, n - x) if x < n else 1.0
    return lo, hi


def garwood(x, alpha=0.05):
    lo = stats.chi2.ppf(alpha / 2, 2 * x) / 2 if x > 0 else 0.0
    hi = stats.chi2.ppf(1 - alpha / 2, 2 * (x + 1)) / 2
    return lo, hi


def gini(x):
    x = np.sort(np.asarray(x, float))
    n = len(x)
    return float((2 * np.sum(np.arange(1, n + 1) * x) / (n * x.sum())) - (n + 1) / n)


def widening_table(which="widening_eu"):
    hc = host_country_frame()
    rows = []
    for yr, g in hc.groupby("year"):
        tot = int(g.grants.sum())
        x = int(g.loc[g[which], "grants"].sum())
        lo, hi = clopper_pearson(x, tot)
        sh = np.sort(g.grants.values)[::-1] / tot
        rows.append(dict(year=yr, grants_total=tot, grants_widening=x, share=x / tot, lo=lo, hi=hi,
                         n_countries=len(g), gini=gini(g.grants.values), hhi=float(np.sum(sh ** 2)),
                         top3=float(sh[:3].sum()), top5=float(sh[:5].sum())))
    return pd.DataFrame(rows)


def pool_share(tab, hksj=True):
    x, n = tab.grants_widening.values.astype(float), tab.grants_total.values.astype(float)
    y = np.log(x / (n - x))
    v = 1 / x + 1 / (n - x)
    r = core.pool(y, v, "REML", hksj=hksj)
    X = np.column_stack([np.ones(len(y)), tab.year.values - tab.year.mean()])
    mr = core.meta_regression(y, v, X, names=["int", "year"], n_perm=2000)
    inv = lambda z: 1 / (1 + np.exp(-z))
    return dict(share=float(inv(r.est)), lo=float(inv(r.ci_lo)), hi=float(inv(r.ci_hi)), tau2=r.tau2, I2=r.I2,
                Q=r.Q, p_Q=r.p_Q, pi_lo=float(inv(r.pi_lo)), pi_hi=float(inv(r.pi_hi)),
                trend_beta=float(mr.beta[1]), trend_se=float(mr.se[1]), trend_p=float(mr.p[1]),
                trend_perm_p=float(mr.perm_p), y=y, v=v)


def sgr_scenarios(tab, applicant_shares=(0.10, 0.125, 0.15, 0.25)):
    """Standardised grant ratio per call and pooled, for assumed widening shares of applicants."""
    out = []
    for s in applicant_shares:
        exp_ = tab.grants_total.values * s
        obs = tab.grants_widening.values.astype(float)
        sgr = obs / exp_
        ci = np.array([garwood(int(o)) for o in obs]) / exp_[:, None]
        y, v = np.log(sgr), 1 / obs
        r = core.pool(y, v, "REML", hksj=True)
        out.append(dict(applicant_share=s, sgr_pooled=float(np.exp(r.est)), lo=float(np.exp(r.ci_lo)),
                        hi=float(np.exp(r.ci_hi)), I2=r.I2, per_call=list(zip(tab.year, sgr, ci[:, 0], ci[:, 1]))))
    return out


def implied_success_ratio(share_grants, share_apps):
    """If widening countries hold share s_a of applications and s_g of grants, their success rate
    relative to the rest is  RR = [s_g/s_a] / [(1-s_g)/(1-s_a)]."""
    return (share_grants / share_apps) / ((1 - share_grants) / (1 - share_apps))


# --------------------------------------------------------------------------- #
# Country shares over time, association-status shocks, rank stability, reallocation
# --------------------------------------------------------------------------- #
FOCUS = ["DE", "UK", "NL", "FR", "CH", "IL", "IT", "ES"]

# Framework-association status of the two associated countries whose status changed:
# UK: associated under Horizon 2020 (calls <= 2020); not associated for the 2021-2023 Horizon Europe calls
#     (UK-hosted proposals evaluated, funded under the UKRI guarantee); associated again from the 2024 call.
# CH: associated under Horizon 2020; non-associated 2021-2024 (Swiss host institutions ineligible in the 2024 call);
#     transitional association restored for the 2025 call.
PERIODS = {"UK": lambda y: "H2020 associated" if y <= 2020 else ("2021-23 non-associated (guarantee)" if y <= 2023 else "2024+ re-associated"),
           "CH": lambda y: "H2020 associated" if y <= 2020 else ("2021-23 non-associated (hosts eligible at submission)" if y <= 2023
                                                                  else ("2024 hosts ineligible" if y == 2024 else "2025+ transitional association"))}


def country_share_table(countries=FOCUS):
    hc = host_country_frame()
    tot = hc.groupby("year").grants.sum()
    rows = []
    for yr in sorted(hc.year.unique()):
        for cc in countries:
            x = int(hc[(hc.year == yr) & (hc.country == cc)].grants.sum())
            lo, hi = clopper_pearson(x, int(tot[yr]))
            rows.append(dict(year=yr, country=cc, grants=x, total=int(tot[yr]), share=x / tot[yr], lo=lo, hi=hi))
    return pd.DataFrame(rows)


def period_contrast(tab, country, n_perm=3000, seed=17):
    """Logit-scale meta-regression of a country's share on period indicators (Knapp-Hartung + permutation)."""
    s = tab[tab.country == country].sort_values("year").reset_index(drop=True)
    per = s.year.map(PERIODS[country])
    levels = list(dict.fromkeys(per))
    x, n = s.grants.values.astype(float), s.total.values.astype(float)
    cc = 0.5 * (x == 0)                       # continuity correction only where a count is zero
    y = np.log((x + cc) / (n - x + cc))
    v = 1 / (x + cc) + 1 / (n - x + cc)
    X = np.column_stack([np.ones(len(y))] + [(per == lv).astype(float).values for lv in levels[1:]])
    mr = core.meta_regression(y, v, X, names=["intercept"] + levels[1:], n_perm=0)
    # permutation test on the first contrast (shuffle period labels across calls)
    rng = np.random.default_rng(seed)
    t_obs = abs(mr.t[1]); cnt = 0
    lab = per.values.copy()
    for _ in range(n_perm):
        lp = rng.permutation(lab)
        Xp = np.column_stack([np.ones(len(y))] + [(lp == lv).astype(float) for lv in levels[1:]])
        try:
            mp = core.meta_regression(y, v, Xp, n_perm=0)
            if abs(mp.t[1]) >= t_obs - 1e-12:
                cnt += 1
        except np.linalg.LinAlgError:
            cnt += 1
    inv = lambda z: 1 / (1 + np.exp(-z))
    base = inv(mr.beta[0])
    out = dict(country=country, baseline_period=levels[0], baseline_share=float(base), tau2=mr.tau2, contrasts=[])
    for j, lv in enumerate(levels[1:], start=1):
        out["contrasts"].append(dict(period=lv, odds_ratio=float(np.exp(mr.beta[j])), lo=float(np.exp(mr.ci_lo[j])),
                                     hi=float(np.exp(mr.ci_hi[j])), p_KH=float(mr.p[j]),
                                     share=float(inv(mr.beta[0] + mr.beta[j]))))
    out["perm_p_first_contrast"] = (cnt + 1) / (n_perm + 1)
    return out


def rank_stability():
    hc = host_country_frame()
    piv = hc.pivot_table(index="country", columns="year", values="grants", fill_value=0)
    yrs = sorted(piv.columns)
    rows = []
    for a, b in zip(yrs[:-1], yrs[1:]):
        rho, p = stats.spearmanr(piv[a], piv[b])
        rows.append(dict(from_year=a, to_year=b, spearman=float(rho), p=float(p)))
    first, last = piv[yrs[0]], piv[yrs[-1]]
    rho_fl, p_fl = stats.spearmanr(first, last)
    return pd.DataFrame(rows), dict(first_last_spearman=float(rho_fl), p=float(p_fl), years=[yrs[0], yrs[-1]])


def reallocation_to_parity(tab, applicant_shares=(0.10, 0.125, 0.15)):
    """Grants per call that would have to move to widening hosts for the share of grants to equal the applicant share."""
    rows = []
    for s in applicant_shares:
        need = tab.grants_total * s - tab.grants_widening
        rows.append(dict(applicant_share=s, mean_extra_grants_per_call=float(need.mean()),
                         share_of_all_grants=float(need.sum() / tab.grants_total.sum()),
                         total_extra_grants_10_calls=float(need.sum())))
    return pd.DataFrame(rows)


def country_fig(tab, contrasts, gini_tab, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    cols = {"DE": "#1f5f8b", "UK": "#b23a48", "NL": "#2a9d8f", "FR": "#e9c46a", "CH": "#7a7a7a", "IL": "#8e44ad", "IT": "#e67e22", "ES": "#16a085"}
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.9), gridspec_kw=dict(width_ratios=[1.45, 1.15, 0.95]))
    ax = axes[0]
    for cc in ["DE", "UK", "NL", "FR", "CH", "IL"]:
        s = tab[tab.country == cc]
        ax.errorbar(s.year, 100 * s.share, yerr=[100 * (s.share - s.lo), 100 * (s.hi - s.share)], fmt="o-", color=cols[cc], ms=3, lw=1.1, capsize=1.5, label=cc)
    ax.axvspan(2020.5, 2023.5, color="#b23a48", alpha=0.07); ax.text(2020.7, 27.2, "UK not associated", fontsize=6, color="#b23a48")
    ax.axvspan(2023.5, 2024.5, color="grey", alpha=0.18); ax.text(2023.6, 25.6, "CH hosts\nineligible", fontsize=6, color="grey")
    ax.set_ylim(0, 29); ax.set_xlabel("call year"); ax.set_ylabel("% of StG grants hosted"); ax.set_title("Host-country shares and association status", fontsize=8.5)
    ax.set_xticks([2013, 2015, 2017, 2019, 2021, 2023, 2025])
    ax.legend(frameon=False, fontsize=6.5, ncol=6, loc="lower left", columnspacing=0.8, handlelength=1.2)
    ax = axes[1]
    labels, vals, los, his = [], [], [], []
    short = {"2021-23 non-associated (guarantee)": "UK 2021–23\n(not associated; UKRI guarantee)",
             "2024+ re-associated": "UK 2024–26\n(re-associated)",
             "2021-23 non-associated (hosts eligible at submission)": "CH 2021\n(not associated; hosts eligible)",
             "2024 hosts ineligible": "CH 2024\n(hosts ineligible: 0 grants)",
             "2025+ transitional association": "CH 2025–26\n(transitional association)"}
    for c in contrasts:
        for k in c["contrasts"]:
            labels.append(short.get(k["period"], k["period"])); vals.append(k["odds_ratio"]); los.append(k["lo"]); his.append(k["hi"])
    yy = np.arange(len(vals))[::-1]
    vals_p, los_p, his_p = np.clip(vals, 0.2, 3), np.clip(los, 0.2, 3), np.clip(his, 0.2, 3)
    ax.errorbar(vals_p, yy, xerr=[vals_p - los_p, his_p - vals_p], fmt="o", color="#1f5f8b", capsize=3)
    for v_, y_ in zip(vals, yy):
        if v_ < 0.2:
            ax.annotate(f"OR ≈ {v_:.2f} (off scale)", (0.36, y_ + 0.22), fontsize=6, va="bottom", color="#1f5f8b",
                        bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none"))
    ax.axvline(1, color="black", lw=0.8); ax.set_xscale("log"); ax.set_xlim(0.2, 2.2)
    ax.set_xticks([0.25, 0.5, 0.7, 1, 1.5, 2]); ax.set_xticklabels(["0.25", "0.5", "0.7", "1", "1.5", "2"])
    ax.set_yticks(yy); ax.set_yticklabels(labels, fontsize=6.3); ax.set_xlabel("odds ratio of hosting a grant vs the H2020 period")
    ax.set_title("Association shocks (logit meta-regression, KH 95% CI)", fontsize=8.5)
    ax = axes[2]
    ax.plot(gini_tab.year, gini_tab.gini, "o-", color="#b23a48", ms=3, label="Gini across host countries")
    ax.plot(gini_tab.year, gini_tab.top5, "s-", color="#1f5f8b", ms=3, label="top-5 country share")
    ax.plot(gini_tab.year, gini_tab.n_countries / 30, "^-", color="#2a9d8f", ms=3, label="host countries / 30")
    ax.set_ylim(0.3, 1.0); ax.set_xlabel("call year"); ax.set_title("Concentration", fontsize=8.5); ax.legend(frameon=False, fontsize=6.5, loc="lower left")
    fig.tight_layout(); fig.savefig(path, dpi=170); plt.close(fig)
