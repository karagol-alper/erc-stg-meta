"""
erc_meta.core
=============
Self-contained frequentist meta-analysis machinery (numpy/scipy only).

Implemented
-----------
* effect sizes for 2x2 tables: log OR, log RR, risk difference
* common-effect (inverse-variance) and Mantel-Haenszel OR with RBG variance
* random-effects tau^2: DerSimonian-Laird, Paule-Mandel, REML
* Q-profile CI for tau^2, Higgins-Thompson CI for H / I^2
* Hartung-Knapp-Sidik-Jonkman (HKSJ) CI, prediction interval
* mixed-effects meta-regression (REML) with Knapp-Hartung CIs and a
  permutation test for the moderator
* leave-one-out, cumulative meta-analysis, Baujat quantities, Cook's D
* Egger, Peters (OR-specific) and Begg tests, trim-and-fill (L0), PET-PEESE
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence
import numpy as np
from scipy import stats, optimize

Z975 = stats.norm.ppf(0.975)


# --------------------------------------------------------------------------- #
# Effect sizes
# --------------------------------------------------------------------------- #
def log_or(a, b, c, d, cc=0.0):
    a, b, c, d = (np.asarray(x, float) + cc for x in (a, b, c, d))
    y = np.log(a * d / (b * c))
    v = 1 / a + 1 / b + 1 / c + 1 / d
    return y, v


def log_rr(a, b, c, d):
    a, b, c, d = (np.asarray(x, float) for x in (a, b, c, d))
    n1, n2 = a + b, c + d
    y = np.log((a / n1) / (c / n2))
    v = 1 / a - 1 / n1 + 1 / c - 1 / n2
    return y, v


def risk_diff(a, b, c, d):
    a, b, c, d = (np.asarray(x, float) for x in (a, b, c, d))
    n1, n2 = a + b, c + d
    p1, p2 = a / n1, c / n2
    return p1 - p2, p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2


# --------------------------------------------------------------------------- #
# Pooling
# --------------------------------------------------------------------------- #
@dataclass
class PooledResult:
    method: str
    est: float
    se: float
    ci_lo: float
    ci_hi: float
    tau2: float = 0.0
    tau2_lo: float = np.nan
    tau2_hi: float = np.nan
    Q: float = np.nan
    df: int = 0
    p_Q: float = np.nan
    I2: float = np.nan
    I2_lo: float = np.nan
    I2_hi: float = np.nan
    H2: float = np.nan
    pi_lo: float = np.nan
    pi_hi: float = np.nan
    weights: Optional[np.ndarray] = None
    z: float = np.nan
    p: float = np.nan
    hksj: bool = False
    hksj_q: float = np.nan

    def as_dict(self, transform=np.exp):
        return dict(method=self.method, est=float(transform(self.est)), lo=float(transform(self.ci_lo)),
                    hi=float(transform(self.ci_hi)), se_log=float(self.se), z=float(self.z), p=float(self.p),
                    tau2=float(self.tau2), tau2_lo=float(self.tau2_lo), tau2_hi=float(self.tau2_hi),
                    Q=float(self.Q), df=int(self.df), p_Q=float(self.p_Q), I2=float(self.I2),
                    I2_lo=float(self.I2_lo), I2_hi=float(self.I2_hi), H2=float(self.H2),
                    pi_lo=float(transform(self.pi_lo)) if np.isfinite(self.pi_lo) else np.nan,
                    pi_hi=float(transform(self.pi_hi)) if np.isfinite(self.pi_hi) else np.nan,
                    hksj=self.hksj, hksj_q=float(self.hksj_q))


def _fe(y, v):
    w = 1 / v
    est = np.sum(w * y) / np.sum(w)
    return est, w


def cochran_q(y, v):
    est, w = _fe(y, v)
    Q = float(np.sum(w * (y - est) ** 2))
    return Q, w


def tau2_dl(y, v):
    Q, w = cochran_q(y, v)
    k = len(y)
    C = np.sum(w) - np.sum(w ** 2) / np.sum(w)
    return max(0.0, (Q - (k - 1)) / C)


def _q_gen(tau2, y, v):
    w = 1 / (v + tau2)
    est = np.sum(w * y) / np.sum(w)
    return np.sum(w * (y - est) ** 2)


def tau2_pm(y, v):
    k = len(y)
    if _q_gen(0.0, y, v) <= k - 1:
        return 0.0
    hi = 1.0
    while _q_gen(hi, y, v) > k - 1:
        hi *= 4
    return float(optimize.brentq(lambda t: _q_gen(t, y, v) - (k - 1), 0.0, hi))


def _reml_nll(tau2, y, v, X=None):
    """Negative REML log-likelihood (up to a constant)."""
    W = 1 / (v + tau2)
    if X is None:
        X = np.ones((len(y), 1))
    XtW = X.T * W
    XtWX = XtW @ X
    beta = np.linalg.solve(XtWX, XtW @ y)
    r = y - X @ beta
    return 0.5 * (np.sum(np.log(v + tau2)) + np.linalg.slogdet(XtWX)[1] + np.sum(W * r ** 2))


def tau2_reml(y, v, X=None):
    res = optimize.minimize_scalar(_reml_nll, bounds=(0.0, 10.0), args=(y, v, X), method="bounded",
                                   options={"xatol": 1e-10})
    return float(max(0.0, res.x))


def tau2_ci_qprofile(y, v, alpha=0.05):
    """Q-profile confidence interval for tau^2 (Viechtbauer 2007)."""
    k = len(y)
    lo_crit, hi_crit = stats.chi2.ppf(1 - alpha / 2, k - 1), stats.chi2.ppf(alpha / 2, k - 1)
    f = lambda t, crit: _q_gen(t, y, v) - crit
    upper = 50.0
    if f(0.0, lo_crit) <= 0:
        tau2_lo = 0.0
    else:
        tau2_lo = optimize.brentq(f, 0.0, upper, args=(lo_crit,))
    if f(0.0, hi_crit) <= 0:
        tau2_hi = 0.0
    else:
        tau2_hi = optimize.brentq(f, 0.0, upper, args=(hi_crit,))
    return float(tau2_lo), float(tau2_hi)


def i2_ci(Q, k, alpha=0.05):
    """Higgins & Thompson (2002) CI for H and I^2 based on the Q statistic."""
    if k < 3:
        return np.nan, np.nan
    H = np.sqrt(max(Q / (k - 1), 1e-12))
    if Q > k:
        se_lnH = 0.5 * (np.log(Q) - np.log(k - 1)) / (np.sqrt(2 * Q) - np.sqrt(2 * k - 3))
    else:
        se_lnH = np.sqrt(1 / (2 * (k - 2)) * (1 - 1 / (3 * (k - 2) ** 2)))
    z = stats.norm.ppf(1 - alpha / 2)
    H_lo, H_hi = max(1.0, np.exp(np.log(H) - z * se_lnH)), max(1.0, np.exp(np.log(H) + z * se_lnH))
    return (H_lo ** 2 - 1) / H_lo ** 2, (H_hi ** 2 - 1) / H_hi ** 2


def pool(y, v, method="REML", hksj=False, alpha=0.05, pi=True):
    """Random-effects (or common-effect) pooling of effect sizes y with sampling variances v."""
    y, v = np.asarray(y, float), np.asarray(v, float)
    k = len(y)
    Q, w_fe = cochran_q(y, v)
    df = k - 1
    p_Q = stats.chi2.sf(Q, df)
    I2 = max(0.0, (Q - df) / Q) if Q > 0 else 0.0
    I2_lo, I2_hi = i2_ci(Q, k)
    H2 = Q / df
    m = method.upper()
    if m == "FE":
        tau2 = 0.0
        tau2_lo = tau2_hi = np.nan
    else:
        tau2 = {"DL": tau2_dl, "PM": tau2_pm, "REML": tau2_reml}[m](y, v)
        tau2_lo, tau2_hi = tau2_ci_qprofile(y, v, alpha)
    w = 1 / (v + tau2)
    est = np.sum(w * y) / np.sum(w)
    se = np.sqrt(1 / np.sum(w))
    q_hk = np.nan
    if hksj and k > 1:
        q_hk = np.sum(w * (y - est) ** 2) / (k - 1)
        se = np.sqrt(q_hk / np.sum(w))
        crit = stats.t.ppf(1 - alpha / 2, k - 1)
        z = est / se
        p = 2 * stats.t.sf(abs(z), k - 1)
    else:
        crit = stats.norm.ppf(1 - alpha / 2)
        z = est / se
        p = 2 * stats.norm.sf(abs(z))
    ci_lo, ci_hi = est - crit * se, est + crit * se
    pi_lo = pi_hi = np.nan
    if pi and m != "FE" and k > 2:
        tcrit = stats.t.ppf(1 - alpha / 2, k - 2)
        sd = np.sqrt(tau2 + se ** 2)
        pi_lo, pi_hi = est - tcrit * sd, est + tcrit * sd
    return PooledResult(method=m + ("+HKSJ" if hksj else ""), est=float(est), se=float(se), ci_lo=float(ci_lo),
                        ci_hi=float(ci_hi), tau2=float(tau2), tau2_lo=tau2_lo, tau2_hi=tau2_hi, Q=Q, df=df,
                        p_Q=float(p_Q), I2=float(I2), I2_lo=I2_lo, I2_hi=I2_hi, H2=float(H2), pi_lo=pi_lo,
                        pi_hi=pi_hi, weights=w / np.sum(w), z=float(z), p=float(p), hksj=hksj, hksj_q=q_hk)


def mantel_haenszel_or(a, b, c, d, alpha=0.05):
    """Mantel-Haenszel pooled OR with Robins-Breslow-Greenland variance."""
    a, b, c, d = (np.asarray(x, float) for x in (a, b, c, d))
    n = a + b + c + d
    R, S = a * d / n, b * c / n
    P, Qv = (a + d) / n, (b + c) / n
    or_mh = np.sum(R) / np.sum(S)
    var = (np.sum(P * R) / (2 * np.sum(R) ** 2) + np.sum(P * S + Qv * R) / (2 * np.sum(R) * np.sum(S))
           + np.sum(Qv * S) / (2 * np.sum(S) ** 2))
    se = np.sqrt(var)
    z = stats.norm.ppf(1 - alpha / 2)
    est = np.log(or_mh)
    return PooledResult(method="MH", est=float(est), se=float(se), ci_lo=float(est - z * se), ci_hi=float(est + z * se),
                        z=float(est / se), p=float(2 * stats.norm.sf(abs(est / se))))


def peto_or(a, b, c, d, alpha=0.05):
    a, b, c, d = (np.asarray(x, float) for x in (a, b, c, d))
    n = a + b + c + d
    n1, m1 = a + b, a + c
    E = n1 * m1 / n
    V = n1 * (c + d) * m1 * (b + d) / (n ** 2 * (n - 1))
    est = np.sum(a - E) / np.sum(V)
    se = 1 / np.sqrt(np.sum(V))
    z = stats.norm.ppf(1 - alpha / 2)
    return PooledResult(method="Peto", est=float(est), se=float(se), ci_lo=float(est - z * se),
                        ci_hi=float(est + z * se), z=float(est / se), p=float(2 * stats.norm.sf(abs(est / se))))


# --------------------------------------------------------------------------- #
# Meta-regression
# --------------------------------------------------------------------------- #
@dataclass
class MetaRegResult:
    beta: np.ndarray
    se: np.ndarray
    ci_lo: np.ndarray
    ci_hi: np.ndarray
    t: np.ndarray
    p: np.ndarray
    tau2: float
    tau2_re: float
    R2: float
    QE: float
    p_QE: float
    QM: float
    p_QM: float
    df_resid: int
    perm_p: float = np.nan
    n_perm: int = 0
    names: Sequence[str] = ()


def meta_regression(y, v, X, names=None, knapp_hartung=True, alpha=0.05, n_perm=0, seed=2026):
    y, v, X = np.asarray(y, float), np.asarray(v, float), np.asarray(X, float)
    k, p = X.shape
    tau2 = tau2_reml(y, v, X)
    tau2_re = tau2_reml(y, v)
    W = 1 / (v + tau2)
    XtW = X.T * W
    XtWX_inv = np.linalg.inv(XtW @ X)
    beta = XtWX_inv @ (XtW @ y)
    r = y - X @ beta
    QE = float(np.sum(W * r ** 2))
    df_resid = k - p
    q = QE / df_resid if knapp_hartung else 1.0
    V = XtWX_inv * q
    se = np.sqrt(np.diag(V))
    t = beta / se
    if knapp_hartung:
        crit = stats.t.ppf(1 - alpha / 2, df_resid)
        pv = 2 * stats.t.sf(np.abs(t), df_resid)
    else:
        crit = stats.norm.ppf(1 - alpha / 2)
        pv = 2 * stats.norm.sf(np.abs(t))
    # omnibus test of moderators (excluding intercept)
    idx = np.arange(1, p)
    if len(idx):
        b1 = beta[idx]
        V1 = V[np.ix_(idx, idx)]
        QM = float(b1 @ np.linalg.solve(V1, b1))
        p_QM = float(stats.f.sf(QM / len(idx), len(idx), df_resid)) if knapp_hartung else float(stats.chi2.sf(QM, len(idx)))
    else:
        QM, p_QM = np.nan, np.nan
    R2 = max(0.0, (tau2_re - tau2) / tau2_re) if tau2_re > 0 else np.nan
    res = MetaRegResult(beta=beta, se=se, ci_lo=beta - crit * se, ci_hi=beta + crit * se, t=t, p=pv, tau2=tau2,
                        tau2_re=tau2_re, R2=R2, QE=QE, p_QE=float(stats.chi2.sf(QE, df_resid)), QM=QM,
                        p_QM=p_QM, df_resid=df_resid, names=names or [f"b{j}" for j in range(p)])
    if n_perm and p == 2:
        rng = np.random.default_rng(seed)
        t_obs = abs(t[1])
        count = 0
        xmod = X[:, 1].copy()
        for _ in range(n_perm):
            Xp = X.copy()
            Xp[:, 1] = rng.permutation(xmod)
            rp = meta_regression(y, v, Xp, knapp_hartung=knapp_hartung, n_perm=0)
            if abs(rp.t[1]) >= t_obs - 1e-12:
                count += 1
        res.perm_p = (count + 1) / (n_perm + 1)
        res.n_perm = n_perm
    return res


# --------------------------------------------------------------------------- #
# Influence, cumulative, Baujat
# --------------------------------------------------------------------------- #
def leave_one_out(y, v, method="REML", hksj=True):
    k = len(y)
    out = []
    full = pool(y, v, method, hksj)
    for i in range(k):
        m = np.ones(k, bool)
        m[i] = False
        r = pool(y[m], v[m], method, hksj)
        # Cook's distance analogue (relative to the full-model variance)
        cook = (full.est - r.est) ** 2 / full.se ** 2
        # externally studentised deleted residual
        resid = (y[i] - r.est) / np.sqrt(v[i] + r.tau2 + r.se ** 2)
        out.append(dict(est=r.est, lo=r.ci_lo, hi=r.ci_hi, tau2=r.tau2, I2=r.I2, cook=float(cook), rstudent=float(resid)))
    return out


def cumulative(y, v, order, method="REML", hksj=True):
    order = np.argsort(order)
    out = []
    for j in range(1, len(y) + 1):
        idx = order[:j]
        if j == 1:
            est, se = float(y[idx][0]), float(np.sqrt(v[idx][0]))
            out.append(dict(k=1, est=est, lo=est - Z975 * se, hi=est + Z975 * se, tau2=0.0))
        else:
            r = pool(y[idx], v[idx], method, hksj if j > 2 else False)
            out.append(dict(k=j, est=r.est, lo=r.ci_lo, hi=r.ci_hi, tau2=r.tau2))
    return out


def baujat(y, v, method="REML"):
    """x: contribution to Q; y: influence on the pooled estimate (Baujat et al. 2002)."""
    k = len(y)
    fe, w = _fe(y, v)
    x_contrib = w * (y - fe) ** 2
    full = pool(y, v, method)
    infl = []
    for i in range(k):
        m = np.ones(k, bool)
        m[i] = False
        r = pool(y[m], v[m], method)
        infl.append((full.est - r.est) ** 2 / r.se ** 2)
    return np.asarray(x_contrib), np.asarray(infl)


# --------------------------------------------------------------------------- #
# Small-study effects
# --------------------------------------------------------------------------- #
def _wls(x, y, w):
    X = np.column_stack([np.ones_like(x), x])
    XtW = X.T * w
    beta = np.linalg.solve(XtW @ X, XtW @ y)
    r = y - X @ beta
    df = len(y) - 2
    s2 = np.sum(w * r ** 2) / df
    cov = np.linalg.inv(XtW @ X) * s2
    se = np.sqrt(np.diag(cov))
    t = beta / se
    p = 2 * stats.t.sf(np.abs(t), df)
    return beta, se, t, p, df


def egger_test(y, v):
    """Egger's regression test: y_i/se_i = b0 + b1 (1/se_i); H0: b0 = 0 (intercept)."""
    se = np.sqrt(v)
    beta, sebeta, t, p, df = _wls(1 / se, y / se, np.ones_like(y))
    return dict(intercept=float(beta[0]), se=float(sebeta[0]), t=float(t[0]), p=float(p[0]), df=int(df),
                slope=float(beta[1]))


def peters_test(a, b, c, d):
    """Peters et al. (2006): regress log OR on 1/N weighted by (events x non-events)/N."""
    y, v = log_or(a, b, c, d)
    n = a + b + c + d
    w = 1 / (1 / (a + c) + 1 / (b + d))
    beta, se, t, p, df = _wls(1 / n, y, w)
    return dict(slope=float(beta[1]), se=float(se[1]), t=float(t[1]), p=float(p[1]), df=int(df))


def begg_test(y, v):
    """Begg & Mazumdar rank correlation between standardised effects and variances."""
    fe, w = _fe(y, v)
    vstar = v - 1 / np.sum(w)
    tstar = (y - fe) / np.sqrt(vstar)
    tau, p = stats.kendalltau(tstar, v)
    return dict(kendall_tau=float(tau), p=float(p))


def trim_and_fill(y, v, side=None, method="REML", max_iter=50):
    """Duval & Tweedie (2000) L0 trim-and-fill.  side='left' means studies are
    presumed missing on the left (small effects suppressed); if None the side is
    chosen from the sign of Egger's intercept."""
    y, v = np.asarray(y, float), np.asarray(v, float)
    if side is None:
        side = "left" if egger_test(y, v)["intercept"] > 0 else "right"
    sgn = 1.0 if side == "left" else -1.0
    yy = sgn * y  # after flipping, missing studies are assumed on the left
    k = len(yy)
    k0 = 0
    order = np.argsort(yy)  # ascending; most extreme right-side effects are at the end
    for _ in range(max_iter):
        keep = order[: k - k0] if k0 > 0 else order
        est = pool(yy[keep], v[keep], method).est
        dev = yy - est
        ranks = stats.rankdata(np.abs(dev))
        Tn = np.sum(ranks[dev > 0])
        L0 = (4 * Tn - k * (k + 1)) / (2 * k - 1)
        k0_new = int(max(0, round(L0)))
        if k0_new == k0:
            break
        k0 = min(k0_new, k - 2)
    keep = order[: k - k0] if k0 > 0 else order
    est_trim = pool(yy[keep], v[keep], method).est
    trimmed = order[k - k0:] if k0 > 0 else np.array([], int)
    y_fill = 2 * est_trim - yy[trimmed]
    v_fill = v[trimmed]
    y_all = np.concatenate([yy, y_fill])
    v_all = np.concatenate([v, v_fill])
    r = pool(y_all, v_all, method, hksj=True)
    lo, hi = sorted([sgn * r.ci_lo, sgn * r.ci_hi])
    return dict(k0=int(k0), side=side, est=float(sgn * r.est), lo=float(lo), hi=float(hi),
                y_fill=sgn * y_fill, v_fill=v_fill, tau2=r.tau2)


def pet_peese(y, v):
    se = np.sqrt(v)
    w = 1 / v
    b_pet, se_pet, t_pet, p_pet, df = _wls(se, y, w)
    b_peese, se_peese, t_peese, p_peese, _ = _wls(v, y, w)
    use = "PET" if p_pet[0] >= 0.10 else "PEESE"
    chosen = (b_pet[0], se_pet[0]) if use == "PET" else (b_peese[0], se_peese[0])
    tcrit = stats.t.ppf(0.975, df)
    return dict(PET=dict(est=float(b_pet[0]), se=float(se_pet[0]), p=float(p_pet[0]), slope=float(b_pet[1]),
                         p_slope=float(p_pet[1])),
                PEESE=dict(est=float(b_peese[0]), se=float(se_peese[0]), p=float(p_peese[0]), slope=float(b_peese[1]),
                           p_slope=float(p_peese[1])),
                chosen=use, est=float(chosen[0]), lo=float(chosen[0] - tcrit * chosen[1]),
                hi=float(chosen[0] + tcrit * chosen[1]))


def limit_meta(y, v):
    """Ruecker's limit meta-analysis (shrunken estimate as precision -> infinity)."""
    tau2 = tau2_reml(y, v)
    se = np.sqrt(v)
    r = pool(y, v, "REML")
    # generalised radial plot regression: y_i = mu + beta * se_i  (weights 1/(v+tau2))
    w = 1 / (v + tau2)
    beta, seb, t, p, df = _wls(se, y, w)
    return dict(est=float(beta[0]), se=float(seb[0]), p_bias=float(p[1]), tau2=float(tau2))
