"""
erc_meta.bias
=============
Quantitative bias analysis (Lash, Fox & Fink; VanderWeele & Ding) adapted to
call-level grant data.

Bias sources addressed
----------------------
1. Denominator measurement error - the women's share of applicants is
   published rounded ("nearly 40 %").  Each call's share is drawn from its
   documented interval; the 2x2 table is rebuilt and the meta-analysis re-run
   (probabilistic bias analysis, PBA).
2. Confounding by domain composition - women apply disproportionately to
   Social Sciences & Humanities and Life Sciences; if success rates differ by
   domain, the crude OR is confounded.  We externally adjust using the
   observed domain-specific success rates and an assumed (uncertain)
   within-domain women's share, calibrated to the call's overall share
   (direct standardisation).
3. Unmeasured confounding in general - E-values for the pooled RR, for its
   confidence limit, and non-null E-values (strength of confounding needed to
   mask a true disadvantage of RR = 0.90 / 0.95).
4. Differential self-selection into applying - a latent-quality model in
   which women's applicant pool has mean quality shifted by delta SD; under a
   fair evaluation with reliability rho the *expected* OR is > 1, so the
   evaluation-stage bias implied by the observed OR is OR_obs / OR_fair(delta).
5. Multiple-bias modelling - (1) and (2) combined, then random error added
   (total-error simulation interval).
"""
from __future__ import annotations

import numpy as np
from scipy import stats, optimize

from . import core
from .data import Call, two_by_two


# --------------------------------------------------------------------------- #
# E-values
# --------------------------------------------------------------------------- #
def evalue(rr: float) -> float:
    rr = float(rr)
    if rr < 1:
        rr = 1 / rr
    return rr + np.sqrt(rr * (rr - 1)) if rr > 1 else 1.0


def evalue_set(rr, lo, hi, true_alternatives=(0.95, 0.90)):
    """E-values for the point estimate, for the CI limit closest to the null, and
    non-null E-values: bias needed to move the estimate to a true RR of `alt`."""
    out = dict(rr=rr, evalue_point=evalue(rr))
    if lo <= 1 <= hi:
        out["evalue_ci"] = 1.0
    else:
        out["evalue_ci"] = evalue(lo if rr > 1 else hi)
    for alt in true_alternatives:
        out[f"evalue_true_{alt}"] = evalue(rr / alt)
        # and for the CI limit nearest to alt
        lim = lo if rr > alt else hi
        out[f"evalue_ci_true_{alt}"] = 1.0 if (lo <= alt <= hi) else evalue(lim / alt)
    return out


# --------------------------------------------------------------------------- #
# Domain-composition confounding (external adjustment)
# --------------------------------------------------------------------------- #
DOMAIN_FACTORS = dict(LS=1.15, PE=0.75, SH=1.30)  # women's share by domain relative to the overall share


def domain_confounding_or(call: Call, share_w: float, factors=DOMAIN_FACTORS) -> float:
    """OR that domain composition alone would induce if success were gender-neutral within domain."""
    n = np.array([call.n_ls, call.n_pe, call.n_sh], float)
    g = np.array([call.g_ls, call.g_pe, call.g_sh], float)
    r = g / n
    f = np.array([factors["LS"], factors["PE"], factors["SH"]])
    # calibrate so that sum_d s_d n_d = share_w * N
    kappa = share_w * n.sum() / np.sum(f * n)
    s = np.clip(kappa * f, 0.02, 0.98)
    pw = np.sum(s * n * r) / np.sum(s * n)
    pm = np.sum((1 - s) * n * r) / np.sum((1 - s) * n)
    return (pw / (1 - pw)) / (pm / (1 - pm))


# --------------------------------------------------------------------------- #
# Probabilistic bias analysis
# --------------------------------------------------------------------------- #
def probabilistic_bias_analysis(calls, n_sim=5000, seed=2026, adjust_domain=True, factor_sd=0.15,
                                 method="DL", share_override=None):
    """Monte-Carlo propagation of (i) denominator rounding and (ii) domain-composition
    confounding through the meta-analysis.  Returns arrays of pooled log OR
    (systematic error only) and with random error added."""
    rng = np.random.default_rng(seed)
    k = len(calls)
    sys_only = np.empty(n_sim)
    total = np.empty(n_sim)
    per_call = np.empty((n_sim, k))
    conf_or = np.empty((n_sim, k))
    for b in range(n_sim):
        ys, vs = [], []
        for i, c in enumerate(calls):
            lo, hi = c.share_w_lo / 100, c.share_w_hi / 100
            s = rng.uniform(lo, hi) if share_override is None else share_override[i]
            t = two_by_two(c, share=s)
            y, v = core.log_or(t["a"], t["b"], t["c"], t["d"])
            if adjust_domain:
                fac = {d: max(0.2, DOMAIN_FACTORS[d] + rng.normal(0, factor_sd)) for d in DOMAIN_FACTORS}
                bias = np.log(domain_confounding_or(c, s, fac))
            else:
                bias = 0.0
            conf_or[b, i] = np.exp(bias)
            ys.append(y - bias)
            vs.append(v)
            per_call[b, i] = y - bias
        ys, vs = np.array(ys), np.array(vs)
        r = core.pool(ys, vs, method)
        sys_only[b] = r.est
        total[b] = rng.normal(r.est, r.se)
    return dict(sys_only=sys_only, total=total, per_call=per_call, conf_or=conf_or)


def summarise_draws(x, transform=np.exp):
    q = np.percentile(x, [2.5, 50, 97.5])
    return dict(median=float(transform(q[1])), lo=float(transform(q[0])), hi=float(transform(q[2])),
                p_below_1=float(np.mean(x < 0)))


# --------------------------------------------------------------------------- #
# Differential self-selection: latent-quality model
# --------------------------------------------------------------------------- #
def fair_or(delta, rho, share_w, success_rate):
    """Expected OR (women vs men) under a quality-based evaluation with reliability rho when the
    women's applicant pool is shifted by `delta` SD in latent quality."""
    s = np.sqrt(1 / rho)  # sd of score = sqrt(1 + sigma^2) with rho = 1/(1+sigma^2)

    def overall(t):
        return share_w * stats.norm.sf((t - delta) / s) + (1 - share_w) * stats.norm.sf(t / s) - success_rate

    t = optimize.brentq(overall, -10, 10)
    pw, pm = stats.norm.sf((t - delta) / s), stats.norm.sf(t / s)
    return (pw / (1 - pw)) / (pm / (1 - pm)), pw, pm


def selection_sensitivity(or_obs, share_w, success_rate, deltas=np.linspace(0, 0.5, 51), rhos=(1.0, 0.7, 0.5)):
    rows = []
    for rho in rhos:
        for d in deltas:
            fo, pw, pm = fair_or(d, rho, share_w, success_rate)
            rows.append(dict(rho=rho, delta=float(d), or_fair=float(fo), implied_eval_or=float(or_obs / fo)))
    # break-even delta for each rho (delta at which fair OR equals observed OR)
    breakeven = {}
    for rho in rhos:
        f = lambda d: fair_or(d, rho, share_w, success_rate)[0] - or_obs
        try:
            breakeven[rho] = float(optimize.brentq(f, 0, 3))
        except ValueError:
            breakeven[rho] = np.nan
    return rows, breakeven
