"""
erc_meta.bayes
==============
Bayesian random-effects meta-analysis by deterministic numerical integration
(no MCMC, hence no convergence diagnostics to worry about and bit-for-bit
reproducibility).

Two likelihoods
---------------
1. Normal-normal (NN):  y_i | theta_i ~ N(theta_i, v_i),  theta_i ~ N(mu, tau^2)
   => y_i | mu, tau ~ N(mu, v_i + tau^2) (theta_i integrated analytically).

2. Hypergeometric-normal (HN, "exact conditional"):  conditional on the
   margins of the i-th 2x2 table, the number of funded women a_i follows
   Fisher's non-central hypergeometric distribution with odds ratio
   psi_i = exp(theta_i); theta_i ~ N(mu, tau^2).  The exact conditional
   log-likelihood l_i(theta) is tabulated on a fine theta grid and the
   integral over theta_i is evaluated by quadrature for every (mu, tau) node.
   This avoids the normal approximation to the log OR (Stijnen et al. 2010).

Priors
------
mu  ~ N(0, s_mu^2)         (s_mu = 1: weakly informative; 0.2: sceptical)
tau ~ Half-Normal(s_tau)   (s_tau = 0.5 weakly informative; 0.1 strong shrinkage)
Optional historical power prior: L_hist(mu)^{a0} from the FP7-era aggregate.

Outputs: posterior summaries for mu (and exp(mu)), tau, posterior
probabilities for regions of practical equivalence, Savage-Dickey Bayes
factor for mu = 0, and the posterior predictive distribution of the effect
in a new call.
"""
from __future__ import annotations

import numpy as np
from scipy import stats
from scipy.special import gammaln, logsumexp


# --------------------------------------------------------------------------- #
# Grids and priors
# --------------------------------------------------------------------------- #
def make_grid(mu_lim=(-0.8, 0.8), n_mu=321, tau_max=1.0, n_tau=161):
    mu = np.linspace(mu_lim[0], mu_lim[1], n_mu)
    tau = np.linspace(0.0, tau_max, n_tau)
    return mu, tau


def log_prior(mu, tau, s_mu=1.0, s_tau=0.5):
    lp_mu = stats.norm.logpdf(mu, 0, s_mu)
    lp_tau = stats.halfnorm.logpdf(tau, 0, s_tau)
    return lp_mu[:, None] + lp_tau[None, :]


# --------------------------------------------------------------------------- #
# Normal-normal marginal log-likelihood on the grid
# --------------------------------------------------------------------------- #
def loglik_nn(y, v, mu, tau):
    y, v = np.asarray(y, float), np.asarray(v, float)
    var = v[None, None, :] + tau[None, :, None] ** 2
    ll = -0.5 * (np.log(2 * np.pi * var) + (y[None, None, :] - mu[:, None, None]) ** 2 / var)
    return ll.sum(axis=2)


# --------------------------------------------------------------------------- #
# Exact conditional (non-central hypergeometric) log-likelihood
# --------------------------------------------------------------------------- #
def _log_choose(n, k):
    return gammaln(n + 1) - gammaln(k + 1) - gammaln(n - k + 1)


def conditional_loglik_table(a, n_w, n_m, g, theta):
    """log P(A = a | margins, theta) for Fisher's NCH distribution on a vector of theta."""
    x_lo, x_hi = max(0, g - n_m), min(n_w, g)
    x = np.arange(x_lo, x_hi + 1)
    base = _log_choose(n_w, x) + _log_choose(n_m, g - x)
    # log normaliser for each theta: logsumexp_x [base_x + x*theta]
    lognorm = logsumexp(base[None, :] + x[None, :] * theta[:, None], axis=1)
    return _log_choose(n_w, a) + _log_choose(n_m, g - a) + a * theta - lognorm


def loglik_hn(tables, mu, tau, theta_grid=None):
    """Marginal log-likelihood of the HN model on the (mu, tau) grid.

    tables: iterable of dicts with keys a, n_w, n_m, g (per call).
    """
    if theta_grid is None:
        theta_grid = np.linspace(-1.5, 1.5, 2001)
    dth = theta_grid[1] - theta_grid[0]
    total = np.zeros((len(mu), len(tau)))
    l_list = [conditional_loglik_table(t["a"], t["n_w"], t["n_m"], t["g"], theta_grid) for t in tables]
    diff = theta_grid[None, :] - mu[:, None]  # (M, T)
    for j, tj in enumerate(tau):
        if tj <= 0:
            for l_theta in l_list:
                total[:, j] += np.interp(mu, theta_grid, l_theta)  # point mass at theta = mu
            continue
        logk = -0.5 * (diff / tj) ** 2 - np.log(tj) - 0.5 * np.log(2 * np.pi) + np.log(dth)  # (M, T)
        for l_theta in l_list:
            total[:, j] += logsumexp(l_theta[None, :] + logk, axis=1)
    return total


# --------------------------------------------------------------------------- #
# Historical power prior from an aggregate (rounded) comparator
# --------------------------------------------------------------------------- #
def historical_loglik(mu, sr_w, sr_m, n_w, n_m, a0=1.0):
    """Power prior on mu from an aggregate 2x2 comparator (rates rounded => treated as an
    approximate normal likelihood on the log OR)."""
    a, c = sr_w * n_w, sr_m * n_m
    b, d = n_w - a, n_m - c
    y = np.log(a * d / (b * c))
    v = 1 / a + 1 / b + 1 / c + 1 / d
    return a0 * stats.norm.logpdf(mu, y, np.sqrt(v)), float(y), float(v)


# --------------------------------------------------------------------------- #
# Posterior summaries
# --------------------------------------------------------------------------- #
def _normalise(logpost, mu, tau):
    lp = logpost - logpost.max()
    p = np.exp(lp)
    dmu, dtau = mu[1] - mu[0], tau[1] - tau[0]
    p /= p.sum() * dmu * dtau
    return p


def _marg_summary(x, dens, probs=(0.025, 0.5, 0.975)):
    dx = x[1] - x[0]
    dens = dens / (dens.sum() * dx)
    cdf = np.cumsum(dens) * dx
    q = np.interp(probs, cdf, x)
    mean = np.sum(x * dens) * dx
    return dict(mean=float(mean), q=[float(v) for v in q], density=dens)


def fit_grid(loglik, mu, tau, s_mu=1.0, s_tau=0.5, extra_logprior=None, rope=np.log(1.10)):
    lp = loglik + log_prior(mu, tau, s_mu, s_tau)
    if extra_logprior is not None:
        lp = lp + extra_logprior[:, None]
    post = _normalise(lp, mu, tau)
    dmu, dtau = mu[1] - mu[0], tau[1] - tau[0]
    pm = post.sum(axis=1) * dtau
    pt = post.sum(axis=0) * dmu
    sm, st = _marg_summary(mu, pm), _marg_summary(tau, pt)
    # posterior probabilities
    pmn = pm / (pm.sum() * dmu)
    p_lt0 = float(np.sum(pmn[mu < 0]) * dmu)
    p_rope = float(np.sum(pmn[np.abs(mu) < rope]) * dmu)
    p_gt_rope = float(np.sum(pmn[mu > rope]) * dmu)
    p_lt_rope = float(np.sum(pmn[mu < -rope]) * dmu)
    # Savage-Dickey BF01 at mu = 0 (prior marginal density at 0 vs posterior marginal density at 0)
    prior_mu0 = stats.norm.pdf(0, 0, s_mu)
    if extra_logprior is not None:
        prior_mu = np.exp(stats.norm.logpdf(mu, 0, s_mu) + extra_logprior)
        prior_mu /= prior_mu.sum() * dmu
        prior_mu0 = float(np.interp(0.0, mu, prior_mu))
    post_mu0 = float(np.interp(0.0, mu, pmn))
    bf01 = post_mu0 / prior_mu0
    # posterior predictive for a new call: mixture of N(mu, tau^2) over the posterior
    theta_new = np.linspace(-0.8, 0.8, 321)
    pred = np.zeros_like(theta_new)
    dth = theta_new[1] - theta_new[0]
    for j, t in enumerate(tau):
        sd = np.sqrt(t ** 2 + dth ** 2)  # dth^2 : negligible smoothing that keeps the discrete kernel proper
        pred += (post[:, j][:, None] * stats.norm.pdf(theta_new[None, :], mu[:, None], sd)).sum(axis=0) * dmu * dtau
    sp = _marg_summary(theta_new, pred)
    return dict(mu_mean=sm["mean"], mu_q=sm["q"], tau_mean=st["mean"], tau_q=st["q"], p_lt0=p_lt0,
                p_rope=p_rope, p_gt_rope=p_gt_rope, p_lt_rope=p_lt_rope, bf01=float(bf01), bf10=float(1 / bf01),
                pred_q=sp["q"], pred_mean=sp["mean"], post=post, pm=pmn, pt=pt / (pt.sum() * dtau), mu=mu, tau=tau,
                theta_new=theta_new, pred=pred / (pred.sum() * (theta_new[1] - theta_new[0])),
                s_mu=s_mu, s_tau=s_tau)


def profile_mle(loglik, mu, tau):
    """Maximum (marginal) likelihood estimate and profile-likelihood 95% CI for mu."""
    prof = loglik.max(axis=1)
    i = int(np.argmax(prof))
    mu_hat = mu[i]
    tau_hat = tau[int(np.argmax(loglik[i]))]
    crit = prof[i] - 0.5 * stats.chi2.ppf(0.95, 1)
    inside = mu[prof >= crit]
    return dict(mu=float(mu_hat), tau=float(tau_hat), lo=float(inside.min()), hi=float(inside.max()))
