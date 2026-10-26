# High-impact meta-analytic questions on ERC Starting Grants and research-funding design

This agenda complements the call-level meta-analysis in `REPORT.md`. Each item states the
policy question, the estimand a meta-analysis should target, the data that exist, the
identification strategy, the dominant biases, and what pooling adds. Items 1–3 are already
partly implemented in this repository (`erc_meta/policy.py`, `erc_meta/bias.py`,
`erc_meta/geo.py`); the rest are designed to be feasible with public or ERC-held data.

Quantitative anchors from the literature are listed in `data/evidence_map.csv` with a
verification flag; two entries there are marked "not re-verified" and should be checked
before citation.

---

## A. Outcomes of StG grants (what does the money buy?)

### 1. Does winning a StG cause more or better science? (local causal effect)
* **Estimand.** Effect of award receipt on 5–10-year output (papers, field-normalised
  citations, top-5 % "hits", follow-on funding, retention in research) for applicants at the
  funding margin.
* **Evidence.** The ERC's own ranking rule permits a sharp multi-cutoff regression
  discontinuity. Ghirelli et al. (2023) apply it to all 2007–2013 applicants and find no
  significant local effect on productivity or quality (with a possible exception in physics
  StG). Wang, Jones & Wang (2019) show for NIH that near-misses have >10 % higher attrition
  yet, conditional on staying, a +6.1 pp higher probability of a top-5 % paper.
* **Meta-analytic design.** Pool RDD estimates across panels × calls × outcome windows
  (multilevel random effects with panel as cluster); meta-regress on domain, grant size,
  host-country research intensity and career stage. Test whether the local null masks
  heterogeneity (e.g. women benefit more than men in the MRC propensity-score study, and
  grants mainly raise PI-led output in the Czech RDD study).
* **Biases.** Local nature of RDD (external validity to the top of the ranking); attrition
  and selection into re-application (collider bias); bibliometric outcome misclassification;
  manipulation of the running variable is implausible but should be tested (density tests).
* **Why high impact.** A precise near-zero marginal effect would imply that shifting the
  cutoff (funding more people with smaller grants) is cheap in lost impact; a strongly
  heterogeneous effect would motivate targeting.

### 2. Portfolio outcomes: breakthroughs versus incremental advances
* **Estimand.** Share of completed StG projects judged "breakthrough" or "major advance" in
  the ERC ex-post qualitative evaluations, and its relation to grant size, domain,
  interdisciplinarity, and applicant characteristics.
* **Design.** Meta-analysis of the ERC's annual ex-post evaluation reports (panel-scored
  project outcomes) treated as repeated cross-sections; hierarchical ordinal model; compare
  with bibliometric hit rates to calibrate the qualitative scale.
* **Biases.** Evaluator leniency drift over time; selection of evaluated projects; the
  ex-post panels are not blind to grantee identity.

### 3. The cost of an extra "hit": funding concentration versus dispersal
* **Estimand.** Elasticity α of output with respect to grant size (output ∝ size^α). The
  concentration literature repeatedly finds α < 1 (diminishing returns).
* **Design.** Meta-analysis of α across funders and fields (log–log regressions of output
  on funding, RDD/IV estimates where available), then plug into the budget-split curve in
  `policy.py` to compute the ERC-specific trade-off between fewer larger and more smaller
  StGs.
* **Biases.** Reverse causation (productive labs attract money), field size effects,
  truncation of high-output tails.

---

## B. Selection: how are StGs chosen and how reliable is that choice?

### 4. Reliability of the two-step ERC evaluation
* **Estimand.** Intraclass correlation of stage-1 (synopsis) and stage-2 (full proposal +
  interview) scores; test–retest reliability of the final ranking; the incremental
  reliability bought by the interview.
* **Evidence.** Single-rater ICCs in grant review cluster around 0.2–0.4 (NSF 0.17–0.37;
  FWF 0.26; a Norwegian funder 0.29); 6–15 independent raters would be needed to reach 0.75.
* **Design.** Reliability-generalisation meta-analysis (as done for journals by Bornmann et
  al. 2010) restricted to grant panels, with moderators (domain, panel size, use of
  interviews, remote vs in-person). The simulator in `policy.py` shows what each 0.1 of ρ is
  worth in portfolio merit and in selection precision.
* **Why high impact.** Reliability is the single parameter that determines whether partial
  lotteries lose anything (see 5) and how much disparity a merit ranking amplifies (see 8).

### 5. Lotteries versus panels
* **Estimand.** Difference in expected portfolio quality, precision, disparity, and cost
  between merit ranking and threshold-plus-lottery designs (SNSF, Volkswagen Foundation,
  HRC New Zealand, BC Health).
* **Design.** (i) Meta-analysis of the randomised lottery trials now running at several
  funders (outcomes of lottery-funded vs panel-funded projects); (ii) the decision-analytic
  simulation here, which at ρ = 0.5 (panel-level reliability) estimates that a
  threshold-plus-lottery costs about 0.26 SD of mean funded merit and 13 percentage points
  of "true top-K" precision, while a merit-top-half-plus-lottery design costs only ~0.10 SD
  and 5 pp, and reduces the disparity amplification of a merit ranking.
* **Biases.** Lottery trials are young (short follow-up), differ in eligibility thresholds,
  and are often evaluated by the funders that run them.

### 6. Does the interview stage help or hurt?
* **Estimand.** Change in the composition of funded PIs (gender, nationality, native
  language, institution prestige) attributable to the interview, and its contribution to
  reliability.
* **Design.** Difference-in-discontinuities: compare the stage-1 ranking with the final
  ranking for the same applicants across calls; pool across panels. Requires ERC-held
  score data (already used by Ghirelli et al.).

### 7. Applicant-pool dynamics: success-rate elasticity and demand inflation
* **Estimand.** Response of applications (and of the women's share) to the previous
  call's success rate and budget; the 2026 call (4,807 applications, 8.8 % success) is a
  natural experiment for demand shocks.
* **Evidence (this repository).** Success rates pool to 12.2 % with a prediction interval of
  8.1–17.8 % (cohort odds ratios 0.54–1.85); demand elasticity to the previous success rate
  is ≈ +0.15 and not distinguishable from zero; the 2026 application cost is 1.0–2.6
  person-years per grant.
* **Design.** Panel meta-regression of call-level application counts on lagged success
  rates across ERC schemes and national funders; distributed-lag models; a meta-analysis of
  proposal-preparation time studies to price the application tax.

---

## C. Equity and geography

### 8. Gender: from "equal success rates" to "equal treatment"
* **Estimand.** Evaluation-stage bias net of differential self-selection.
* **Evidence.** This repository: pooled StG OR 1.085 (95 % CI 1.005–1.170) for women vs men
  over 2017–2026, I² = 0 %. Meta-analyses across funders find award rates approximately
  equal (Schmaling & Gallo 2023: +1 % for men, CI −1 to +3 %) but higher reapplication
  success and larger amounts for men; older syntheses found men favoured by ~7 % in odds.
* **Design.** Two-stage meta-analysis: (i) call-level ORs as here; (ii) applicant-level
  models with pre-application productivity to estimate the self-selection differential δ,
  whose break-even value is only ≈0.04–0.06 SD in our sensitivity model. A meta-analysis of
  δ across funders (from studies with pre-application bibliometrics) is the missing piece.
* **Biases.** Self-selection (collider), domain composition, rounding of published
  denominators, non-binary reporting, reserve-list versions of the counts.

### 9. Geography: are widening-country applicants disadvantaged at evaluation or before it?
* **Estimand.** Success-rate ratio for widening vs non-widening host institutions,
  decomposed into applicant-pool composition and evaluation effects.
* **Evidence.** Widening countries host 4.2 % (95 % CI 3.7–4.8 %) of StG grants across ten
  calls with no trend; the ERC white paper reports success rates of 1–7 % vs ~11 %.
* **Design.** Meta-analysis of country-level standardised grant ratios once the ERC
  publishes applicant counts by country per call; mediation analysis through host-institution
  characteristics and applicant mobility; policy evaluation of the ERC's widening measures
  (mentoring, visiting fellowships) as staggered difference-in-differences.

### 9b. Association status as a natural experiment
* **Evidence (this repository).** UK share of hosted StGs 17.3 % → 11.6 % (non-association)
  → 11.3 % (re-association), OR ≈ 0.6 with permutation p = 0.007; Germany 16 % → 21 %;
  Switzerland unaffected except for the mechanical zero of 2024.
* **Design.** Applicant-level difference-in-differences with UK/CH-based applicants as
  treated groups and other associated countries as controls, outcomes: applications,
  stage-1 pass, funding, host mobility; requires ERC applicant data.

### 10. Mobility and brain drain
* **Estimand.** Effect of a StG on the probability that the grantee moves to (or stays in)
  a widening country, and the net flows of grants across countries.
* **Design.** Pool host-country and nationality distributions (published per call) in a
  gravity-type model; the ERC's "nationals abroad" statistics are the numerators.

---

## D. Funding-system comparisons

### 11. Public versus private/philanthropic funding
* **Estimand.** Difference in high-impact output and novelty between people-based,
  long-horizon philanthropic schemes (HHMI, Wellcome investigator awards, Novo Nordisk,
  Simons) and project-based public grants (NIH R01, national councils), conditional on
  applicant quality.
* **Evidence.** Azoulay, Graff Zivin & Manso (2011): HHMI investigators produce far more
  high-impact papers than matched NIH scientists (secondary summaries cite roughly +39 %
  publications and about double the top-1 % papers), and more flops, consistent with
  tolerance of early failure. The ERC itself is a public scheme designed on the HHMI
  template (5-year, PI-centred, few deliverables), so the relevant comparison is
  "ERC-like public" vs "project-based public" vs "philanthropic".
* **Design.** Meta-analysis of matched-cohort and RDD estimates across funder pairs;
  meta-regress on scheme features (duration, renewal tolerance, PI vs project focus, size)
  rather than on the public/private label, which is confounded with those features.
* **Biases.** Selection on unobservables into elite programmes; outcome definitions that
  favour citation-dense fields; publication bias in favour of striking contrasts.

### 12. Grant size and duration
* **Estimand.** Marginal impact per euro and per year of funding; whether the StG's
  €1.5 M/5-year template is on the flat part of the returns curve.
* **Design.** Meta-regression of α (item 3) on scheme duration; within-ERC variation from
  budget top-ups (e.g. the +€1 M start-up allowance) as a natural experiment.

### 13. Success-rate policy: is a 10–13 % success rate too low?
* **Estimand.** Welfare loss from unfunded fundable proposals (preparation cost × number
  of fundable-but-unfunded) versus the quality gain of a tighter cutoff.
* **Design.** Combine the reliability estimates (4), the local causal effect (1) and the
  cost of proposal preparation in a decision model; meta-analyse proposal-preparation cost
  studies (person-weeks per proposal) to price the "application tax".

### 14. Mandates and conditions (open access, data sharing, mobility rules)
* **Estimand.** Effects of grant conditions on compliance and on downstream reuse.
* **Design.** Staggered adoption across funders → difference-in-differences meta-analysis.

---

## What a "meta-analysis" means here

Two units of analysis are available and should be kept distinct:

1. **Calls as studies** (this repository): each competition contributes a 2×2 table, a
   country distribution or a selection ranking. Pooling is defensible because calls are
   independent draws of the same process; heterogeneity between calls is itself informative.
2. **Published estimates as studies**: quasi-experimental effect sizes across funders. Here
   the classical apparatus (random effects, meta-regression on design features,
   small-study effects, risk-of-bias grading of identification strategies) applies, and the
   funder-design features—not the public/private label—are the moderators of interest.

The most policy-relevant single parameter that emerges from both strands is the
**reliability of the evaluation stage**: it governs the price of lotteries, the size of
disparity amplification, and the interpretability of "equal success rates" as evidence of
equal treatment.
