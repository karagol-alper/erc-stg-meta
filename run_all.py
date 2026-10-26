"""
run_all.py - reproducible pipeline for the ERC Starting Grant call-level meta-analysis
(gender and geographic disparities in success rates, quantitative bias analysis,
and the selection-mechanism policy simulator).

Usage:  python run_all.py        (~1-2 min on one CPU; outputs written to ./outputs)
"""
from __future__ import annotations

import json, time, sys, os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from erc_meta.data import (CALLS, CALLS_IMPUTED, HISTORICAL, analytic_table, provenance_table, two_by_two, Call)
from erc_meta import core, bayes, bias, geo, plots, policy, dynamics, domains

T0 = time.time()
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")
FIG, TAB = os.path.join(OUT, "figures"), os.path.join(OUT, "tables")
os.makedirs(FIG, exist_ok=True); os.makedirs(TAB, exist_ok=True)
R = {}


def log(msg):
    print(f"[{time.time() - T0:6.1f}s] {msg}", flush=True)


DROP = {"post", "pm", "pt", "theta_new", "pred", "y", "v", "sys_only", "per_call", "draws", "conf_or", "y_fill", "v_fill", "weights", "density"}


def jsonable(o):
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items() if k not in DROP}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, float) and np.isnan(o):
        return None
    return o


# ============================================================================ #
# 1. Data
# ============================================================================ #
log("Assembling analytic tables")
df = analytic_table()
provenance_table().to_csv(f"{TAB}/table0_provenance.csv", index=False)
df.to_csv(f"{TAB}/table1_analytic_2x2.csv", index=False)
a, b, c, d = (df[k].values.astype(float) for k in "abcd")
y, v = core.log_or(a, b, c, d)
y_rr, v_rr = core.log_rr(a, b, c, d)
y_rd, v_rd = core.risk_diff(a, b, c, d)
df_es = df.copy()
df_es["logOR"], df_es["var_logOR"] = y, v
df_es["OR"], df_es["OR_lo"], df_es["OR_hi"] = np.exp(y), np.exp(y - 1.96 * np.sqrt(v)), np.exp(y + 1.96 * np.sqrt(v))
df_es["RR"] = np.exp(y_rr)
df_es["RD_pp"] = 100 * y_rd
df_es["RD_lo_pp"], df_es["RD_hi_pp"] = 100 * (y_rd - 1.96 * np.sqrt(v_rd)), 100 * (y_rd + 1.96 * np.sqrt(v_rd))
df_es.round(4).to_csv(f"{TAB}/table1b_effect_sizes.csv", index=False)
R["data"] = dict(k=len(df), n_applications=int(df.n.sum()), n_women=int(df.n_w.sum()), n_men=int(df.n_m.sum()),
                 grants_women=int(df.a.sum()), grants_men=int(df.c.sum()), years=[int(x) for x in df.year],
                 crude_sr_women=float(df.a.sum() / df.n_w.sum()), crude_sr_men=float(df.c.sum() / df.n_m.sum()))

# ============================================================================ #
# 2. Pooling
# ============================================================================ #
log("Pooling (IV-FE, MH, Peto, DL, PM, REML, HKSJ)")
pooled = {"IV_FE": core.pool(y, v, "FE"), "MH": core.mantel_haenszel_or(a, b, c, d), "Peto": core.peto_or(a, b, c, d),
          "DL": core.pool(y, v, "DL"), "PM": core.pool(y, v, "PM"), "REML": core.pool(y, v, "REML"),
          "REML_HKSJ": core.pool(y, v, "REML", hksj=True), "DL_HKSJ": core.pool(y, v, "DL", hksj=True)}
RE = pooled["REML_HKSJ"]
pd.DataFrame([dict(model=k, **r.as_dict()) for k, r in pooled.items()]).round(4).to_csv(f"{TAB}/table2_pooled_OR.csv", index=False)
R["pooled_OR"] = {k: r.as_dict() for k, r in pooled.items()}
rr_re = core.pool(y_rr, v_rr, "REML", hksj=True)
rd_re = core.pool(y_rd, v_rd, "REML", hksj=True)
R["pooled_RR"] = rr_re.as_dict()
R["pooled_RD_pp"] = rd_re.as_dict(transform=lambda z: 100 * z)
pd.DataFrame([dict(measure="RR", **rr_re.as_dict()), dict(measure="RD (pp)", **rd_re.as_dict(transform=lambda z: 100 * z))]
             ).round(4).to_csv(f"{TAB}/table2b_pooled_RR_RD.csv", index=False)

# ============================================================================ #
# 3. Meta-regression, cumulative, influence
# ============================================================================ #
log("Meta-regression on call year and era (REML/KH + permutation tests)")
X = np.column_stack([np.ones(len(y)), df.year.values - df.year.values.mean()])
mr = core.meta_regression(y, v, X, names=["intercept", "year_centred"], n_perm=5000)
R["metareg_year"] = dict(beta=mr.beta.tolist(), se=mr.se.tolist(), ci_lo=mr.ci_lo.tolist(), ci_hi=mr.ci_hi.tolist(),
                         t=mr.t.tolist(), p=mr.p.tolist(), perm_p=mr.perm_p, n_perm=mr.n_perm, tau2=mr.tau2,
                         tau2_re=mr.tau2_re, R2=mr.R2, QE=mr.QE, p_QE=mr.p_QE, QM=mr.QM, p_QM=mr.p_QM,
                         or_change_per_decade=float(np.exp(10 * mr.beta[1])))
era = (df.year.values >= 2021).astype(float)
mre = core.meta_regression(y, v, np.column_stack([np.ones(len(y)), era]), names=["intercept", "HorizonEurope"], n_perm=5000)
R["metareg_era"] = dict(beta=mre.beta.tolist(), se=mre.se.tolist(), p=mre.p.tolist(), perm_p=mre.perm_p,
                        or_ratio=float(np.exp(mre.beta[1])), ci=[float(np.exp(mre.ci_lo[1])), float(np.exp(mre.ci_hi[1]))])
rows = []
for lab, m_ in [("year (centred)", mr), ("era (HE vs H2020)", mre)]:
    for n_, b_, s_, l_, h_, t_, p_ in zip(m_.names, m_.beta, m_.se, m_.ci_lo, m_.ci_hi, m_.t, m_.p):
        rows.append(dict(model=lab, term=n_, beta=b_, se=s_, ci_lo=l_, ci_hi=h_, t=t_, p_KH=p_, perm_p=m_.perm_p,
                         tau2_resid=m_.tau2, QE=m_.QE, p_QE=m_.p_QE))
pd.DataFrame(rows).round(5).to_csv(f"{TAB}/table3_metaregression.csv", index=False)

log("Cumulative, leave-one-out, Baujat")
cum = core.cumulative(y, v, df.year.values)
loo = core.leave_one_out(y, v)
bj = core.baujat(y, v)
infl = pd.DataFrame(loo); infl.insert(0, "omitted_call", df.year.values)
infl["OR"], infl["OR_lo"], infl["OR_hi"] = np.exp(infl.est), np.exp(infl.lo), np.exp(infl.hi)
infl["Q_contribution"], infl["baujat_influence"] = bj[0], bj[1]
infl.round(4).to_csv(f"{TAB}/table4_influence.csv", index=False)
cum_df = pd.DataFrame(cum); cum_df.insert(0, "through_call", np.sort(df.year.values))
cum_df["OR"], cum_df["OR_lo"], cum_df["OR_hi"] = np.exp(cum_df.est), np.exp(cum_df.lo), np.exp(cum_df.hi)
cum_df.round(4).to_csv(f"{TAB}/table4b_cumulative.csv", index=False)
R["influence"] = dict(max_cook=float(infl.cook.max()), max_cook_call=int(infl.omitted_call[infl.cook.idxmax()]),
                      loo_OR_range=[float(infl.OR.min()), float(infl.OR.max())],
                      max_abs_rstudent=float(infl.rstudent.abs().max()))

# ============================================================================ #
# 4. Small-study effects
# ============================================================================ #
log("Small-study effects")
eg, pt, bg = core.egger_test(y, v), core.peters_test(a, b, c, d), core.begg_test(y, v)
tf, pp, lm = core.trim_and_fill(y, v), core.pet_peese(y, v), core.limit_meta(y, v)
R["small_study"] = dict(egger=eg, peters=pt, begg=bg,
                        trim_fill=dict(k0=tf["k0"], side=tf["side"], OR=float(np.exp(tf["est"])),
                                       lo=float(np.exp(tf["lo"])), hi=float(np.exp(tf["hi"]))),
                        pet_peese=dict(chosen=pp["chosen"], OR=float(np.exp(pp["est"])), lo=float(np.exp(pp["lo"])),
                                       hi=float(np.exp(pp["hi"])), PET=pp["PET"], PEESE=pp["PEESE"]),
                        limit=dict(OR=float(np.exp(lm["est"])), se=lm["se"], p_bias=lm["p_bias"]),
                        se_range=[float(np.sqrt(v).min()), float(np.sqrt(v).max())],
                        note="PET-PEESE and limit meta-analysis extrapolate to SE = 0; with SE varying only "
                             "between the values in se_range they are not identified and are reported for completeness only.")

# ============================================================================ #
# 5. Bayesian analysis
# ============================================================================ #
log("Bayesian grid posteriors (normal-normal and exact-conditional hypergeometric-normal)")
mu_g, tau_g = bayes.make_grid()
ll_nn = bayes.loglik_nn(y, v, mu_g, tau_g)
ll_hn = bayes.loglik_hn(df[["a", "n_w", "n_m", "g"]].to_dict("records"), mu_g, tau_g)
prior_sets = {"weakly informative (mu~N(0,1), tau~HN(0.5))": (1.0, 0.5),
              "sceptical (mu~N(0,0.2), tau~HN(0.5))": (0.2, 0.5),
              "strong shrinkage (mu~N(0,1), tau~HN(0.1))": (1.0, 0.1)}
fits_nn = {k: bayes.fit_grid(ll_nn, mu_g, tau_g, *p) for k, p in prior_sets.items()}
fits_hn = {k: bayes.fit_grid(ll_hn, mu_g, tau_g, *p) for k, p in prior_sets.items()}
mle_hn, mle_nn = bayes.profile_mle(ll_hn, mu_g, tau_g), bayes.profile_mle(ll_nn, mu_g, tau_g)


def bsum(f):
    return dict(OR_mean=float(np.exp(f["mu_mean"])), OR_median=float(np.exp(f["mu_q"][1])),
                OR_lo=float(np.exp(f["mu_q"][0])), OR_hi=float(np.exp(f["mu_q"][2])),
                tau_median=f["tau_q"][1], tau_hi=f["tau_q"][2], P_OR_lt_1=f["p_lt0"], P_ROPE=f["p_rope"],
                P_OR_gt_1p10=f["p_gt_rope"], P_OR_lt_0p91=f["p_lt_rope"], BF10=f["bf10"], BF01=f["bf01"],
                pred_OR_lo=float(np.exp(f["pred_q"][0])), pred_OR_hi=float(np.exp(f["pred_q"][2])))


R["bayes"] = dict(NN={k: bsum(f) for k, f in fits_nn.items()}, HN={k: bsum(f) for k, f in fits_hn.items()},
                  HN_MLE=dict(OR=float(np.exp(mle_hn["mu"])), lo=float(np.exp(mle_hn["lo"])), hi=float(np.exp(mle_hn["hi"])), tau=mle_hn["tau"]),
                  NN_MLE=dict(OR=float(np.exp(mle_nn["mu"])), lo=float(np.exp(mle_nn["lo"])), hi=float(np.exp(mle_nn["hi"])), tau=mle_nn["tau"]))
h = HISTORICAL["fp7_stg"]
n_w_h = int(0.27 * h["n_apps_total"]); n_m_h = h["n_apps_total"] - n_w_h
hist_fits = []
for a0 in [0.0, 0.05, 0.1, 0.25, 0.5, 1.0]:
    lp_h, yh, vh = bayes.historical_loglik(mu_g, h["sr_women"], h["sr_men"], n_w_h, n_m_h, a0)
    f = bayes.fit_grid(ll_hn, mu_g, tau_g, 1.0, 0.5, extra_logprior=lp_h if a0 > 0 else None)
    hist_fits.append(dict(a0=a0, mu_q=f["mu_q"], p_lt0=f["p_lt0"], hist_or=float(np.exp(yh)), hist_se=float(np.sqrt(vh))))
R["bayes"]["power_prior"] = [dict(a0=x["a0"], OR_median=float(np.exp(x["mu_q"][1])), lo=float(np.exp(x["mu_q"][0])),
                                  hi=float(np.exp(x["mu_q"][2])), P_OR_lt_1=x["p_lt0"]) for x in hist_fits]
R["bayes"]["historical_comparator"] = dict(OR=hist_fits[0]["hist_or"], se_logOR=hist_fits[0]["hist_se"],
                                            note="StG 2007-2013: success 8% (women) vs 10% (men), rounded rates; women assumed 27% of applicants")
pd.DataFrame([dict(model="NN", prior=k, **s) for k, s in R["bayes"]["NN"].items()] +
             [dict(model="HN (exact conditional)", prior=k, **s) for k, s in R["bayes"]["HN"].items()]
             ).round(4).to_csv(f"{TAB}/table5_bayes.csv", index=False)
pd.DataFrame(R["bayes"]["power_prior"]).round(4).to_csv(f"{TAB}/table5b_power_prior.csv", index=False)

# ============================================================================ #
# 6. Quantitative bias analysis
# ============================================================================ #
log("Quantitative bias analysis")
ev = bias.evalue_set(float(np.exp(rr_re.est)), float(np.exp(rr_re.ci_lo)), float(np.exp(rr_re.ci_hi)))
or_sqrt = float(np.exp(RE.est)) ** 0.5
ev_or = bias.evalue_set(or_sqrt, float(np.exp(RE.ci_lo)) ** 0.5, float(np.exp(RE.ci_hi)) ** 0.5)
R["evalues"] = dict(RR_based=ev, OR_sqrt_based=ev_or)
pba_me = bias.probabilistic_bias_analysis(CALLS, n_sim=5000, adjust_domain=False, seed=11)
pba_full = bias.probabilistic_bias_analysis(CALLS, n_sim=5000, adjust_domain=True, seed=12)
conf_point = np.array([bias.domain_confounding_or(cc, cc.share_w) for cc in CALLS])
R["pba"] = dict(denominator_only=dict(systematic=bias.summarise_draws(pba_me["sys_only"]), total=bias.summarise_draws(pba_me["total"])),
                denominator_plus_domain=dict(systematic=bias.summarise_draws(pba_full["sys_only"]), total=bias.summarise_draws(pba_full["total"])),
                domain_confounding_OR_point={int(cc.year): float(x) for cc, x in zip(CALLS, conf_point.round(4))},
                conventional=dict(OR=float(np.exp(RE.est)), lo=float(np.exp(RE.ci_lo)), hi=float(np.exp(RE.ci_hi))))
pd.DataFrame([dict(analysis="denominator rounding only", error="systematic", **R["pba"]["denominator_only"]["systematic"]),
              dict(analysis="denominator rounding only", error="systematic+random", **R["pba"]["denominator_only"]["total"]),
              dict(analysis="rounding + domain composition", error="systematic", **R["pba"]["denominator_plus_domain"]["systematic"]),
              dict(analysis="rounding + domain composition", error="systematic+random", **R["pba"]["denominator_plus_domain"]["total"]),
              dict(analysis="conventional REML/HKSJ", error="random", median=R["pba"]["conventional"]["OR"],
                   lo=R["pba"]["conventional"]["lo"], hi=R["pba"]["conventional"]["hi"], p_below_1=np.nan)]
             ).round(4).to_csv(f"{TAB}/table6_pba.csv", index=False)
share_w_all = df.n_w.sum() / df.n.sum()
sr_all = (df.a.sum() + df.c.sum()) / df.n.sum()
sel_rows, breakeven = bias.selection_sensitivity(float(np.exp(RE.est)), share_w_all, sr_all)
R["selection_model"] = dict(breakeven_delta={str(k): v_ for k, v_ in breakeven.items()}, share_w=float(share_w_all),
                            success_rate=float(sr_all),
                            table=[r_ for r_ in sel_rows if round(r_["delta"] * 100) % 10 == 0])
pd.DataFrame(sel_rows).round(4).to_csv(f"{TAB}/table7_selection_sensitivity.csv", index=False)

# ============================================================================ #
# 7. Sensitivity analyses
# ============================================================================ #
log("Sensitivity analyses")
sens = {}
df_nb = analytic_table(exclude_nb_from_n=True)
yy, vv = core.log_or(*(df_nb[k].values.astype(float) for k in "abcd"))
sens["exclude_nonbinary_from_denominator"] = core.pool(yy, vv, "REML", hksj=True).as_dict()
calls_2023u = [Call(**{**cc.__dict__, "g_female": 173, "g_male": 224, "g_nonbinary": 1, "g_total": 398}) if cc.year == 2023 else cc
               for cc in CALLS]
df_u = analytic_table(calls_2023u)
yy, vv = core.log_or(*(df_u[k].values.astype(float) for k in "abcd"))
sens["updated_2023_reserve_list_counts"] = core.pool(yy, vv, "REML", hksj=True).as_dict()
rng = np.random.default_rng(7)
calls_ext = CALLS_IMPUTED + CALLS
ext_draws = []
for _ in range(4000):
    ys_, vs_ = [], []
    for cc in calls_ext:
        t = two_by_two(cc, share=rng.uniform(cc.share_w_lo / 100, cc.share_w_hi / 100))
        y_, v_ = core.log_or(t["a"], t["b"], t["c"], t["d"])
        ys_.append(y_); vs_.append(v_)
    r_ = core.pool(np.array(ys_), np.array(vs_), "DL")
    ext_draws.append((r_.est, r_.se, r_.tau2, r_.I2))
ext_draws = np.array(ext_draws)
tot = rng.normal(ext_draws[:, 0], ext_draws[:, 1])
sens["extended_2015_2026_imputed_MC"] = dict(OR_median=float(np.exp(np.median(ext_draws[:, 0]))),
                                             lo_total=float(np.exp(np.percentile(tot, 2.5))), hi_total=float(np.exp(np.percentile(tot, 97.5))),
                                             tau2_median=float(np.median(ext_draws[:, 2])), I2_median=float(np.median(ext_draws[:, 3])),
                                             I2_q975=float(np.percentile(ext_draws[:, 3], 97.5)))
df_ext = analytic_table(calls_ext)
y_ext, v_ext = core.log_or(*(df_ext[k].values.astype(float) for k in "abcd"))
res_ext = core.pool(y_ext, v_ext, "REML", hksj=True)
sens["extended_point_imputation"] = res_ext.as_dict()
mr_ext = core.meta_regression(y_ext, v_ext, np.column_stack([np.ones(len(y_ext)), df_ext.year.values - df_ext.year.values.mean()]), n_perm=5000)
sens["extended_trend"] = dict(slope=float(mr_ext.beta[1]), se=float(mr_ext.se[1]), p_KH=float(mr_ext.p[1]),
                              perm_p=float(mr_ext.perm_p), or_ratio_per_decade=float(np.exp(10 * mr_ext.beta[1])))
lo_h = (0.075 / 0.925) / (0.105 / 0.895); hi_h = (0.085 / 0.915) / (0.095 / 0.905)
sens["fp7_comparator_OR_range"] = dict(point=(0.08 / 0.92) / (0.10 / 0.90), lo=lo_h, hi=hi_h)
sens["stg_2007_2016_share_based_OR"] = dict(value=float((0.27 / 0.73) / (0.31 / 0.69)))
R["sensitivity"] = sens
pd.DataFrame([dict(analysis=k, **vv_) for k, vv_ in sens.items()]).round(4).to_csv(f"{TAB}/table8_sensitivity.csv", index=False)

# ============================================================================ #
# 8. Counterfactual grant gap
# ============================================================================ #
exp_w = df.n_w * (df.c / df.n_m)
excess = df.a - exp_w
se_ex = df.n_w * np.sqrt((df.c / df.n_m) * (1 - df.c / df.n_m) / df.n_m + (df.a / df.n_w) * (1 - df.a / df.n_w) / df.n_w)
gap = pd.DataFrame(dict(year=df.year, women_funded=df.a, expected_if_men_rate=exp_w.round(1), excess=excess.round(1),
                        excess_lo=(excess - 1.96 * se_ex).round(1), excess_hi=(excess + 1.96 * se_ex).round(1)))
gap.to_csv(f"{TAB}/table9_counterfactual_gap.csv", index=False)
R["counterfactual"] = dict(cumulative_excess_women_grants=float(excess.sum()),
                           lo=float(excess.sum() - 1.96 * np.sqrt(np.sum(se_ex ** 2))), hi=float(excess.sum() + 1.96 * np.sqrt(np.sum(se_ex ** 2))))

# ============================================================================ #
# 9. Geography
# ============================================================================ #
log("Geographic module")
tab_geo, tab_geo_any = geo.widening_table("widening_eu"), geo.widening_table("widening_any")
ps, ps_any = geo.pool_share(tab_geo), geo.pool_share(tab_geo_any)
sgrs = geo.sgr_scenarios(tab_geo)
tab_geo.round(4).to_csv(f"{TAB}/table10_geo_widening.csv", index=False)
R["geo"] = dict(widening_eu={k: vv_ for k, vv_ in ps.items() if k not in ("y", "v")},
                widening_any={k: vv_ for k, vv_ in ps_any.items() if k not in ("y", "v")},
                sgr=[dict(applicant_share=s["applicant_share"], pooled=s["sgr_pooled"], lo=s["lo"], hi=s["hi"]) for s in sgrs],
                implied_success_ratio={str(sa): float(geo.implied_success_ratio(ps["share"], sa)) for sa in (0.10, 0.125, 0.15, 0.25)},
                concentration=dict(gini_mean=float(tab_geo.gini.mean()), top3_mean=float(tab_geo.top3.mean()),
                                   top5_mean=float(tab_geo.top5.mean()), hhi_mean=float(tab_geo.hhi.mean())))

# ============================================================================ #
# 10. Policy simulator: peer review reliability vs. lotteries
# ============================================================================ #
log("Policy simulator (selection mechanisms)")
pol = policy.run_policy_simulation(success_rate=float(sr_all), share_w=float(share_w_all), n_sim=200, seed=3)
pol["table"].round(4).to_csv(f"{TAB}/table11_policy_simulation.csv", index=False)
R["policy"] = pol["summary"]

# ============================================================================ #
# 10b. Competition dynamics
# ============================================================================ #
log("Competition dynamics (success-rate meta-analysis, decomposition, elasticity, application tax, women's share trend)")
dyn = dynamics.run_dynamics(n_perm=5000)
dyn["series"].round(4).to_csv(f"{TAB}/table12_competition_series.csv", index=False)
dyn["decomposition"].round(4).to_csv(f"{TAB}/table12b_success_rate_decomposition.csv", index=False)
dyn["tax"].round(3).to_csv(f"{TAB}/table12c_application_tax.csv", index=False)
dyn["women"]["gap_table"].round(4).to_csv(f"{TAB}/table12d_women_share_gap.csv", index=False)
dyn["sr_meta"]["cohort_or"].round(3).to_csv(f"{TAB}/table12e_cohort_odds_ratios.csv")
R["dynamics"] = dyn["summary"]

# ============================================================================ #
# 10c. Domains
# ============================================================================ #
log("Domain module (neutrality of success rates, rate ratios, shares, gender x domain bounds)")
dm = domains.run_domains()
dm["neutrality"].round(4).to_csv(f"{TAB}/table13_domain_neutrality.csv", index=False)
dm["gender_domain"].round(4).to_csv(f"{TAB}/table13b_gender_by_domain_2025_scenarios.csv", index=False)
R["domains"] = dm["summary"]

# ============================================================================ #
# 10d. Geography: country shares, association shocks, rank stability, reallocation
# ============================================================================ #
log("Country shares, association-status contrasts, rank stability, reallocation to parity")
ctab = geo.country_share_table()
ctab.round(4).to_csv(f"{TAB}/table14_country_shares.csv", index=False)
contrasts = [geo.period_contrast(ctab, "UK", n_perm=3000), geo.period_contrast(ctab, "CH", n_perm=3000)]
rank_tab, rank_fl = geo.rank_stability()
realloc = geo.reallocation_to_parity(tab_geo)
realloc.round(3).to_csv(f"{TAB}/table14b_reallocation_to_parity.csv", index=False)
de = ctab[ctab.country == "DE"]
R["geo"]["association_contrasts"] = contrasts
R["geo"]["rank_stability"] = dict(consecutive_spearman_min=float(rank_tab.spearman.min()), consecutive_spearman_median=float(rank_tab.spearman.median()), **rank_fl)
R["geo"]["reallocation_to_parity"] = realloc.to_dict("records")
R["geo"]["DE_share_first_last"] = [float(de.share.iloc[0]), float(de.share.iloc[-1])]
R["geo"]["UK_share_first_last"] = [float(ctab[ctab.country == "UK"].share.iloc[0]), float(ctab[ctab.country == "UK"].share.iloc[-1])]
gini_X = np.column_stack([np.ones(len(tab_geo)), tab_geo.year.values - tab_geo.year.mean()])
gini_b = np.linalg.lstsq(gini_X, tab_geo.gini.values, rcond=None)[0]
R["geo"]["gini_trend_per_year"] = float(gini_b[1])

# ============================================================================ #
# 10e. Evidence-to-decision: reliability meta-analysis feeding the simulator
# ============================================================================ #
log("Reliability meta-analysis and propagation into the selection simulator")
rel = policy.reliability_meta()
prop = policy.propagate_reliability(pol["table"], rel, n_raters=5)
R["policy"]["reliability_meta"] = rel
R["policy"]["propagated"] = {k: v for k, v in prop.items() if k != "draws"}
pd.DataFrame([dict(k=k, **(v if isinstance(v, dict) else {"value": v})) for k, v in prop.items() if k != "draws"]).to_csv(f"{TAB}/table15_reliability_propagation.csv", index=False)

# ============================================================================ #
# 11. Figures
# ============================================================================ #
log("Figures")
plots.forest(df, y, v, RE, pooled["MH"], f"{FIG}/fig01_forest.png")
plots.success_rates(df, f"{FIG}/fig02_success_rates.png")
plots.cumulative_loo(df, cum, loo, RE, f"{FIG}/fig03_cumulative_loo.png")
plots.funnel_baujat(df, y, v, RE, eg, tf, bj, f"{FIG}/fig04_funnel_baujat.png")
plots.metareg(df, y, v, mr, RE, f"{FIG}/fig05_metaregression_year.png")
plots.bayes_fig(fits_hn, hist_fits[1:], f"{FIG}/fig06_bayesian.png")
plots.bias_fig(pba_me, pba_full, RE, pba_full["conf_or"], dict(years=df.year.values, **ev), f"{FIG}/fig07_bias_analysis.png")
plots.selection_fig(sel_rows, breakeven, float(np.exp(RE.est)), (float(np.exp(RE.ci_lo)), float(np.exp(RE.ci_hi))),
                    f"{FIG}/fig08_selection_sensitivity.png")
plots.geo_fig(tab_geo, ps, sgrs, f"{FIG}/fig09_geography.png")
plots.extended_fig(df_ext, y_ext, v_ext, np.array([cc.share_w_text.startswith("IMPUTED") for cc in calls_ext]),
                   RE, res_ext, (sens["fp7_comparator_OR_range"]["point"], lo_h, hi_h), f"{FIG}/fig10_extended_series.png")
policy.policy_fig(pol, f"{FIG}/fig11_policy_simulation.png")
dynamics.dynamics_fig(dyn, f"{FIG}/fig12_competition_dynamics.png")
domains.domains_fig(dm, f"{FIG}/fig13_domains.png")
geo.country_fig(ctab, contrasts, tab_geo, f"{FIG}/fig14_country_shares_association.png")
policy.reliability_fig(rel, prop, f"{FIG}/fig15_reliability_to_policy.png")

# ============================================================================ #
# 12. Save
# ============================================================================ #
with open(f"{OUT}/results.json", "w") as fh:
    json.dump(jsonable(R), fh, indent=2, default=lambda o: o.item() if hasattr(o, "item") else str(o))

L = ["# Auto-generated key results (run_all.py)\n"]
D = R["data"]
L.append(f"- Calls: {D['k']} (2017-2026); applications {D['n_applications']:,} (women {D['n_women']:,}, men {D['n_men']:,}); "
         f"grants to women {D['grants_women']:,}, to men {D['grants_men']:,}.")
L.append(f"- Crude success: women {100 * D['crude_sr_women']:.2f}% vs men {100 * D['crude_sr_men']:.2f}%.")
for k_ in ["MH", "Peto", "IV_FE", "DL", "PM", "REML", "REML_HKSJ", "DL_HKSJ"]:
    p_ = R["pooled_OR"][k_]
    L.append(f"- {k_}: OR {p_['est']:.3f} [{p_['lo']:.3f}, {p_['hi']:.3f}], p = {p_['p']:.4f}, tau2 = {p_['tau2']:.5f}")
p_ = R["pooled_OR"]["REML_HKSJ"]
L.append(f"- Heterogeneity: Q = {p_['Q']:.2f} (df {p_['df']}, p = {p_['p_Q']:.3f}); I2 = {100 * p_['I2']:.1f}% [{100 * p_['I2_lo']:.0f}, {100 * p_['I2_hi']:.0f}]; "
         f"tau2 = {p_['tau2']:.5f} [{p_['tau2_lo']:.4f}, {p_['tau2_hi']:.4f}]; PI [{p_['pi_lo']:.3f}, {p_['pi_hi']:.3f}]")
L.append(f"- RR {R['pooled_RR']['est']:.3f} [{R['pooled_RR']['lo']:.3f}, {R['pooled_RR']['hi']:.3f}]; RD {R['pooled_RD_pp']['est']:.2f} pp "
         f"[{R['pooled_RD_pp']['lo']:.2f}, {R['pooled_RD_pp']['hi']:.2f}]")
m_ = R["metareg_year"]
L.append(f"- Trend: {m_['beta'][1]:+.4f} logOR/yr (95% CI {m_['ci_lo'][1]:+.4f}, {m_['ci_hi'][1]:+.4f}); KH p = {m_['p'][1]:.3f}; "
         f"perm p = {m_['perm_p']:.3f}; OR ratio per decade {m_['or_change_per_decade']:.3f}; residual tau2 {m_['tau2']:.5f}")
e_ = R["metareg_era"]
L.append(f"- Era (HE vs H2020): OR ratio {e_['or_ratio']:.3f} [{e_['ci'][0]:.3f}, {e_['ci'][1]:.3f}], KH p = {e_['p'][1]:.3f}, perm p = {e_['perm_p']:.3f}")
s_ = R["small_study"]
L.append(f"- Egger intercept {s_['egger']['intercept']:.2f} (p = {s_['egger']['p']:.3f}); Peters p = {s_['peters']['p']:.3f}; Begg p = {s_['begg']['p']:.3f}; "
         f"trim-fill k0 = {s_['trim_fill']['k0']} ({s_['trim_fill']['side']}), OR {s_['trim_fill']['OR']:.3f} [{s_['trim_fill']['lo']:.3f}, {s_['trim_fill']['hi']:.3f}]; "
         f"PET-PEESE ({s_['pet_peese']['chosen']}) {s_['pet_peese']['OR']:.2f}; limit {s_['limit']['OR']:.2f}; SE range {s_['se_range'][0]:.3f}-{s_['se_range'][1]:.3f}")
L.append(f"- Influence: LOO OR range {R['influence']['loo_OR_range'][0]:.3f}-{R['influence']['loo_OR_range'][1]:.3f}; max Cook's D {R['influence']['max_cook']:.2f} ({R['influence']['max_cook_call']}); max |rstudent| {R['influence']['max_abs_rstudent']:.2f}")
for mdl in ["NN", "HN"]:
    for k_, s2 in R["bayes"][mdl].items():
        L.append(f"- Bayes {mdl} {k_}: OR {s2['OR_median']:.3f} [{s2['OR_lo']:.3f}, {s2['OR_hi']:.3f}]; tau med {s2['tau_median']:.3f} (97.5% {s2['tau_hi']:.3f}); "
                 f"P(OR<1) = {s2['P_OR_lt_1']:.3f}; P(ROPE 0.91-1.10) = {s2['P_ROPE']:.3f}; P(OR>1.10) = {s2['P_OR_gt_1p10']:.3f}; BF10 = {s2['BF10']:.2f}; "
                 f"pred [{s2['pred_OR_lo']:.3f}, {s2['pred_OR_hi']:.3f}]")
L.append(f"- HN MLE: OR {R['bayes']['HN_MLE']['OR']:.3f} [{R['bayes']['HN_MLE']['lo']:.3f}, {R['bayes']['HN_MLE']['hi']:.3f}], tau {R['bayes']['HN_MLE']['tau']:.3f}")
L.append(f"- Historical comparator: OR {R['bayes']['historical_comparator']['OR']:.3f} (SE log {R['bayes']['historical_comparator']['se_logOR']:.3f})")
for x in R["bayes"]["power_prior"]:
    L.append(f"- Power prior a0={x['a0']}: OR {x['OR_median']:.3f} [{x['lo']:.3f}, {x['hi']:.3f}], P(OR<1) = {x['P_OR_lt_1']:.3f}")
L.append(f"- E-values (RR): point {ev['evalue_point']:.2f}, CI {ev['evalue_ci']:.2f}; mask true RR 0.95: {ev['evalue_true_0.95']:.2f} (CI {ev['evalue_ci_true_0.95']:.2f}); "
         f"mask true RR 0.90: {ev['evalue_true_0.9']:.2f} (CI {ev['evalue_ci_true_0.9']:.2f})")
for k_, s2 in R["pba"].items():
    if isinstance(s2, dict) and "systematic" in s2:
        L.append(f"- PBA {k_}: systematic {s2['systematic']['median']:.3f} [{s2['systematic']['lo']:.3f}, {s2['systematic']['hi']:.3f}]; "
                 f"total {s2['total']['median']:.3f} [{s2['total']['lo']:.3f}, {s2['total']['hi']:.3f}]; P(OR<1) = {s2['total']['p_below_1']:.3f}")
L.append(f"- Domain confounding OR by call: {R['pba']['domain_confounding_OR_point']}")
L.append(f"- Selection model (share_w {share_w_all:.3f}, success {sr_all:.4f}): break-even delta {R['selection_model']['breakeven_delta']}")
L.append("- Selection table (rho, delta, fair OR, implied evaluation OR): " +
         "; ".join(f"({r_['rho']}, {r_['delta']:.1f}, {r_['or_fair']:.3f}, {r_['implied_eval_or']:.3f})" for r_ in R["selection_model"]["table"]))
for k_, s2 in sens.items():
    L.append(f"- Sensitivity {k_}: " + ", ".join(f"{kk}={vv_:.4f}" if isinstance(vv_, float) else f"{kk}={vv_}" for kk, vv_ in s2.items()
                                                 if kk in ("est", "lo", "hi", "p", "tau2", "I2", "OR_median", "lo_total", "hi_total", "tau2_median",
                                                           "I2_median", "I2_q975", "slope", "se", "p_KH", "perm_p", "or_ratio_per_decade", "point", "value")))
L.append(f"- Counterfactual excess women grants 2017-2026: {R['counterfactual']['cumulative_excess_women_grants']:.1f} [{R['counterfactual']['lo']:.1f}, {R['counterfactual']['hi']:.1f}]")
g_ = R["geo"]
L.append(f"- Widening (EU) share of grants: {100 * g_['widening_eu']['share']:.2f}% [{100 * g_['widening_eu']['lo']:.2f}, {100 * g_['widening_eu']['hi']:.2f}]; "
         f"I2 = {100 * g_['widening_eu']['I2']:.0f}%; Q p = {g_['widening_eu']['p_Q']:.2f}; trend {g_['widening_eu']['trend_beta']:+.4f}/yr, KH p = {g_['widening_eu']['trend_p']:.3f} "
         f"(perm {g_['widening_eu']['trend_perm_p']:.3f}); PI [{100 * g_['widening_eu']['pi_lo']:.2f}, {100 * g_['widening_eu']['pi_hi']:.2f}]; "
         f"incl. associated: {100 * g_['widening_any']['share']:.2f}% [{100 * g_['widening_any']['lo']:.2f}, {100 * g_['widening_any']['hi']:.2f}]")
for s2 in g_["sgr"]:
    L.append(f"- SGR (applicant share {s2['applicant_share']}): {s2['pooled']:.3f} [{s2['lo']:.3f}, {s2['hi']:.3f}]")
L.append(f"- Implied success-rate ratio widening vs rest: " + ", ".join(f"{k_}: {vv_:.3f}" for k_, vv_ in g_['implied_success_ratio'].items()))
L.append(f"- Concentration: Gini {g_['concentration']['gini_mean']:.3f}, HHI {g_['concentration']['hhi_mean']:.3f}, top-3 {100 * g_['concentration']['top3_mean']:.1f}%, top-5 {100 * g_['concentration']['top5_mean']:.1f}%")
L.append("- Policy simulation summary: " + json.dumps(jsonable({k: v for k, v in R["policy"].items() if k not in ("reliability_meta", "propagated")})))
L.append("- Reliability meta-analysis: " + json.dumps(jsonable(rel)))
L.append("- Propagated policy effects: " + json.dumps(jsonable(R["policy"]["propagated"])))
L.append("- Dynamics: " + json.dumps(jsonable(R["dynamics"])))
L.append("- Domains: " + json.dumps(jsonable(R["domains"])))
L.append("- Association contrasts: " + json.dumps(jsonable(contrasts)))
L.append("- Rank stability: " + json.dumps(jsonable(R["geo"]["rank_stability"])) + f"; Gini trend/yr {R['geo']['gini_trend_per_year']:+.4f}; DE share {R['geo']['DE_share_first_last']}; UK share {R['geo']['UK_share_first_last']}")
L.append("- Reallocation to parity: " + json.dumps(jsonable(R["geo"]["reallocation_to_parity"])))
L.append(f"\nPer-call effect sizes:\n{df_es[['year', 'n_w', 'a', 'n_m', 'c', 'p_w', 'p_m', 'OR', 'OR_lo', 'OR_hi', 'RD_pp', 'RD_lo_pp', 'RD_hi_pp']].round(4).to_string(index=False)}")
L.append(f"\nCumulative:\n{cum_df[['through_call', 'k', 'OR', 'OR_lo', 'OR_hi', 'tau2']].round(4).to_string(index=False)}")
L.append(f"\nInfluence:\n{infl[['omitted_call', 'OR', 'OR_lo', 'OR_hi', 'cook', 'rstudent', 'Q_contribution']].round(3).to_string(index=False)}")
L.append(f"\nCounterfactual gap:\n{gap.to_string(index=False)}")
L.append(f"\nGeography:\n{tab_geo.round(3).to_string(index=False)}")
L.append(f"\nPolicy simulation:\n{pol['table'].round(3).to_string(index=False)}")
L.append(f"\nDecomposition:\n{dyn['decomposition'].round(3).to_string(index=False)}")
L.append(f"\nDomain neutrality:\n{dm['neutrality'].round(3).to_string(index=False)}")
L.append(f"\nGender x domain 2025 scenarios:\n{dm['gender_domain'].round(3).to_string(index=False)}")
L.append(f"\nCountry shares:\n{ctab.pivot(index='year', columns='country', values='share').round(3).to_string()}")
with open(f"{OUT}/key_results.md", "w") as fh:
    fh.write("\n".join(L))
log("Done.")
