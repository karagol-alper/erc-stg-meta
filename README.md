# ERC Starting Grants — call-level meta-analysis (gender, geography, bias analysis, selection policy)

```
erc_stg_meta/
├── run_all.py                 # one-command pipeline (~2 min): tables, figures, results.json, key_results.md
├── prepare_tables.py          # formats every table for the paper/supplement (outputs/paper_tables.json)
├── make_paper.js              # builds the research paper and the supplementary data .docx (docx-js)
├── REPORT.md                  # full write-up with results and interpretation
├── POLICY_AGENDA.md           # 14 high-impact meta-analytic policy questions with designs
├── README.md
├── data/
│   └── evidence_map.csv       # literature anchors (ERC RDD, near-miss, HHMI vs NIH, gender meta-analyses, review reliability)
├── erc_meta/
│   ├── data.py                # per-call ERC data with provenance; 2x2 construction; host-country counts; widening lists
│   ├── core.py                # effect sizes; IV/MH/Peto; DL/PM/REML; Q-profile & I2 CIs; HKSJ; prediction intervals;
│   │                          #   meta-regression (REML, Knapp-Hartung, permutation); LOO/cumulative/Baujat;
│   │                          #   Egger/Peters/Begg; trim-and-fill; PET-PEESE; limit meta-analysis
│   ├── bayes.py               # grid posteriors: normal-normal and exact-conditional hypergeometric-normal models;
│   │                          #   prior sensitivity; Savage-Dickey BF; posterior predictive; power priors
│   ├── bias.py                # E-values; probabilistic bias analysis (denominator rounding, domain composition);
│   │                          #   latent-quality self-selection sensitivity model
│   ├── geo.py                 # widening-country share (logit RE), SGR scenarios, concentration indices,
│   │                          #   country shares over time, association-status contrasts, rank stability, reallocation
│   ├── policy.py              # selection-mechanism simulator (panel / two-stage / lotteries), dispersal curve,
│   │                          #   reliability meta-analysis (ICC pooling, Spearman-Brown) and uncertainty propagation
│   ├── dynamics.py            # success-rate meta-analysis & cohort luck, supply/demand decomposition, demand elasticity,
│   │                          #   application-cost accounting, women's applicant-share trend and parity projection
│   ├── domains.py             # domain neutrality tests, SH:PE / LS:PE rate ratios, domain-share trends, gender x domain bounds
│   └── plots.py               # all figures
└── outputs/
    ├── figures/fig01..fig15   # forest, success rates, cumulative/LOO, funnel/Baujat, meta-regression, Bayesian,
    │                          #   bias analysis, selection sensitivity, geography, extended series, policy simulation,
    │                          #   competition dynamics, domains, country shares/association, reliability-to-policy
    ├── tables/table0..table15 # provenance, 2x2, effect sizes, pooled, meta-regression, influence, Bayesian,
    │                          #   PBA, selection, sensitivity, counterfactual gap, geography, policy simulation,
    │                          #   competition series/decomposition/tax/women's share/cohort ORs, domain neutrality,
    │                          #   gender x domain scenarios, country shares, reallocation, reliability propagation
    ├── results.json           # every estimate, machine-readable
    └── key_results.md         # auto-generated summary
```

## Reproduce

```bash
pip install numpy scipy pandas matplotlib      # Python >= 3.10
python run_all.py        # about 2 minutes
python prepare_tables.py # paper tables
node make_paper.js       # paper + supplement (.docx)
```

## Extend

* Add a call: append a `Call(...)` record in `erc_meta/data.py` (counts from the ERC statistics PDF,
  women's share from the "facts and figures" release, encoded as an interval) — every table and figure updates.
* Add host-country counts for 2022/2023 (if the ERC publishes labelled charts) in `HOST_COUNTRY`.
* When the ERC publishes applicant counts by country, `geo.sgr_scenarios` can be replaced by observed denominators.
* Change the policy simulator's inputs (`success_rate`, `share_w`, `delta`, `p1`, `pool_mult`) in `run_all.py`.

## Design notes

* Each call is a study; heterogeneity between calls is estimated, not assumed away.
* All methods are implemented from primary formulas (no meta-analysis package), so reviewers can audit them.
* The Bayesian analysis uses deterministic numerical integration rather than MCMC: bit-for-bit reproducible, no convergence diagnostics.
* The bias analysis distinguishes measurement error (rounding), confounding (domain), unmeasured confounding (E-values) and selection (latent-quality model); the last is the decisive one for interpreting "equal success rates".
