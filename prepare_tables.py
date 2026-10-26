"""prepare_tables.py - format every table needed by the paper and the supplement as JSON."""
import json, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from erc_meta.data import CALLS, CALLS_IMPUTED
T = "outputs/tables"
R = json.load(open("outputs/results.json"))
out = {"main": {}, "supp": {}}


def f(x, d=3):
    try:
        if x is None or (isinstance(x, float) and np.isnan(x)):
            return "–"
        return f"{float(x):.{d}f}"
    except Exception:
        return str(x)


def pct(x, d=1):
    return f"{100 * float(x):.{d}f}"


def ci(e, lo, hi, d=3):
    return f"{f(e, d)} ({f(lo, d)}–{f(hi, d)})"


def tbl(key, title, columns, rows, note="", where="main", widths=None):
    out[where][key] = dict(title=title, columns=columns, rows=[[str(c) for c in r] for r in rows], note=note, widths=widths)


# ---------------- main text tables ----------------
es = pd.read_csv(f"{T}/table1b_effect_sizes.csv")
prov = pd.read_csv(f"{T}/table0_provenance.csv")
rows = []
for _, r in es.iterrows():
    p = prov[prov.call == r.year].iloc[0]
    rows.append([int(r.year), f"{int(p.evaluated_proposals):,}", p.women_share_apps_text.replace(" %", "%"),
                 f"{int(r.a)} / {int(r.n_w):,}", f"{int(r.c)} / {int(r.n_m):,}", pct(r.p_w), pct(r.p_m),
                 ci(r.OR, r.OR_lo, r.OR_hi, 2), f"{r.RD_pp:+.1f}"])
tbl("t1", "Table 1. Per-call data and effect sizes, ERC Starting Grant calls 2017–2026 (women vs men).",
    ["Call", "Evaluated proposals", "Women's share of proposals (ERC wording)", "Women funded / applied", "Men funded / applied",
     "Success women (%)", "Success men (%)", "OR (95% CI)", "RD (pp)"], rows,
    "Women's applicant counts are the midpoint of the published rounding interval multiplied by the number of evaluated proposals; non-binary grantees (14 in total) are excluded from the female/male tables. OR, odds ratio; RD, risk difference in percentage points.",
    widths=[6, 9, 20, 12, 12, 8, 8, 14, 6])

po = pd.read_csv(f"{T}/table2_pooled_OR.csv").set_index("model")
rr = pd.read_csv(f"{T}/table2b_pooled_RR_RD.csv").set_index("measure")
rows = []
for m, lab in [("MH", "Mantel–Haenszel (RBG variance)"), ("Peto", "Peto"), ("IV_FE", "Inverse-variance common effect"),
               ("DL", "DerSimonian–Laird"), ("PM", "Paule–Mandel"), ("REML", "REML"), ("REML_HKSJ", "REML + Hartung–Knapp (primary)"),
               ("DL_HKSJ", "DL + Hartung–Knapp")]:
    r = po.loc[m]
    rows.append([lab, "OR", ci(r.est, r.lo, r.hi), f(r.p), f(r.tau2, 5) if not np.isnan(r.tau2) else "–"])
rows.append(["REML + Hartung–Knapp", "RR", ci(rr.loc["RR"].est, rr.loc["RR"].lo, rr.loc["RR"].hi), f(rr.loc["RR"].p), f(rr.loc["RR"].tau2, 5)])
rows.append(["REML + Hartung–Knapp", "RD (pp)", ci(rr.loc["RD (pp)"].est, rr.loc["RD (pp)"].lo, rr.loc["RD (pp)"].hi, 2), f(rr.loc["RD (pp)"].p), f(rr.loc["RD (pp)"].tau2, 5)])
p_ = R["pooled_OR"]["REML_HKSJ"]
tbl("t2", "Table 2. Pooled gender contrast (women vs men) under alternative estimators, and heterogeneity.",
    ["Estimator", "Measure", "Estimate (95% CI)", "p", "τ²"], rows,
    f"Heterogeneity (log OR): Q = {p_['Q']:.2f}, df = {p_['df']}, p = {p_['p_Q']:.2f}; I² = {100 * p_['I2']:.0f}% (95% CI {100 * p_['I2_lo']:.0f}–{100 * p_['I2_hi']:.0f}%); "
    f"τ² = {p_['tau2']:.4f} (Q-profile CI {p_['tau2_lo']:.3f}–{p_['tau2_hi']:.3f}); 95% prediction interval {p_['pi_lo']:.3f}–{p_['pi_hi']:.3f}. RBG, Robins–Breslow–Greenland.")

# Table 3: bias analysis
pba = R["pba"]; ev = R["evalues"]["RR_based"]; sel = R["selection_model"]
rows = [
    ["Conventional analysis (random error only)", ci(pba["conventional"]["OR"], pba["conventional"]["lo"], pba["conventional"]["hi"]), "REML + Hartung–Knapp"],
    ["Rounding of published applicant shares: systematic error only", ci(pba["denominator_only"]["systematic"]["median"], pba["denominator_only"]["systematic"]["lo"], pba["denominator_only"]["systematic"]["hi"]), "5,000 draws, uniform within each call's interval"],
    ["Rounding: systematic + random error", ci(pba["denominator_only"]["total"]["median"], pba["denominator_only"]["total"]["lo"], pba["denominator_only"]["total"]["hi"]), f"P(OR < 1) = {pba['denominator_only']['total']['p_below_1']:.3f}"],
    ["Rounding + domain composition: systematic only", ci(pba["denominator_plus_domain"]["systematic"]["median"], pba["denominator_plus_domain"]["systematic"]["lo"], pba["denominator_plus_domain"]["systematic"]["hi"]), "within-domain shares LS 1.15, PE 0.75, SH 1.30 (±0.15) × overall share"],
    ["Rounding + domain composition: systematic + random", ci(pba["denominator_plus_domain"]["total"]["median"], pba["denominator_plus_domain"]["total"]["lo"], pba["denominator_plus_domain"]["total"]["hi"]), f"P(OR < 1) = {pba['denominator_plus_domain']['total']['p_below_1']:.3f}"],
    ["Confounding OR induced by domain composition alone (range over calls)", f"{min(pba['domain_confounding_OR_point'].values()):.3f}–{max(pba['domain_confounding_OR_point'].values()):.3f}", "point estimates per call"],
    ["E-value, pooled RR 1.074 (point / CI limit)", f"{ev['evalue_point']:.2f} / {ev['evalue_ci']:.2f}", "VanderWeele & Ding"],
    ["E-value to mask a true RR of 0.95 (point / CI limit)", f"{ev['evalue_true_0.95']:.2f} / {ev['evalue_ci_true_0.95']:.2f}", ""],
    ["E-value to mask a true RR of 0.90 (point / CI limit)", f"{ev['evalue_true_0.9']:.2f} / {ev['evalue_ci_true_0.9']:.2f}", ""],
    ["Self-selection: break-even quality shift δ of the female pool (SD)", f"{sel['breakeven_delta']['1.0']:.3f} / {sel['breakeven_delta']['0.7']:.3f} / {sel['breakeven_delta']['0.5']:.3f}", "evaluation reliability ρ = 1 / 0.7 / 0.5"],
]
t = {(r["rho"], r["delta"]): r for r in sel["table"]}
rows.append(["Self-selection: implied evaluation-stage OR if δ = 0.1 SD", f"{t[(1.0, 0.1)]['implied_eval_or']:.3f} / {t[(0.7, 0.1)]['implied_eval_or']:.3f} / {t[(0.5, 0.1)]['implied_eval_or']:.3f}", "ρ = 1 / 0.7 / 0.5"])
rows.append(["Self-selection: implied evaluation-stage OR if δ = 0.2 SD", f"{t[(1.0, 0.2)]['implied_eval_or']:.3f} / {t[(0.7, 0.2)]['implied_eval_or']:.3f} / {t[(0.5, 0.2)]['implied_eval_or']:.3f}", "ρ = 1 / 0.7 / 0.5"])
tbl("t3", "Table 3. Quantitative bias analysis of the pooled gender contrast.", ["Analysis", "Pooled OR (95% interval) or value", "Details"], rows,
    f"Applicant pool: {100 * sel['share_w']:.1f}% women; overall success rate {100 * sel['success_rate']:.2f}%. The self-selection model assumes latent merit N(δ, 1) for women and N(0, 1) for men, evaluation score = merit + noise with reliability ρ, and a common funding threshold.")

# Table 4: sensitivity + Bayesian
sens = R["sensitivity"]; B = R["bayes"]
rows = [
    ["Primary: 10 calls 2017–2026, REML + HK", ci(p_["est"], p_["lo"], p_["hi"]), "τ² = 0.0002, I² = 0%"],
    ["Non-binary grantees removed from the denominator", ci(sens["exclude_nonbinary_from_denominator"]["est"], sens["exclude_nonbinary_from_denominator"]["lo"], sens["exclude_nonbinary_from_denominator"]["hi"]), ""],
    ["2023 call: updated reserve-list counts (398 funded)", ci(sens["updated_2023_reserve_list_counts"]["est"], sens["updated_2023_reserve_list_counts"]["lo"], sens["updated_2023_reserve_list_counts"]["hi"]), ""],
    ["Extended 2013–2026 (2013, 2015, 2016 applicant share imputed; Monte Carlo)", ci(sens["extended_2015_2026_imputed_MC"]["OR_median"], sens["extended_2015_2026_imputed_MC"]["lo_total"], sens["extended_2015_2026_imputed_MC"]["hi_total"]),
     f"I² median {100 * sens['extended_2015_2026_imputed_MC']['I2_median']:.0f}% (97.5th pct {100 * sens['extended_2015_2026_imputed_MC']['I2_q975']:.0f}%)"],
    ["Extended 2013–2026, point imputation, REML + HK", ci(sens["extended_point_imputation"]["est"], sens["extended_point_imputation"]["lo"], sens["extended_point_imputation"]["hi"]),
     f"trend {sens['extended_trend']['slope']:+.4f}/yr, KH p = {sens['extended_trend']['p_KH']:.2f}, permutation p = {sens['extended_trend']['perm_p']:.2f}"],
    ["FP7-era comparator, StG 2007–2013 (rounded rates 8% vs 10%)", f"{sens['fp7_comparator_OR_range']['point']:.3f} (rounding range {sens['fp7_comparator_OR_range']['lo']:.2f}–{sens['fp7_comparator_OR_range']['hi']:.2f})", "historical"],
    ["StG 2007–2016 share-based (31% of applications, 27% of grants)", f"{sens['stg_2007_2016_share_based_OR']['value']:.3f}", "historical"],
]
for k, lab in [("weakly informative (mu~N(0,1), tau~HN(0.5))", "Bayesian HN, weakly informative priors"),
               ("sceptical (mu~N(0,0.2), tau~HN(0.5))", "Bayesian HN, sceptical prior on μ"),
               ("strong shrinkage (mu~N(0,1), tau~HN(0.1))", "Bayesian HN, strong shrinkage on τ")]:
    b = B["HN"][k]
    rows.append([lab, ci(b["OR_median"], b["OR_lo"], b["OR_hi"]), f"P(OR<1) = {b['P_OR_lt_1']:.3f}; P(ROPE) = {b['P_ROPE']:.2f}; BF10 = {b['BF10']:.2f}; predictive {b['pred_OR_lo']:.2f}–{b['pred_OR_hi']:.2f}"])
rows.append(["Bayesian HN, marginal maximum likelihood", ci(B["HN_MLE"]["OR"], B["HN_MLE"]["lo"], B["HN_MLE"]["hi"]), f"τ̂ = {B['HN_MLE']['tau']:.3f}"])
for x in B["power_prior"]:
    if x["a0"] in (0.1, 0.25, 0.5, 1.0):
        rows.append([f"Power prior on FP7-era aggregate, a₀ = {x['a0']}", ci(x["OR_median"], x["lo"], x["hi"]), f"P(OR<1) = {x['P_OR_lt_1']:.3f}"])
tbl("t4", "Table 4. Sensitivity analyses, historical comparators and Bayesian estimates of the pooled OR (women vs men).",
    ["Analysis", "OR (95% CI / CrI)", "Notes"], rows,
    "HN, exact-conditional hypergeometric-normal model; ROPE, region of practical equivalence 0.91–1.10; BF10, Savage–Dickey Bayes factor against OR = 1; HK, Hartung–Knapp.")

# Table 5: geography
g = R["geo"]
rows = [
    ["Share of grants hosted in widening Member States (10 calls)", f"{100 * g['widening_eu']['share']:.2f}% ({100 * g['widening_eu']['lo']:.2f}–{100 * g['widening_eu']['hi']:.2f})", f"I² = {100 * g['widening_eu']['I2']:.0f}%; trend KH p = {g['widening_eu']['trend_p']:.2f}, permutation p = {g['widening_eu']['trend_perm_p']:.2f}"],
    ["… including associated widening countries", f"{100 * g['widening_any']['share']:.2f}% ({100 * g['widening_any']['lo']:.2f}–{100 * g['widening_any']['hi']:.2f})", ""],
]
for s in g["sgr"]:
    rows.append([f"Standardised grant ratio if widening applicants are {100 * s['applicant_share']:.1f}% of the pool", ci(s["pooled"], s["lo"], s["hi"]), f"implied success-rate ratio {g['implied_success_ratio'][str(s['applicant_share'])]:.2f}"])
wid24 = 940 / (940 + 7271)
rows.append(["Widening share of ERC applications, all schemes, 2024 (ERC white paper: 940 vs 7,271)", f"{100 * wid24:.1f}%", "external anchor for the applicant-share scenarios"])
rows.append([f"Standardised grant ratio and implied success-rate ratio at that share", f"SGR {g['widening_eu']['share'] / wid24:.2f}", f"success-rate ratio {(g['widening_eu']['share'] / wid24) / ((1 - g['widening_eu']['share']) / (1 - wid24)):.2f}"])
for r in g["reallocation_to_parity"]:
    rows.append([f"Extra grants per call for parity at {100 * r['applicant_share']:.1f}% applicant share", f"{r['mean_extra_grants_per_call']:.0f}", f"{100 * r['share_of_all_grants']:.0f}% of all grants"])
c = g["association_contrasts"]
for cc in c:
    for k in cc["contrasts"]:
        rows.append([f"{cc['country']}: {k['period']} vs Horizon 2020 ({100 * cc['baseline_share']:.1f}%)", f"OR {ci(k['odds_ratio'], k['lo'], k['hi'], 2)}", f"share {100 * k['share']:.1f}%; KH p = {k['p_KH']:.3f}"])
rows.append(["UK: permutation p for the first contrast", f"{c[0]['perm_p_first_contrast']:.3f}", ""])
rows.append(["Concentration (mean over calls)", f"Gini {g['concentration']['gini_mean']:.2f}; top-5 {100 * g['concentration']['top5_mean']:.0f}%", f"Gini trend {g['gini_trend_per_year']:+.4f}/yr"])
rows.append(["Rank stability of host-country distribution", f"consecutive Spearman ρ {g['rank_stability']['consecutive_spearman_min']:.2f}–0.96 (median {g['rank_stability']['consecutive_spearman_median']:.2f})", f"2013 vs 2026: ρ = {g['rank_stability']['first_last_spearman']:.2f}"])
tbl("t5", "Table 5. Geographic distribution of StG grants: widening-country share, standardised grant ratios, association-status contrasts and concentration.",
    ["Quantity", "Estimate (95% CI)", "Notes"], rows,
    "Widening Member States: BG, HR, CY, CZ, EE, EL, HU, LV, LT, MT, PL, PT, RO, SK, SI. Applicant counts by country are not published, so the standardised grant ratio is reported under scenarios for the widening countries' share of applications.")

# Table 6: dynamics
d = R["dynamics"]; tx = d["tax_2026"]
rows = [
    ["Pooled success rate, 13 verified calls (logit REML + HK)", f"{100 * d['success_rate_pooled']:.1f}% ({100 * d['success_rate_ci'][0]:.1f}–{100 * d['success_rate_ci'][1]:.1f})", f"I² = {100 * d['success_rate_I2']:.0f}%; τ (logit) = {d['success_rate_tau_logit']:.2f}"],
    ["95% prediction interval for a new call", f"{100 * d['success_rate_pi'][0]:.1f}–{100 * d['success_rate_pi'][1]:.1f}%", ""],
    ["Pairwise cohort odds ratios (range)", f"{d['cohort_or_range'][0]:.2f}–{d['cohort_or_range'][1]:.2f}", f"2026 vs 2024: {d['cohort_or_2026_vs_2024']:.2f}; 2026 vs 2023: {d['cohort_or_2026_vs_2023']:.2f}"],
    ["2025→2026 change: Δlog applications / Δlog grants / Δlog success rate", f"{100 * d['last_change']['dlogN']:+.1f} / {100 * d['last_change']['dlogG']:+.1f} / {100 * d['last_change']['dlogSR']:+.1f} log-points", f"demand share of the change {100 * d['last_change']['demand_share']:.0f}%"],
    ["Demand elasticity to previous call's success rate (verified series)", f"{d['elasticity_verified']['elasticity']:+.2f} (HC1 SE {d['elasticity_verified']['se']:.2f})", f"permutation p = {d['elasticity_verified']['perm_p']:.2f}; n = {d['elasticity_verified']['n']}"],
    ["Demand elasticity (extended series 2007–2026)", f"{d['elasticity_full']['elasticity']:+.2f} (HC1 SE {d['elasticity_full']['se']:.2f})", f"permutation p = {d['elasticity_full']['perm_p']:.2f}; n = {d['elasticity_full']['n']}"],
    ["Application cost, 2026 call (20 / 34 / 50 working days per proposal)", f"{tx['20']['applicant_person_years']:.0f} / {tx['34']['applicant_person_years']:.0f} / {tx['50']['applicant_person_years']:.0f} person-years", f"{tx['20']['person_years_per_grant']:.1f} / {tx['34']['person_years_per_grant']:.1f} / {tx['50']['person_years_per_grant']:.1f} per grant; {100 * tx['20']['tax_ratio']:.0f}–{100 * tx['50']['tax_ratio']:.0f}% of funded PI-years"],
    ["Women's share of proposals, linear trend 2017–2026", f"{d['women_share_slope_pp_per_year']:+.2f} pp/yr (SE {d['women_share_slope_se']:.2f})", f"p = {d['women_share_trend_p']:.4f}; grantee share {d['grantee_share_slope_pp_per_year']:+.2f} pp/yr"],
    ["Projected year of a 50% applicant share", f"{d['parity_year_point']:.0f} ({d['parity_year_ci'][0]:.0f}–{d['parity_year_ci'][1]:.0f})", f"P(parity before 2035) = {d['parity_prob_before_2035']:.3f}"],
]
tbl("t6", "Table 6. Competition dynamics of the StG scheme.", ["Quantity", "Estimate", "Notes"], rows,
    "Verified series: calls 2013 and 2015–2026. Person-years assume 220 working days per year; funded PI-years = grants × 5.")

# Table 7: domains
dm = R["domains"]
rows = [["Within-call equality of domain success rates", f"0 of {dm['k_calls']} calls with χ² p < 0.05", f"max/min success-rate ratio: median {dm['median_max_min_ratio']:.2f}, max {dm['max_max_min_ratio']:.2f} ({dm['year_max']})"]]
for k, r in dm["rr"].items():
    rows.append([f"Pooled success-rate ratio {k}", ci(r["RR"], r["lo"], r["hi"]), f"p = {r['p']:.3f}; I² = {100 * r['I2']:.0f}%; trend {100 * r['trend_per_year']:+.1f}%/yr, permutation p = {r['trend_perm_p']:.3f}"])
for k, r in dm["app_share_trends"].items():
    rows.append([f"Share of proposals: {k}", f"{100 * r['first']:.1f}% ({r['first_year']}) → {100 * r['last']:.1f}% ({r['last_year']})", f"{r['slope_pp_per_year']:+.2f} pp/yr, permutation p = {r['perm_p']:.4f}"])
ns = dm["gender_domain_neutral_shares_2025"]
rows.append(["2025 call: applicant shares of women that would make every domain OR = 1", f"LS {100 * ns['LS']:.0f}%, PE {100 * ns['PE']:.0f}%, SH {100 * ns['SH']:.0f}%", f"weighted average {100 * dm['gender_domain_neutral_overall_2025']:.1f}% vs published 40%"])
tbl("t7", "Table 7. Domain structure: neutrality of success rates, demand shift and gender-by-domain identification.", ["Quantity", "Estimate", "Notes"], rows,
    "LS, Life Sciences; PE, Physical Sciences and Engineering; SH, Social Sciences and Humanities. Thirteen calls (2013, 2015–2026).")

# Table 8: policy
P = R["policy"]; pr = P["propagated"]; rel = P["reliability_meta"]
mech = ["single-stage panel", "two-stage (ERC-like)", "threshold + lottery", "merit top-half + lottery", "pure lottery"]
rows = []
for m in mech:
    a = P["at_rho_0.5"][m]; b = pr[m]
    rows.append([m, f"{a['mean_merit']:.2f}", f"{100 * a['share_topK']:.0f}%", f"{100 * a['share_top1']:.0f}%", f"{a['subgroup_OR']:.2f}", f"{a['workload']:.0f}",
                 f"{b['mean_merit_funded']['median']:.2f} ({b['mean_merit_funded']['lo']:.2f}–{b['mean_merit_funded']['hi']:.2f})",
                 f"{100 * b['share_true_topK_funded']['median']:.0f}% ({100 * b['share_true_topK_funded']['lo']:.0f}–{100 * b['share_true_topK_funded']['hi']:.0f})",
                 f"{b['subgroup_OR']['median']:.2f} ({b['subgroup_OR']['lo']:.2f}–{b['subgroup_OR']['hi']:.2f})"])
tbl("t8", "Table 8. Selection-mechanism simulation: outcomes at a fixed stage reliability of 0.5 and under the meta-analytic reliability distribution.",
    ["Mechanism", "Mean merit of funded set (SD), ρ = 0.5", "True top-K funded, ρ = 0.5", "True top-1% funded, ρ = 0.5", "OR for −0.2 SD subgroup, ρ = 0.5", "Full reviews (of 3,500)",
     "Mean merit, ρ from meta-analysis (95% interval)", "True top-K funded, ρ from meta-analysis", "Subgroup OR, ρ from meta-analysis"], rows,
    f"Simulated competition: 3,500 applicants, success rate {100 * P['inputs']['success_rate']:.1f}%, subgroup share {100 * P['inputs']['share_w']:.0f}% with latent-merit shift −0.2 SD; 200 replications per reliability value. "
    f"Meta-analytic reliability: pooled single-rater ICC {rel['pooled_single_rater']:.3f} ({rel['lo']:.3f}–{rel['hi']:.3f}), five-rater panel {pr['rho_panel']['median']:.2f} ({pr['rho_panel']['lo']:.2f}–{pr['rho_panel']['hi']:.2f}) including an assumed between-funder SD of {pr['extra_sd']:.2f}. "
    f"Two-stage gain in mean merit {pr['two_stage_gain_merit_SD']['median']:.2f} SD ({pr['two_stage_gain_merit_SD']['lo']:.2f}–{pr['two_stage_gain_merit_SD']['hi']:.2f}); threshold-lottery cost {pr['threshold_lottery_cost_merit_SD']['median']:.2f} SD ({pr['threshold_lottery_cost_merit_SD']['lo']:.2f}–{pr['threshold_lottery_cost_merit_SD']['hi']:.2f}); hybrid cost {pr['hybrid_lottery_cost_merit_SD']['median']:.2f} SD ({pr['hybrid_lottery_cost_merit_SD']['lo']:.2f}–{pr['hybrid_lottery_cost_merit_SD']['hi']:.2f}).")

# ---------------- supplementary tables (formatted CSV dumps) ----------------
def dump(key, title, path, note="", rename=None, keep=None, dec=3, index=False):
    df = pd.read_csv(path, index_col=0 if index else None)
    if index:
        df = df.reset_index().rename(columns={"index": "call"})
    if keep:
        df = df[keep]
    if rename:
        df = df.rename(columns=rename)
    rows = []
    for _, r in df.iterrows():
        row = []
        for c in df.columns:
            v = r[c]
            if isinstance(v, (float, np.floating)):
                if np.isnan(v):
                    row.append("–")
                elif float(v).is_integer() and c.lower() in ("year", "call", "k", "df", "n", "through_call", "omitted_call", "from_year", "to_year"):
                    row.append(str(int(v)))
                elif abs(v) >= 1000 and float(v).is_integer():
                    row.append(f"{int(v):,}")
                else:
                    row.append(f"{v:.{dec}f}")
            elif isinstance(v, (int, np.integer)):
                row.append(f"{int(v):,}" if abs(int(v)) >= 10000 else str(int(v)))
            else:
                row.append(str(v))
        rows.append(row)
    tbl(key, title, list(df.columns), rows, note, where="supp")


dump("s1", "Table S1. Provenance of every input (per call).", f"{T}/table0_provenance.csv",
     keep=["call", "evaluated_proposals", "LS", "PE", "SH", "selected", "sel_LS", "sel_PE", "sel_SH", "women_share_apps_text", "share_lo", "share_hi", "grantees_F", "grantees_M", "grantees_NB", "notes"], dec=1)
dump("s1b", "Table S1b. Source URLs per call.", f"{T}/table0_provenance.csv", keep=["call", "source_statistics", "source_share"])
dump("s2", "Table S2. Analytic 2×2 tables and effect sizes.", f"{T}/table1b_effect_sizes.csv",
     keep=["year", "a", "b", "c", "d", "n_w", "n_m", "n", "share_w", "p_w", "p_m", "logOR", "var_logOR", "OR", "OR_lo", "OR_hi", "RR", "RD_pp", "RD_lo_pp", "RD_hi_pp"], dec=4,
     note="a, women funded; b, women not funded; c, men funded; d, men not funded.")
dump("s3", "Table S3. Pooled log-OR estimates by estimator (full output).", f"{T}/table2_pooled_OR.csv",
     keep=["model", "est", "lo", "hi", "se_log", "z", "p", "tau2", "tau2_lo", "tau2_hi", "Q", "df", "p_Q", "I2", "I2_lo", "I2_hi", "pi_lo", "pi_hi", "hksj_q"], dec=4)
dump("s3b", "Table S3b. Pooled RR and RD.", f"{T}/table2b_pooled_RR_RD.csv", keep=["measure", "est", "lo", "hi", "p", "tau2", "I2", "pi_lo", "pi_hi"], dec=4)
dump("s4", "Table S4. Mixed-effects meta-regression (REML, Knapp–Hartung) on call year and programme era.", f"{T}/table3_metaregression.csv", dec=4)
dump("s5", "Table S5. Leave-one-out influence diagnostics.", f"{T}/table4_influence.csv", keep=["omitted_call", "OR", "OR_lo", "OR_hi", "tau2", "I2", "cook", "rstudent", "Q_contribution", "baujat_influence"], dec=4)
dump("s5b", "Table S5b. Cumulative meta-analysis by call year.", f"{T}/table4b_cumulative.csv", keep=["through_call", "k", "OR", "OR_lo", "OR_hi", "tau2"], dec=4)
dump("s6", "Table S6. Bayesian analyses under alternative priors (normal-normal and exact-conditional models).", f"{T}/table5_bayes.csv", dec=3)
dump("s6b", "Table S6b. Historical power-prior sensitivity.", f"{T}/table5b_power_prior.csv", dec=3)
dump("s7", "Table S7. Probabilistic bias analysis.", f"{T}/table6_pba.csv", dec=4)
sel_df = pd.read_csv(f"{T}/table7_selection_sensitivity.csv")
sel_df = sel_df[np.isclose((sel_df.delta * 100) % 5, 0)]
sel_df.to_csv("/tmp/sel_sub.csv", index=False)
dump("s8", "Table S8. Self-selection sensitivity model (δ in steps of 0.05 SD).", "/tmp/sel_sub.csv", dec=3)
rows = []
for k, vv in sens.items():
    if "est" in vv:
        rows.append([k, f(vv["est"]), f(vv["lo"]), f(vv["hi"]), f"p = {vv['p']:.4f}; tau2 = {vv['tau2']:.5f}; I2 = {100 * vv['I2']:.1f}%"])
    elif "OR_median" in vv:
        rows.append([k, f(vv["OR_median"]), f(vv["lo_total"]), f(vv["hi_total"]), f"tau2 median {vv['tau2_median']:.4f}; I2 median {100 * vv['I2_median']:.1f}% (97.5th pct {100 * vv['I2_q975']:.1f}%)"])
    elif "slope" in vv:
        rows.append([k, f"{vv['slope']:+.4f}/yr", "", "", f"SE {vv['se']:.4f}; KH p = {vv['p_KH']:.3f}; permutation p = {vv['perm_p']:.3f}; OR ratio per decade {vv['or_ratio_per_decade']:.3f}"])
    elif "point" in vv:
        rows.append([k, f(vv["point"]), f(vv["lo"]), f(vv["hi"]), "rounding range of the published rates"])
    else:
        rows.append([k, f(vv["value"]), "", "", ""])
tbl("s9", "Table S9. Sensitivity analyses (pooled OR, women vs men).", ["Analysis", "Estimate", "Lower", "Upper", "Notes"], rows, where="supp", widths=[26, 8, 8, 8, 40])
dump("s10", "Table S10. Counterfactual grant gap (women funded minus expected at men's success rate).", f"{T}/table9_counterfactual_gap.csv", dec=1)
dump("s11", "Table S11. Widening-country share of grants and concentration indices per call.", f"{T}/table10_geo_widening.csv", dec=3)
ctab = pd.read_csv(f"{T}/table14_country_shares.csv")
piv = ctab.pivot(index="year", columns="country", values="share").reset_index()
piv.to_csv("/tmp/country_piv.csv", index=False)
dump("s11b", "Table S11b. Share of grants hosted by selected countries, per call.", "/tmp/country_piv.csv", dec=3)
dump("s11c", "Table S11c. Grants that would have to move to widening hosts for parity with assumed applicant shares.", f"{T}/table14b_reallocation_to_parity.csv", dec=2)
dump("s12", "Table S12. Competition series 2007–2026.", f"{T}/table12_competition_series.csv", keep=["year", "apps", "grants", "budget_meur", "status", "sr", "sr_lo", "sr_hi"], dec=3)
dump("s12b", "Table S12b. Decomposition of consecutive changes in the success rate.", f"{T}/table12b_success_rate_decomposition.csv", dec=3)
dump("s12c", "Table S12c. Application-cost accounting per call.", f"{T}/table12c_application_tax.csv", dec=2)
dump("s12d", "Table S12d. Women's share of applicants and grantees and the representation gap.", f"{T}/table12d_women_share_gap.csv", dec=3)
dump("s12e", "Table S12e. Pairwise cohort odds ratios (row call vs column call).", f"{T}/table12e_cohort_odds_ratios.csv", dec=2, index=True)
dump("s13", "Table S13. Within-call tests of domain neutrality.", f"{T}/table13_domain_neutrality.csv", dec=3)
dump("s13b", "Table S13b. 2025 call: domain-specific gender ORs under scenarios for the within-domain applicant share.", f"{T}/table13b_gender_by_domain_2025_scenarios.csv", dec=3)
dump("s14", "Table S14. Selection-mechanism simulation, full grid.", f"{T}/table11_policy_simulation.csv", dec=3)
rows = [["Single-rater ICC, pooled (REML/HKSJ)", f(rel["pooled_single_rater"]), f(rel["lo"]), f(rel["hi"]), f"k = {rel['k']}; tau2 = {rel['tau2']:.5f}"],
        ["Panel of 3 raters (Spearman–Brown)", f(rel["panel_3_raters"]), f(rel["panel_3_raters_lo"]), f(rel["panel_3_raters_hi"]), ""],
        ["Panel of 5 raters (Spearman–Brown)", f(rel["panel_5_raters"]), f(rel["panel_5_raters_lo"]), f(rel["panel_5_raters_hi"]), ""],
        ["Two independent 5-rater stages averaged", f(rel["two_stage_of_5_rater_panels"]), "", "", ""],
        ["Propagated five-rater reliability (incl. between-funder SD 0.05)", f(pr["rho_panel"]["median"], 2), f(pr["rho_panel"]["lo"], 2), f(pr["rho_panel"]["hi"], 2), "median and 95% interval of draws"]]
for m in mech:
    for col, lab in [("mean_merit_funded", "mean merit of funded set (SD)"), ("share_true_topK_funded", "share of true top-K funded"), ("subgroup_OR", "subgroup OR (pool shifted −0.2 SD)")]:
        b = pr[m][col]
        rows.append([f"{m}: {lab}", f(b["median"]), f(b["lo"]), f(b["hi"]), ""])
for k, lab in [("two_stage_gain_merit_SD", "Gain from ERC second stage (SD of merit)"), ("threshold_lottery_cost_merit_SD", "Cost of threshold + lottery (SD of merit)"),
               ("hybrid_lottery_cost_merit_SD", "Cost of merit top-half + lottery (SD of merit)"), ("threshold_lottery_topK_loss", "Loss of true top-K precision, threshold + lottery"),
               ("threshold_lottery_disparity_gain_OR", "Gain in subgroup OR, threshold + lottery")]:
    rows.append([lab, f(pr[k]["median"]), f(pr[k]["lo"]), f(pr[k]["hi"]), ""])
tbl("s14b", "Table S14b. Reliability meta-analysis and its propagation through the selection simulator.", ["Quantity", "Estimate", "Lower", "Upper", "Notes"], rows, where="supp", widths=[40, 8, 8, 8, 26])
dump("s15", "Table S15. Evidence map of quantitative studies used for context.", "data/evidence_map.csv", keep=["topic", "study", "design", "setting", "key_estimate_as_reported", "verification"])
dump("s15b", "Table S15b. Evidence map: sources.", "data/evidence_map.csv", keep=["study", "url"])

json.dump(out, open("outputs/paper_tables.json", "w"), indent=1)
print({k: len(v) for k, v in out.items()})
