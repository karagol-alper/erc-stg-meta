"""
erc_meta.domains
================
Domain structure of StG competitions (Life Sciences, Physical Sciences &
Engineering, Social Sciences & Humanities).

1. Success-rate neutrality across domains.  The ERC allocates each panel's
   budget in proportion to the budget requested, which should equalise
   success rates across domains.  We test this per call (chi-square on the
   3 x 2 table) and pool the domain rate ratios (SH vs PE, LS vs PE) across
   calls with REML/HKSJ; the between-call heterogeneity of the ratio tells us
   whether departures from neutrality are systematic.
2. Domain shares of applications and grants over time (trend + permutation p).
3. Identification bounds for domain-specific gender effects.  Only the 2025
   call publishes grantees by domain x gender.  For any assumed within-domain
   women's share of applicants s_d the domain-specific OR is determined, and
   the shares are constrained to average to the call's overall women's share.
   We tabulate the ORs under three scenarios instead of pretending the
   applicant split is known.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from . import core
from .data import CALLS, CALLS_IMPUTED

DOMS = ["LS", "PE", "SH"]


def domain_frame(calls=None):
    calls = sorted(CALLS_IMPUTED + CALLS, key=lambda c: c.year) if calls is None else calls
    rows = []
    for c in calls:
        n = dict(LS=c.n_ls, PE=c.n_pe, SH=c.n_sh); g = dict(LS=c.g_ls, PE=c.g_pe, SH=c.g_sh)
        for d in DOMS:
            rows.append(dict(year=c.year, domain=d, apps=n[d], grants=g[d], sr=g[d] / n[d],
                             app_share=n[d] / c.n_total, grant_share=g[d] / c.g_total))
    return pd.DataFrame(rows)


def neutrality_tests(df):
    out = []
    for yr, g in df.groupby("year"):
        tab = np.array([[r.grants, r.apps - r.grants] for _, r in g.iterrows()])
        chi2, p, dof, _ = stats.chi2_contingency(tab)
        sr = g.set_index("domain").sr
        out.append(dict(year=yr, chi2=float(chi2), p=float(p), sr_LS=sr["LS"], sr_PE=sr["PE"], sr_SH=sr["SH"],
                        max_min_ratio=float(sr.max() / sr.min())))
    return pd.DataFrame(out)


def pooled_rate_ratio(df, num="SH", den="PE"):
    ys, vs, yrs = [], [], []
    for yr, g in df.groupby("year"):
        gg = g.set_index("domain")
        a, n1 = gg.loc[num, "grants"], gg.loc[num, "apps"]
        c, n2 = gg.loc[den, "grants"], gg.loc[den, "apps"]
        ys.append(np.log((a / n1) / (c / n2))); vs.append(1 / a - 1 / n1 + 1 / c - 1 / n2); yrs.append(yr)
    ys, vs = np.array(ys), np.array(vs)
    r = core.pool(ys, vs, "REML", hksj=True)
    X = np.column_stack([np.ones(len(ys)), np.array(yrs) - np.mean(yrs)])
    mr = core.meta_regression(ys, vs, X, n_perm=2000)
    return dict(contrast=f"{num} vs {den}", RR=float(np.exp(r.est)), lo=float(np.exp(r.ci_lo)), hi=float(np.exp(r.ci_hi)),
                p=r.p, tau2=r.tau2, I2=r.I2, Q_p=r.p_Q, pi_lo=float(np.exp(r.pi_lo)), pi_hi=float(np.exp(r.pi_hi)),
                trend_per_year=float(mr.beta[1]), trend_p=float(mr.p[1]), trend_perm_p=float(mr.perm_p),
                per_call=list(zip(yrs, np.exp(ys), np.exp(ys - 1.96 * np.sqrt(vs)), np.exp(ys + 1.96 * np.sqrt(vs)))))


def share_trends(df, n_perm=2000, seed=21):
    rng = np.random.default_rng(seed)
    out = {}
    for d in DOMS:
        s = df[df.domain == d].sort_values("year")
        x = s.year.values - s.year.mean(); y = s.app_share.values
        b = np.polyfit(x, y, 1)[0]
        cnt = 0
        for _ in range(n_perm):
            if abs(np.polyfit(rng.permutation(x), y, 1)[0]) >= abs(b) - 1e-12:
                cnt += 1
        out[d] = dict(slope_pp_per_year=float(100 * b), perm_p=(cnt + 1) / (n_perm + 1),
                      first=float(y[0]), last=float(y[-1]), first_year=int(s.year.iloc[0]), last_year=int(s.year.iloc[-1]))
    return out


def gender_by_domain_2025(scenarios=None):
    """Grantees by domain x gender in the 2025 call (F LS55/PE64/SH82; M LS79/PE133/SH59; NB excluded).
    Applicant shares by domain are not published; each scenario gives relative factors (LS, PE, SH) that are
    calibrated to the overall share of 40 %."""
    c = [x for x in CALLS if x.year == 2025][0]
    n = np.array([c.n_ls, c.n_pe, c.n_sh], float)
    F = np.array([55, 64, 82], float); M = np.array([79, 133, 59], float)
    if scenarios is None:
        scenarios = {"uniform (same share in every domain)": (1.0, 1.0, 1.0),
                     "central (LS 1.15, PE 0.75, SH 1.30)": (1.15, 0.75, 1.30),
                     "steep (LS 1.25, PE 0.65, SH 1.45)": (1.25, 0.65, 1.45)}
    rows = []
    for name, f in scenarios.items():
        f = np.array(f); kappa = c.share_w * n.sum() / np.sum(f * n); s = kappa * f
        nw = s * n; nm = n - nw
        for d, i in zip(DOMS, range(3)):
            a, b_, cc, dd = F[i], nw[i] - F[i], M[i], nm[i] - M[i]
            y, v = core.log_or(a, b_, cc, dd)
            rows.append(dict(scenario=name, domain=d, assumed_women_share=float(s[i]), women_funded=int(F[i]),
                             men_funded=int(M[i]), OR=float(np.exp(y)), lo=float(np.exp(y - 1.96 * np.sqrt(v))),
                             hi=float(np.exp(y + 1.96 * np.sqrt(v)))))
    # neutral shares: the applicant shares under which every domain OR would equal 1
    neutral = F / (F + M)
    return pd.DataFrame(rows), dict(zip(DOMS, neutral.round(4).tolist())), float(np.sum(neutral * n) / n.sum())


def run_domains():
    df = domain_frame()
    nt = neutrality_tests(df)
    rr_sh = pooled_rate_ratio(df, "SH", "PE"); rr_ls = pooled_rate_ratio(df, "LS", "PE")
    tr = share_trends(df)
    gd, neutral, neutral_overall = gender_by_domain_2025()
    return dict(frame=df, neutrality=nt, rr=[rr_sh, rr_ls], trends=tr, gender_domain=gd,
                summary=dict(k_calls=int(df.year.nunique()), n_calls_p_lt_05=int((nt.p < 0.05).sum()),
                             median_max_min_ratio=float(nt.max_min_ratio.median()),
                             max_max_min_ratio=float(nt.max_min_ratio.max()), year_max=int(nt.loc[nt.max_min_ratio.idxmax(), "year"]),
                             rr={r["contrast"]: {k: v for k, v in r.items() if k != "per_call"} for r in (rr_sh, rr_ls)},
                             app_share_trends=tr, gender_domain_neutral_shares_2025=neutral,
                             gender_domain_neutral_overall_2025=neutral_overall))


def domains_fig(dm, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    C = dict(LS="#2a9d8f", PE="#1f5f8b", SH="#b23a48")
    df = dm["frame"]
    fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.6))
    ax = axes[0]
    for d in DOMS:
        s = df[df.domain == d]
        lo, hi = zip(*[stats.beta.interval(0.95, g + 0.5, n - g + 0.5) for g, n in zip(s.grants, s.apps)])
        ax.errorbar(s.year, 100 * s.sr, yerr=[100 * (s.sr - np.array(lo)), 100 * (np.array(hi) - s.sr)], fmt="o-", color=C[d], ms=3, lw=1, capsize=1.5, label=d)
    ax.set_xlabel("call year"); ax.set_ylabel("success rate (%)"); ax.set_title("Success rate by domain (budget-proportional rule)", fontsize=8.5)
    ax.legend(frameon=False, fontsize=7)
    ax = axes[1]
    for r, col, off in zip(dm["rr"], ["#b23a48", "#2a9d8f"], [-0.15, 0.15]):
        yrs = [p[0] + off for p in r["per_call"]]; val = [p[1] for p in r["per_call"]]; lo = [p[2] for p in r["per_call"]]; hi = [p[3] for p in r["per_call"]]
        ax.errorbar(yrs, val, yerr=[np.subtract(val, lo), np.subtract(hi, val)], fmt="o", color=col, ms=3, capsize=1.5, lw=1,
                    label=f"{r['contrast']}: pooled RR {r['RR']:.2f} [{r['lo']:.2f}, {r['hi']:.2f}], I² {100 * r['I2']:.0f}%")
        ax.axhline(r["RR"], color=col, lw=0.8, ls="--")
    ax.axhline(1, color="black", lw=0.8)
    ax.set_yscale("log"); ax.set_yticks([0.7, 0.85, 1, 1.2, 1.4]); ax.set_yticklabels(["0.7", "0.85", "1", "1.2", "1.4"])
    ax.set_xlabel("call year"); ax.set_ylabel("success-rate ratio (log scale)"); ax.set_title("Domain rate ratios per call", fontsize=8.5)
    ax.legend(frameon=False, fontsize=6)
    ax = axes[2]
    for d in DOMS:
        s = df[df.domain == d]
        ax.plot(s.year, 100 * s.app_share, "o-", color=C[d], ms=3, lw=1.2, label=f"{d}: {dm['trends'][d]['slope_pp_per_year']:+.2f} pp/yr (perm. p {dm['trends'][d]['perm_p']:.2f})")
    ax.set_xlabel("call year"); ax.set_ylabel("share of evaluated proposals (%)"); ax.set_title("Where the demand comes from", fontsize=8.5)
    ax.legend(frameon=False, fontsize=6)
    fig.tight_layout(); fig.savefig(path, dpi=170); plt.close(fig)
