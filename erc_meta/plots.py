"""
erc_meta.plots
==============
Publication-style figures (matplotlib only).
"""
from __future__ import annotations

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from scipy import stats

C_W, C_M, C_RE, C_FE, C_GREY = "#b23a48", "#1f5f8b", "#2a9d8f", "#e9c46a", "#7a7a7a"
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                     "figure.dpi": 170, "savefig.dpi": 170, "axes.titleweight": "bold"})


def _wilson(x, n, z=1.96):
    p = x / n
    den = 1 + z ** 2 / n
    ctr = (p + z ** 2 / (2 * n)) / den
    half = z * np.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / den
    return ctr - half, ctr + half


# --------------------------------------------------------------------------- #
def forest(df, y, v, res_re, res_fe, path, title="ERC Starting Grants: odds of funding, women vs men"):
    from matplotlib.ticker import NullFormatter, FixedLocator
    k = len(y)
    or_, lo, hi = np.exp(y), np.exp(y - 1.96 * np.sqrt(v)), np.exp(y + 1.96 * np.sqrt(v))
    w = res_re.weights * 100
    fig = plt.figure(figsize=(8.2, 5.4))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.15, 1.35, 1.0], wspace=0.02, left=0.02, right=0.98, top=0.90, bottom=0.14)
    axl, ax, axr = fig.add_subplot(gs[0]), fig.add_subplot(gs[1]), fig.add_subplot(gs[2])
    ys = np.arange(k)[::-1] + 2
    ylim = (-0.3, k + 3.2)
    for a_ in (axl, axr):
        a_.set_xlim(0, 1); a_.set_ylim(*ylim); a_.axis("off")
    # left text columns
    axl.text(0.02, k + 2.4, "Call", fontsize=8.5, fontweight="bold")
    axl.text(0.30, k + 2.4, "Women\nfunded / applied", fontsize=7.5, fontweight="bold", color=C_W, va="center")
    axl.text(0.63, k + 2.4, "Men\nfunded / applied", fontsize=7.5, fontweight="bold", color=C_M, va="center")
    for i in range(k):
        axl.text(0.02, ys[i], f"{df.year.iloc[i]}", va="center", fontsize=8.5)
        axl.text(0.30, ys[i], f"{df.a.iloc[i]} / {df.n_w.iloc[i]}", va="center", fontsize=7.8, color=C_W)
        axl.text(0.63, ys[i], f"{df.c.iloc[i]} / {df.n_m.iloc[i]}", va="center", fontsize=7.8, color=C_M)
    # right text columns
    axr.text(0.06, k + 2.4, "OR [95% CI]", fontsize=8.5, fontweight="bold", va="center")
    axr.text(0.78, k + 2.4, "Weight", fontsize=8.5, fontweight="bold", va="center")
    for i in range(k):
        axr.text(0.06, ys[i], f"{or_[i]:.2f} [{lo[i]:.2f}, {hi[i]:.2f}]", va="center", fontsize=7.8)
        axr.text(0.78, ys[i], f"{w[i]:.1f}%", va="center", fontsize=7.8)
    # plot
    ax.errorbar(or_, ys, xerr=[or_ - lo, hi - or_], fmt="none", ecolor="black", elinewidth=1, capsize=2)
    ax.scatter(or_, ys, s=20 + 6 * w, marker="s", color=C_RE, zorder=3, edgecolor="black", linewidth=0.5)
    for yy, r, lab, col in [(1.0, res_re, "Random effects (REML, HKSJ)", C_RE), (0.2, res_fe, "Common effect (Mantel-Haenszel)", C_FE)]:
        e, l, h = np.exp(r.est), np.exp(r.ci_lo), np.exp(r.ci_hi)
        ax.add_patch(Polygon([[l, yy], [e, yy + 0.28], [h, yy], [e, yy - 0.28]], closed=True, color=col, alpha=0.9))
        axl.text(0.02, yy, lab, va="center", fontsize=7.8, fontweight="bold")
        axr.text(0.06, yy, f"{e:.3f} [{l:.3f}, {h:.3f}]", va="center", fontsize=7.8, fontweight="bold")
    if np.isfinite(res_re.pi_lo):
        ax.plot([np.exp(res_re.pi_lo), np.exp(res_re.pi_hi)], [1.0, 1.0], color=C_RE, lw=1.3, ls=":")
        axr.text(0.06, 0.6, f"95% prediction interval [{np.exp(res_re.pi_lo):.3f}, {np.exp(res_re.pi_hi):.3f}]", fontsize=7, color=C_RE, va="center")
    ax.axvline(1, color="black", lw=0.8)
    ax.axvline(np.exp(res_re.est), color=C_RE, lw=0.8, ls="--")
    ax.set_xscale("log")
    ax.set_xlim(0.62, 1.65)
    ax.xaxis.set_major_locator(FixedLocator([0.7, 0.85, 1.0, 1.2, 1.4]))
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.set_xticklabels(["0.7", "0.85", "1.0", "1.2", "1.4"])
    ax.set_ylim(*ylim)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.set_xlabel("Odds ratio for funding, women vs men (log scale)")
    fig.suptitle(title, fontsize=10.5, fontweight="bold", y=0.965)
    fig.text(0.02, 0.03, f"Heterogeneity: Q = {res_re.Q:.2f} (df = {res_re.df}, p = {res_re.p_Q:.2f});  "
                         f"I\u00b2 = {100 * res_re.I2:.0f}% [{100 * res_re.I2_lo:.0f}, {100 * res_re.I2_hi:.0f}];  "
                         f"\u03c4\u00b2 = {res_re.tau2:.4f} [{res_re.tau2_lo:.3f}, {res_re.tau2_hi:.3f}]   "
                         f"(applications 2017\u20132026: {int(df.n.sum()):,}; grants {int(df.g.sum()):,})", fontsize=7.2)
    fig.savefig(path)
    plt.close(fig)


def r_est(r):
    return r.est


# --------------------------------------------------------------------------- #
def success_rates(df, path):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8, 3.6), gridspec_kw=dict(width_ratios=[1.3, 1]))
    x = df.year.values
    for col, xcol, ncol, lab, off in [(C_W, "a", "n_w", "women", -0.12), (C_M, "c", "n_m", "men", 0.12)]:
        p = df[xcol] / df[ncol]
        lo, hi = _wilson(df[xcol].values, df[ncol].values)
        ax1.errorbar(x + off, 100 * p, yerr=[100 * (p - lo), 100 * (hi - p)], fmt="o-", color=col, ms=4,
                     capsize=2, lw=1, label=lab)
    ax1.set_ylabel("Success rate (%)  ± 95% Wilson CI")
    ax1.set_xlabel("Call year")
    ax1.set_xticks(x)
    ax1.tick_params(axis="x", labelrotation=45)
    ax1.legend(frameon=False)
    ax1.set_title("Success rate by gender and call", fontsize=9.5)
    rd = 100 * (df.a / df.n_w - df.c / df.n_m)
    se = 100 * np.sqrt((df.a / df.n_w) * (1 - df.a / df.n_w) / df.n_w + (df.c / df.n_m) * (1 - df.c / df.n_m) / df.n_m)
    ax2.bar(x, rd, color=np.where(rd >= 0, C_W, C_M), alpha=0.85)
    ax2.errorbar(x, rd, yerr=1.96 * se, fmt="none", ecolor="black", capsize=2, lw=1)
    ax2.axhline(0, color="black", lw=0.8)
    ax2.set_ylabel("Risk difference, women − men (pp)")
    ax2.set_xlabel("Call year")
    ax2.set_xticks(x)
    ax2.tick_params(axis="x", labelrotation=45)
    ax2.set_title("Difference in success rate", fontsize=9.5)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


# --------------------------------------------------------------------------- #
def cumulative_loo(df, cum, loo, res_re, path):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8, 3.8))
    yrs = np.sort(df.year.values)
    est = np.exp([c["est"] for c in cum]); lo = np.exp([c["lo"] for c in cum]); hi = np.exp([c["hi"] for c in cum])
    ax1.errorbar(est, np.arange(len(cum))[::-1], xerr=[est - lo, hi - est], fmt="D", color=C_RE, ms=4, capsize=2)
    ax1.set_yticks(np.arange(len(cum))[::-1])
    ax1.set_yticklabels([f"… + {y}" if i else f"{y}" for i, y in enumerate(yrs)])
    ax1.axvline(1, color="black", lw=0.8)
    ax1.set_xscale("log"); ax1.set_xticks([0.8, 1.0, 1.2, 1.5]); ax1.set_xticklabels(["0.8", "1.0", "1.2", "1.5"])
    ax1.set_xlabel("Cumulative pooled OR (REML/HKSJ)")
    ax1.set_title("Cumulative meta-analysis by call year", fontsize=9.5)
    est = np.exp([l["est"] for l in loo]); lo = np.exp([l["lo"] for l in loo]); hi = np.exp([l["hi"] for l in loo])
    ax2.errorbar(est, np.arange(len(loo))[::-1], xerr=[est - lo, hi - est], fmt="o", color=C_M, ms=4, capsize=2)
    ax2.axvspan(np.exp(res_re.ci_lo), np.exp(res_re.ci_hi), color=C_RE, alpha=0.15, label="full-data 95% CI")
    ax2.axvline(np.exp(res_re.est), color=C_RE, lw=1, ls="--")
    ax2.axvline(1, color="black", lw=0.8)
    ax2.set_yticks(np.arange(len(loo))[::-1])
    ax2.set_yticklabels([f"omit {y}" for y in df.year.values])
    ax2.set_xscale("log"); ax2.set_xticks([0.95, 1.0, 1.05, 1.1, 1.15, 1.2]); ax2.set_xticklabels(["0.95", "1.0", "1.05", "1.1", "1.15", "1.2"])
    ax2.set_xlabel("Pooled OR omitting one call")
    ax2.set_title("Leave-one-out influence", fontsize=9.5)
    ax2.legend(frameon=False, fontsize=7, loc="lower right")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


# --------------------------------------------------------------------------- #
def funnel_baujat(df, y, v, res_re, egger, tf, bj, path):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8, 3.9))
    se = np.sqrt(v)
    est = res_re.est
    se_grid = np.linspace(0, max(se) * 1.35, 100)
    for zc, col, lab in [(1.96, "#f0f0f0", "p > 0.05"), (2.58, "#d9d9d9", "0.01 < p < 0.05"), (3.29, "#bdbdbd", "p < 0.01")]:
        ax1.fill_betweenx(se_grid, -zc * se_grid, zc * se_grid, color=col, alpha=0.6, lw=0)
    ax1.fill_betweenx(se_grid, -1.96 * se_grid, 1.96 * se_grid, color="white", alpha=0.0)
    ax1.plot(est - 1.96 * se_grid, se_grid, color=C_RE, lw=0.8, ls="--")
    ax1.plot(est + 1.96 * se_grid, se_grid, color=C_RE, lw=0.8, ls="--")
    ax1.scatter(y, se, color=C_RE, edgecolor="black", zorder=3, s=28)
    for yy, s, yr in zip(y, se, df.year):
        ax1.annotate(str(yr), (yy, s), fontsize=6, xytext=(3, 2), textcoords="offset points")
    if len(tf["y_fill"]):
        ax1.scatter(tf["y_fill"], np.sqrt(tf["v_fill"]), facecolor="none", edgecolor="black", s=40, zorder=3,
                    label=f"trim-and-fill imputed (k0 = {tf['k0']})")
    # Egger line: y = b0*se + b1 ... in (y, se) space: y = slope + intercept*se
    ax1.plot(egger["slope"] + egger["intercept"] * se_grid, se_grid, color=C_W, lw=1,
             label=f"Egger: intercept {egger['intercept']:.2f} (p = {egger['p']:.2f})")
    ax1.axvline(0, color="black", lw=0.6)
    ax1.axvline(est, color=C_RE, lw=0.8)
    ax1.invert_yaxis()
    ax1.set_xlabel("log OR (women vs men)")
    ax1.set_ylabel("Standard error")
    ax1.set_title("Contour-enhanced funnel plot", fontsize=9.5)
    ax1.legend(frameon=False, fontsize=6.5, loc="lower left")
    ax2.scatter(bj[0], bj[1], color=C_M, edgecolor="black", s=30)
    for xx, yy, yr in zip(bj[0], bj[1], df.year):
        ax2.annotate(str(yr), (xx, yy), fontsize=6.5, xytext=(3, 3), textcoords="offset points")
    ax2.set_xlabel("Contribution to overall heterogeneity (Q)")
    ax2.set_ylabel("Influence on pooled estimate")
    ax2.set_title("Baujat plot", fontsize=9.5)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


# --------------------------------------------------------------------------- #
def metareg(df, y, v, mr, res_re, path):
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    x = df.year.values
    w = 1 / (v + mr.tau2)
    ax.scatter(x, np.exp(y), s=8 + 500 * w / w.max(), color=C_RE, alpha=0.75, edgecolor="black", lw=0.5)
    xx = np.linspace(x.min() - 0.5, x.max() + 0.5, 100)
    xc = xx - x.mean()
    X = np.column_stack([np.ones_like(xc), xc])
    fit = X @ mr.beta
    # KH-adjusted variance of the fitted line
    W = 1 / (v + mr.tau2)
    Xd = np.column_stack([np.ones_like(x), x - x.mean()])
    cov = np.linalg.inv((Xd.T * W) @ Xd) * (mr.QE / mr.df_resid)
    se_fit = np.sqrt(np.einsum("ij,jk,ik->i", X, cov, X))
    tcrit = stats.t.ppf(0.975, mr.df_resid)
    ax.plot(xx, np.exp(fit), color=C_W, lw=1.5)
    ax.fill_between(xx, np.exp(fit - tcrit * se_fit), np.exp(fit + tcrit * se_fit), color=C_W, alpha=0.15)
    ax.axhline(1, color="black", lw=0.8)
    ax.axhline(np.exp(res_re.est), color=C_RE, lw=0.8, ls="--")
    ax.set_yscale("log"); ax.set_yticks([0.8, 0.9, 1.0, 1.1, 1.2, 1.3]); ax.set_yticklabels(["0.8", "0.9", "1.0", "1.1", "1.2", "1.3"])
    ax.set_xticks(x); ax.tick_params(axis="x", labelrotation=45)
    ax.set_xlabel("Call year"); ax.set_ylabel("OR (women vs men), log scale")
    ax.set_title("Mixed-effects meta-regression on call year (REML, Knapp–Hartung)", fontsize=9.5)
    ax.text(0.02, 0.04, f"slope = {mr.beta[1]:+.4f} log-OR/yr (95% CI {mr.ci_lo[1]:+.3f} to {mr.ci_hi[1]:+.3f}); "
                        f"KH p = {mr.p[1]:.2f}; permutation p = {mr.perm_p:.2f}; residual I² ≈ {0 if np.isnan(mr.R2) else 0:.0f}%",
            transform=ax.transAxes, fontsize=7)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


# --------------------------------------------------------------------------- #
def bayes_fig(fits, hist_fits, path):
    fig, axes = plt.subplots(2, 2, figsize=(8, 6))
    ax = axes[0, 0]
    for (lab, f), col in zip(fits.items(), [C_RE, C_W, C_M, C_FE]):
        ax.plot(np.exp(f["mu"]), f["pm"], color=col, lw=1.4, label=lab)
        ax.plot(np.exp(f["mu"]), stats.norm.pdf(f["mu"], 0, f["s_mu"]), color=col, lw=0.8, ls=":")
    ax.axvline(1, color="black", lw=0.8)
    ax.set_xlim(0.85, 1.35); ax.set_xlabel("OR = exp(μ)"); ax.set_ylabel("posterior density (dotted: prior)")
    ax.set_title("Posterior of the mean OR under alternative priors", fontsize=9)
    ax.legend(frameon=False, fontsize=6.5)
    ax = axes[0, 1]
    for (lab, f), col in zip(fits.items(), [C_RE, C_W, C_M, C_FE]):
        ax.plot(f["tau"], f["pt"], color=col, lw=1.4, label=lab)
        ax.plot(f["tau"], stats.halfnorm.pdf(f["tau"], 0, f["s_tau"]), color=col, lw=0.8, ls=":")
    ax.set_xlim(0, 0.5); ax.set_xlabel("τ (between-call SD of log OR)"); ax.set_ylabel("density")
    ax.set_title("Posterior of between-call heterogeneity τ", fontsize=9)
    ax = axes[1, 0]
    f = list(fits.values())[0]
    ax.plot(np.exp(f["theta_new"]), f["pred"], color=C_RE, lw=1.4, label="posterior predictive, new call")
    ax.plot(np.exp(f["mu"]), f["pm"], color=C_RE, lw=1, ls="--", label="posterior of mean μ")
    ax.axvline(1, color="black", lw=0.8)
    ax.set_xlim(0.75, 1.45); ax.set_xlabel("OR"); ax.set_ylabel("density")
    ax.set_title("Predicted OR in the next StG call", fontsize=9)
    ax.legend(frameon=False, fontsize=6.5)
    ax = axes[1, 1]
    a0s = [h["a0"] for h in hist_fits]
    med = [np.exp(h["mu_q"][1]) for h in hist_fits]
    lo = [np.exp(h["mu_q"][0]) for h in hist_fits]
    hi = [np.exp(h["mu_q"][2]) for h in hist_fits]
    ax.errorbar(a0s, med, yerr=[np.subtract(med, lo), np.subtract(hi, med)], fmt="o-", color=C_M, capsize=3)
    ax.axhline(1, color="black", lw=0.8)
    ax.axhline(hist_fits[0]["hist_or"], color=C_GREY, lw=0.8, ls="--")
    ax.text(0.02, hist_fits[0]["hist_or"] + 0.01, "FP7-era aggregate OR (2007–2013)", fontsize=6.5, color=C_GREY)
    ax.set_xlabel("power-prior discount a₀ on FP7-era evidence"); ax.set_ylabel("posterior OR (median, 95% CrI)")
    ax.set_title("Historical power prior sensitivity", fontsize=9)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


# --------------------------------------------------------------------------- #
def bias_fig(pba_me, pba_full, res_re, conf_or, ev, path):
    fig, axes = plt.subplots(1, 3, figsize=(9.8, 3.5), gridspec_kw=dict(width_ratios=[1.35, 1, 0.9]))
    ax = axes[0]
    rows = [("Conventional REML/HKSJ (random error only)", np.exp([res_re.est, res_re.ci_lo, res_re.ci_hi]), "black"),
            ("Rounding of applicant share: systematic only", np.exp(np.percentile(pba_me["sys_only"], [50, 2.5, 97.5])), C_FE),
            ("Rounding + domain composition: systematic only", np.exp(np.percentile(pba_full["sys_only"], [50, 2.5, 97.5])), C_M),
            ("Rounding: systematic + random", np.exp(np.percentile(pba_me["total"], [50, 2.5, 97.5])), C_FE),
            ("Rounding + domain: systematic + random", np.exp(np.percentile(pba_full["total"], [50, 2.5, 97.5])), C_RE)]
    for i, (lab, (m, l, h), col) in enumerate(rows):
        yy = len(rows) - i
        ax.plot([l, h], [yy, yy], color=col, lw=2.2, solid_capstyle="butt")
        ax.plot(m, yy, "o", color=col, ms=5, mec="black", mew=0.5)
        ax.text(0.955, yy + 0.28, lab, fontsize=6.4, va="bottom")
        ax.text(1.215, yy, f"{m:.3f} [{l:.3f}, {h:.3f}]", fontsize=6.4, va="center")
    ax.axvline(1, color="black", lw=0.8)
    ax.set_xlim(0.95, 1.30); ax.set_ylim(0.3, len(rows) + 0.9); ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.set_xlabel("Pooled OR (women vs men): median and 95% interval")
    ax.set_title("Probabilistic bias analysis (5,000 draws)", fontsize=9)
    ax = axes[1]
    ax.boxplot(conf_or, positions=np.arange(conf_or.shape[1]), widths=0.6, showfliers=False)
    ax.axhline(1, color="black", lw=0.8)
    ax.set_xticks(np.arange(conf_or.shape[1])); ax.set_xticklabels([str(y) for y in ev["years"]], rotation=45)
    ax.set_ylabel("confounding OR induced by domain mix")
    ax.set_title("Bias factor from domain composition", fontsize=9)
    ax = axes[2]
    rr = ev["rr"]
    grid = np.linspace(1.0, 3.0, 200)
    with np.errstate(divide="ignore", invalid="ignore"):
        rr_eu = rr * (grid - 1) / (grid - rr)
    ok = (grid > rr) & (rr_eu > 0)
    ax.plot(grid[ok], rr_eu[ok], color=C_W, lw=1.5)
    ax.plot([ev["evalue_point"]], [ev["evalue_point"]], "o", color=C_W)
    ax.annotate(f"E-value = {ev['evalue_point']:.2f}", (ev["evalue_point"], ev["evalue_point"]), fontsize=7,
                xytext=(6, 6), textcoords="offset points")
    ax.set_xlim(1, 3); ax.set_ylim(1, 3)
    ax.set_xlabel("RR (confounder \u2192 funding)"); ax.set_ylabel("RR (gender \u2192 confounder)")
    ax.set_title(f"E-value curve, pooled RR = {rr:.3f}", fontsize=9)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


# --------------------------------------------------------------------------- #
def selection_fig(rows, breakeven, or_obs, ci, path):
    import pandas as pd
    d = pd.DataFrame(rows)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8, 3.6))
    for rho, col in zip(sorted(d.rho.unique(), reverse=True), [C_RE, C_M, C_W]):
        s = d[d.rho == rho]
        ax1.plot(s.delta, s.or_fair, color=col, lw=1.4, label=f"reliability ρ = {rho:.1f}")
        ax2.plot(s.delta, s.implied_eval_or, color=col, lw=1.4, label=f"ρ = {rho:.1f} (break-even δ = {breakeven[rho]:.2f})")
    ax1.axhline(or_obs, color="black", lw=1, ls="--")
    ax1.axhspan(ci[0], ci[1], color="grey", alpha=0.15)
    ax1.text(0.3, or_obs + 0.03, f"observed pooled OR = {or_obs:.3f}", fontsize=7)
    ax1.set_xlabel("δ: quality shift of women's applicant pool (SD)"); ax1.set_ylabel("expected OR under fair evaluation")
    ax1.set_title("Self-selection generates OR > 1 without bias", fontsize=9)
    ax1.legend(frameon=False, fontsize=7)
    ax2.axhline(1, color="black", lw=0.8)
    ax2.axhline(0.9, color=C_GREY, lw=0.8, ls=":")
    ax2.set_xlabel("δ (SD)"); ax2.set_ylabel("implied evaluation-stage OR = OR_obs / OR_fair(δ)")
    ax2.set_title("Evaluation bias consistent with the data", fontsize=9)
    ax2.legend(frameon=False, fontsize=6.5)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


# --------------------------------------------------------------------------- #
def geo_fig(tab, ps, sgrs, path):
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.5))
    ax = axes[0]
    ax.errorbar(tab.year, 100 * tab.share, yerr=[100 * (tab.share - tab.lo), 100 * (tab.hi - tab.share)], fmt="o",
                color=C_M, capsize=2)
    ax.axhline(100 * ps["share"], color=C_RE, lw=1.2)
    ax.axhspan(100 * ps["lo"], 100 * ps["hi"], color=C_RE, alpha=0.15)
    ax.axhline(25, color=C_GREY, lw=0.8, ls="--"); ax.text(2015, 25.6, "widening share of EU population ≈ 25%", fontsize=6.5, color=C_GREY)
    ax.set_ylim(0, 28); ax.set_ylabel("% of StG grants hosted in widening countries"); ax.set_xlabel("Call year")
    ax.set_title(f"Pooled share {100 * ps['share']:.1f}% [{100 * ps['lo']:.1f}, {100 * ps['hi']:.1f}]", fontsize=9)
    ax = axes[1]
    for s, col in zip(sgrs, [C_RE, C_M, C_W, C_GREY]):
        yrs = [p[0] for p in s["per_call"]]; val = [p[1] for p in s["per_call"]]
        ax.plot(yrs, val, "o-", color=col, ms=3, lw=1, label=f"applicant share {100 * s['applicant_share']:.1f}%: pooled SGR {s['sgr_pooled']:.2f}")
    ax.axhline(1, color="black", lw=0.8)
    ax.set_ylabel("Standardised grant ratio (obs/expected)"); ax.set_xlabel("Call year")
    ax.set_title("SGR under applicant-share scenarios", fontsize=9)
    ax.legend(frameon=False, fontsize=6)
    ax = axes[2]
    ax.plot(tab.year, tab.gini, "o-", color=C_RE, label="Gini (across host countries)")
    ax.plot(tab.year, tab.top3, "s-", color=C_M, label="top-3 country share")
    ax.plot(tab.year, tab.top5, "^-", color=C_FE, label="top-5 country share")
    ax.set_ylim(0.3, 0.75); ax.set_xlabel("Call year"); ax.set_ylabel("index")
    ax.set_title("Concentration of grants", fontsize=9)
    ax.legend(frameon=False, fontsize=6.5)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


# --------------------------------------------------------------------------- #
def extended_fig(df_ext, y_ext, v_ext, imputed_mask, res_prim, res_ext, hist_or, path):
    fig, ax = plt.subplots(figsize=(7, 3.8))
    x = df_ext.year.values
    est, lo, hi = np.exp(y_ext), np.exp(y_ext - 1.96 * np.sqrt(v_ext)), np.exp(y_ext + 1.96 * np.sqrt(v_ext))
    for msk, col in [(imputed_mask, C_GREY), (~imputed_mask, C_RE)]:
        if msk.any():
            ax.errorbar(x[msk], est[msk], yerr=[(est - lo)[msk], (hi - est)[msk]], fmt="none", ecolor=col, capsize=2)
            ax.scatter(x[msk], est[msk], color=col, edgecolor="black", zorder=3, s=28)
    ax.axhline(1, color="black", lw=0.8)
    ax.axhspan(np.exp(res_prim.ci_lo), np.exp(res_prim.ci_hi), color=C_RE, alpha=0.15, label="primary pooled 95% CI (2017–2026)")
    ax.axhspan(np.exp(res_ext.ci_lo), np.exp(res_ext.ci_hi), color=C_GREY, alpha=0.15, label="extended series 95% CI (2015–2026)")
    ax.axhline(hist_or[0], color=C_W, lw=1, ls="--"); ax.axhspan(hist_or[1], hist_or[2], color=C_W, alpha=0.12, label="FP7-era aggregate 2007–2013 (rounded rates)")
    ax.set_yscale("log"); ax.set_yticks([0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.4]); ax.set_yticklabels(["0.7", "0.8", "0.9", "1.0", "1.1", "1.2", "1.4"])
    ax.set_xticks(x); ax.tick_params(axis="x", labelrotation=45)
    ax.set_ylabel("OR (women vs men)"); ax.set_xlabel("Call year (grey = applicant share imputed)")
    ax.set_title("Extended series and historical comparator", fontsize=9.5)
    ax.legend(frameon=False, fontsize=6.5, loc="lower right")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
