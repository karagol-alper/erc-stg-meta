"""
erc_meta.policy
===============
Decision-analytic simulator for selection mechanisms in an ERC-StG-like
competition.  It translates two empirical quantities into policy-relevant
outcomes:

* the success rate and applicant mix estimated from the call-level data;
* the reliability (rho) of peer-review scores, for which the literature on
  grant review reports low-to-moderate values (single-panel intraclass
  correlations broadly in the 0.2-0.5 range; see the policy agenda for
  references).  rho is therefore treated as an uncertain input and swept.

Latent model
------------
Applicant i has latent scientific merit Q_i ~ N(0, 1) (a subgroup may be
shifted by delta).  A review stage observes S = Q + e with
Var(e) = (1 - rho) / rho, so that Corr(S, Q)^2 = rho.  Two independent stages
averaged have reliability 2*rho / (1 + rho) (Spearman-Brown).

Mechanisms
----------
1. single-stage panel : fund the top K by S.
2. two-stage (ERC-like) : stage-1 score selects the top p1 share; stage-2
   adds an independent score; fund the top K by the mean of both scores.
3. threshold + lottery : stage-1 score defines a fundable pool of size
   pool_mult*K; K are drawn at random from the pool (SNSF/Volkswagen style).
4. merit top-half + lottery : the top K/2 by score are funded outright; the
   remaining K/2 are drawn at random from the next tier of the fundable pool.
5. pure lottery : K drawn at random from all eligible applicants.

Outputs
-------
mean latent merit of the funded portfolio (SD units), share of the truly
top-K applicants funded, share of true top-1 % funded, the odds ratio for a
subgroup whose applicant pool is shifted by delta (disparity amplification),
and the full-review workload (number of proposals needing a stage-2 review).

A second, deliberately simple module gives the expected portfolio output of a
fixed budget split into n grants when output per grant scales as size^alpha
(alpha < 1: diminishing returns, the stylised finding of the funding
concentration literature).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

MECHS = ["single-stage panel", "two-stage (ERC-like)", "threshold + lottery", "merit top-half + lottery", "pure lottery"]


def _score(Q, rho, rng):
    if rho >= 1:
        return Q.copy()
    return Q + rng.normal(0, np.sqrt((1 - rho) / rho), size=Q.shape)


def simulate_once(rng, n=3500, success_rate=0.12, share_w=0.40, delta=-0.2, rho=0.3, p1=0.30, pool_mult=2.0):
    K = int(round(success_rate * n))
    group = rng.random(n) < share_w          # True = subgroup (shifted by delta)
    Q = rng.normal(0, 1, n) + delta * group
    top_k = np.argsort(-Q)[:K]
    top1 = np.argsort(-Q)[: max(1, int(round(0.01 * n)))]
    S1 = _score(Q, rho, rng)
    S2 = _score(Q, rho, rng)
    out = {}
    # 1. single-stage panel
    f = np.zeros(n, bool); f[np.argsort(-S1)[:K]] = True; out[MECHS[0]] = (f, n)
    # 2. two-stage: stage 1 keeps top p1 share, stage 2 adds a second independent score
    n1 = int(round(p1 * n)); stage2 = np.argsort(-S1)[:n1]
    comb = 0.5 * (S1[stage2] + S2[stage2])
    f = np.zeros(n, bool); f[stage2[np.argsort(-comb)[:K]]] = True; out[MECHS[1]] = (f, n1)
    # 3. threshold + lottery: fundable pool = top pool_mult*K by S1, then random draw
    pool = np.argsort(-S1)[: int(round(pool_mult * K))]
    f = np.zeros(n, bool); f[rng.choice(pool, K, replace=False)] = True; out[MECHS[2]] = (f, len(pool))
    # 4. merit top-half + lottery for the rest of the pool
    kh = K // 2
    ranked = np.argsort(-S1)
    f = np.zeros(n, bool); f[ranked[:kh]] = True
    rest_pool = ranked[kh: int(round(pool_mult * K))]
    f[rng.choice(rest_pool, K - kh, replace=False)] = True; out[MECHS[3]] = (f, int(round(pool_mult * K)))
    # 5. pure lottery
    f = np.zeros(n, bool); f[rng.choice(n, K, replace=False)] = True; out[MECHS[4]] = (f, 0)
    rows = []
    for m, (f, workload) in out.items():
        pw, pm = f[group].mean(), f[~group].mean()
        rows.append(dict(mechanism=m, mean_merit_funded=float(Q[f].mean()),
                         share_true_topK_funded=float(f[top_k].mean()), share_true_top1pct_funded=float(f[top1].mean()),
                         subgroup_OR=float((pw / (1 - pw)) / (pm / (1 - pm))), subgroup_success=float(pw),
                         reference_success=float(pm), full_review_workload=int(workload)))
    return rows


def run_policy_simulation(success_rate=0.12, share_w=0.40, delta=-0.2, rhos=(0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 1.0),
                          n_sim=200, n=3500, seed=3):
    rng = np.random.default_rng(seed)
    recs = []
    for rho in rhos:
        for s in range(n_sim):
            for r in simulate_once(rng, n=n, success_rate=success_rate, share_w=share_w, delta=delta, rho=rho):
                recs.append(dict(rho=rho, sim=s, **r))
    df = pd.DataFrame(recs)
    tab = df.groupby(["rho", "mechanism"]).agg(
        mean_merit_funded=("mean_merit_funded", "mean"), merit_mc_se=("mean_merit_funded", lambda x: x.std() / np.sqrt(len(x))),
        share_true_topK_funded=("share_true_topK_funded", "mean"), share_true_top1pct_funded=("share_true_top1pct_funded", "mean"),
        subgroup_OR=("subgroup_OR", "mean"), subgroup_OR_sd=("subgroup_OR", "std"),
        full_review_workload=("full_review_workload", "mean")).reset_index()
    tab["mechanism"] = pd.Categorical(tab["mechanism"], MECHS, ordered=True)
    tab = tab.sort_values(["rho", "mechanism"]).reset_index(drop=True)
    # summaries at a single-rater-like reliability (0.3) and a panel-level reliability (0.5)
    summary = dict(inputs=dict(success_rate=success_rate, share_w=share_w, delta=delta, n=n, rhos=list(rhos), n_sim=n_sim,
                               reliability_anchor="single-rater ICC 0.17-0.37 (NSF, FWF, a Norwegian funder); 3-5 raters -> ~0.4-0.6 by Spearman-Brown"))
    for rho0 in (0.3, 0.5):
        t0 = tab[tab.rho == rho0].set_index("mechanism")
        summary[f"at_rho_{rho0}"] = {m: dict(mean_merit=float(t0.loc[m, "mean_merit_funded"]),
                                            share_topK=float(t0.loc[m, "share_true_topK_funded"]),
                                            share_top1=float(t0.loc[m, "share_true_top1pct_funded"]),
                                            subgroup_OR=float(t0.loc[m, "subgroup_OR"]),
                                            workload=float(t0.loc[m, "full_review_workload"])) for m in MECHS}
        summary[f"value_of_second_stage_rho_{rho0}"] = dict(
            merit_gain_SD=float(t0.loc[MECHS[1], "mean_merit_funded"] - t0.loc[MECHS[0], "mean_merit_funded"]),
            topK_gain=float(t0.loc[MECHS[1], "share_true_topK_funded"] - t0.loc[MECHS[0], "share_true_topK_funded"]))
        summary[f"lottery_cost_rho_{rho0}"] = dict(
            merit_loss_SD=float(t0.loc[MECHS[0], "mean_merit_funded"] - t0.loc[MECHS[2], "mean_merit_funded"]),
            topK_loss=float(t0.loc[MECHS[0], "share_true_topK_funded"] - t0.loc[MECHS[2], "share_true_topK_funded"]),
            disparity_gain_OR=float(t0.loc[MECHS[2], "subgroup_OR"] - t0.loc[MECHS[0], "subgroup_OR"]))
    disp = dispersal_curve()
    return dict(table=tab, summary=summary, dispersal=disp)


def dispersal_curve(budget=1.0, n_grants=np.arange(1, 61), alphas=(0.5, 0.7, 0.9, 1.0, 1.2)):
    """Total output when a fixed budget is split evenly into n grants and output per grant = size^alpha."""
    out = {}
    for al in alphas:
        size = budget / n_grants
        out[al] = n_grants * size ** al
    return dict(n=n_grants, curves=out)


def policy_fig(pol, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    tab = pol["table"]
    cols = ["#2a9d8f", "#1f5f8b", "#e9c46a", "#b23a48", "#7a7a7a"]
    fig, axes = plt.subplots(2, 2, figsize=(9, 6.6))
    for ax, ycol, lab, ttl in [(axes[0, 0], "mean_merit_funded", "mean latent merit of funded set (SD)", "Portfolio quality vs review reliability"),
                                (axes[0, 1], "share_true_topK_funded", "share of truly top-K applicants funded", "Selection precision"),
                                (axes[1, 0], "subgroup_OR", "OR for subgroup with pool shifted by δ = −0.2 SD", "Disparity amplification by mechanism")]:
        for m, col in zip(MECHS, cols):
            s = tab[tab.mechanism == m]
            ax.plot(s.rho, s[ycol], "o-", color=col, ms=3.5, lw=1.3, label=m)
        ax.set_xlabel("reliability ρ of a single review stage"); ax.set_ylabel(lab); ax.set_title(ttl, fontsize=9)
        ax.axvspan(0.2, 0.6, color="grey", alpha=0.08)
    axes[1, 0].axhline(1, color="black", lw=0.8)
    axes[0, 0].legend(frameon=False, fontsize=6.5)
    axes[0, 0].text(0.21, axes[0, 0].get_ylim()[1] - 0.06, "shaded: single-rater ICC 0.17\u20130.37;\n3\u20135 raters \u2248 0.4\u20130.6 (Spearman\u2013Brown)", fontsize=6, color="grey", va="top")
    ax = axes[1, 1]
    d = pol["dispersal"]
    for al, col in zip(d["curves"], ["#b23a48", "#e9c46a", "#2a9d8f", "#1f5f8b", "#7a7a7a"]):
        ax.plot(d["n"], d["curves"][al] / d["curves"][al][0], color=col, lw=1.3, label=f"α = {al}")
    ax.set_xlabel("number of grants funded from a fixed budget"); ax.set_ylabel("total output relative to one large grant")
    ax.set_yscale("log"); ax.set_title("Concentration vs dispersal (output ∝ size^α)", fontsize=9)
    ax.legend(frameon=False, fontsize=6.5)
    fig.tight_layout(); fig.savefig(path, dpi=170); plt.close(fig)


# --------------------------------------------------------------------------- #
# Evidence-to-decision: reliability meta-analysis -> simulator outputs with uncertainty
# --------------------------------------------------------------------------- #
# Single-rater intraclass correlations of grant-review scores (see data/evidence_map.csv).
RELIABILITY_STUDIES = [
    # label, ICC, standard error, note
    ("FWF (Mutz, Bornmann & Daniel 2012)", 0.259, (0.279 - 0.249) / 3.92, "95% CI 0.249-0.279 reported"),
    ("NSF (Cole et al. 1981; range per Cicchetti 1991)", 0.27, (0.37 - 0.17) / 3.92, "range 0.17-0.37 across fields treated as a 95% interval (assumption)"),
    ("Norwegian funder (as cited by Hesselberg et al. 2025)", 0.29, 0.03, "SE assumed (not reported in the citing source)"),
]


def spearman_brown(rho1, r):
    return r * rho1 / (1 + (r - 1) * rho1)


def reliability_meta(n_raters=(1, 3, 5), two_stage=True):
    from . import core
    y = np.array([s[1] for s in RELIABILITY_STUDIES]); v = np.array([s[2] ** 2 for s in RELIABILITY_STUDIES])
    r = core.pool(y, v, "REML", hksj=True)
    out = dict(pooled_single_rater=r.est, lo=r.ci_lo, hi=r.ci_hi, se=r.se, tau2=r.tau2, I2=r.I2, k=len(y))
    for nr in n_raters:
        out[f"panel_{nr}_raters"] = float(spearman_brown(r.est, nr))
        out[f"panel_{nr}_raters_lo"] = float(spearman_brown(r.ci_lo, nr))
        out[f"panel_{nr}_raters_hi"] = float(spearman_brown(r.ci_hi, nr))
    if two_stage:
        p5 = spearman_brown(r.est, 5)
        out["two_stage_of_5_rater_panels"] = float(2 * p5 / (1 + p5))
    return out


def propagate_reliability(pol_table, rel, n_raters=5, n_draw=4000, seed=42, extra_sd=0.05):
    """Draw the panel-level reliability from the meta-analytic distribution (single-rater ICC ~ N(est, se),
    Spearman-Brown to n_raters) and interpolate the simulator outputs over the rho grid.
    extra_sd: assumed between-funder/field SD of the single-rater ICC (the k = 3 pooled estimate cannot
    estimate it; 0.05 reproduces the NSF field range of 0.17-0.37)."""
    rng = np.random.default_rng(seed)
    rho1 = np.clip(rng.normal(rel["pooled_single_rater"], np.sqrt(rel["se"] ** 2 + extra_sd ** 2), n_draw), 0.02, 0.98)
    rho_panel = spearman_brown(rho1, n_raters)
    tab = pol_table
    grid = np.sort(tab.rho.unique())
    out = {}
    for m in MECHS:
        s = tab[tab.mechanism == m].sort_values("rho")
        for col in ["mean_merit_funded", "share_true_topK_funded", "subgroup_OR"]:
            vals = np.interp(rho_panel, s.rho.values, s[col].values)
            out[(m, col)] = vals
    def summ(x):
        return dict(median=float(np.median(x)), lo=float(np.percentile(x, 2.5)), hi=float(np.percentile(x, 97.5)))
    res = dict(rho_panel=summ(rho_panel), n_raters=n_raters, extra_sd=extra_sd)
    for m in MECHS:
        res[m] = {col: summ(out[(m, col)]) for col in ["mean_merit_funded", "share_true_topK_funded", "subgroup_OR"]}
    res["two_stage_gain_merit_SD"] = summ(out[(MECHS[1], "mean_merit_funded")] - out[(MECHS[0], "mean_merit_funded")])
    res["threshold_lottery_cost_merit_SD"] = summ(out[(MECHS[0], "mean_merit_funded")] - out[(MECHS[2], "mean_merit_funded")])
    res["hybrid_lottery_cost_merit_SD"] = summ(out[(MECHS[0], "mean_merit_funded")] - out[(MECHS[3], "mean_merit_funded")])
    res["threshold_lottery_topK_loss"] = summ(out[(MECHS[0], "share_true_topK_funded")] - out[(MECHS[2], "share_true_topK_funded")])
    res["threshold_lottery_disparity_gain_OR"] = summ(out[(MECHS[2], "subgroup_OR")] - out[(MECHS[0], "subgroup_OR")])
    res["draws"] = dict(rho_panel=rho_panel, two_stage_gain=out[(MECHS[1], "mean_merit_funded")] - out[(MECHS[0], "mean_merit_funded")],
                        lottery_cost=out[(MECHS[0], "mean_merit_funded")] - out[(MECHS[2], "mean_merit_funded")],
                        hybrid_cost=out[(MECHS[0], "mean_merit_funded")] - out[(MECHS[3], "mean_merit_funded")])
    return res


def reliability_fig(rel, prop, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.5))
    ax = axes[0]
    labs = [s[0] for s in RELIABILITY_STUDIES]; est = [s[1] for s in RELIABILITY_STUDIES]; se = [s[2] for s in RELIABILITY_STUDIES]
    yy = np.arange(len(labs))[::-1] + 1
    ax.errorbar(est, yy, xerr=1.96 * np.array(se), fmt="s", color="#1f5f8b", capsize=3)
    ax.errorbar([rel["pooled_single_rater"]], [0], xerr=[[rel["pooled_single_rater"] - rel["lo"]], [rel["hi"] - rel["pooled_single_rater"]]], fmt="D", color="#2a9d8f", capsize=3)
    ax.set_yticks(list(yy) + [0]); ax.set_yticklabels(labs + [f"pooled (REML/HKSJ): {rel['pooled_single_rater']:.3f}"], fontsize=6.5)
    ax.set_xlim(0.1, 0.45); ax.set_xlabel("single-rater ICC"); ax.set_title("Reliability of grant-review scores", fontsize=8.5)
    ax = axes[1]
    r = np.arange(1, 16)
    for rho1, col, lab in [(rel["lo"], "#7a7a7a", "lower CI"), (rel["pooled_single_rater"], "#2a9d8f", "pooled"), (rel["hi"], "#7a7a7a", "upper CI")]:
        ax.plot(r, spearman_brown(rho1, r), "o-", color=col, ms=3, lw=1.1, label=lab if lab != "upper CI" else None)
    ax.axhline(0.75, color="#b23a48", lw=0.8, ls="--"); ax.text(1.2, 0.76, "conventional 'acceptable' 0.75", fontsize=6.5, color="#b23a48")
    ax.set_xlabel("number of independent raters averaged"); ax.set_ylabel("panel reliability (Spearman–Brown)")
    ax.set_title("How many reviewers would it take?", fontsize=8.5); ax.legend(frameon=False, fontsize=6.5)
    ax = axes[2]
    d = prop["draws"]
    ax.hist(d["two_stage_gain"], 40, color="#1f5f8b", alpha=0.7, label="gain from ERC 2nd stage")
    ax.hist(d["lottery_cost"], 40, color="#e9c46a", alpha=0.7, label="cost of threshold + lottery")
    ax.hist(d["hybrid_cost"], 40, color="#b23a48", alpha=0.6, label="cost of merit top-half + lottery")
    ax.set_xlabel(f"mean latent merit of funded set (SD), {prop['n_raters']}-rater panels"); ax.set_ylabel("draws")
    ax.set_title(f"Policy effects with reliability uncertainty (ρ_panel ≈ {prop['rho_panel']['median']:.2f})", fontsize=8.5)
    ax.legend(frameon=False, fontsize=6.5)
    fig.tight_layout(); fig.savefig(path, dpi=170); plt.close(fig)
