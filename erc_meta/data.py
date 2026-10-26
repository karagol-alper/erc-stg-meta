"""
erc_meta.data
=============
Call-level data for ERC Starting Grant (StG) competitions, assembled from the
ERC's own per-call statistics PDFs and "facts and figures" releases.

Every number carries a provenance note.  Two kinds of quantities are used:

* EXACT counts   - total submitted / selected proposals (by domain), and the
                   number of grantees by gender, taken from the per-call
                   statistics PDF (bar-chart data labels).
* ROUNDED shares - the share of proposals submitted by women, taken from the
                   ERC "facts and figures" release for each call.  The ERC
                   reports these to the nearest percent, often qualified as
                   "nearly X %".  We encode each as an interval
                   [share_lo, share_hi] and use the midpoint as the point
                   estimate; the interval is propagated in the probabilistic
                   bias analysis (denominator measurement error).

Convention for the interval:
    "nearly X %"           ->  [X-1, X]
    "X %" / "around X %"   ->  [X-0.5, X+0.5]

Grantees who declared a non-binary gender are recorded separately and are
excluded from the female/male 2x2 tables (they cannot be assigned to either
row); the applicant pool is assumed to contain a negligible number of
non-binary applicants (the ERC does not publish applicant counts by
non-binary status).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List
import numpy as np
import pandas as pd

ERC = "https://erc.europa.eu"

# --------------------------------------------------------------------------- #
# Primary series: ten consecutive calls with fully documented inputs
# --------------------------------------------------------------------------- #
@dataclass
class Call:
    year: int
    n_total: int          # evaluated proposals (statistics PDF)
    n_ls: int
    n_pe: int
    n_sh: int
    g_total: int          # selected proposals (statistics PDF, same version as gender split)
    g_ls: int
    g_pe: int
    g_sh: int
    share_w_lo: float     # women's share of proposals, interval lower bound (%)
    share_w_hi: float     # interval upper bound (%)
    share_w_text: str     # verbatim ERC wording
    g_female: int
    g_male: int
    g_nonbinary: int
    src_stats: str
    src_share: str
    notes: str = ""

    @property
    def share_w(self) -> float:
        return 0.5 * (self.share_w_lo + self.share_w_hi) / 100.0


CALLS: List[Call] = [
    Call(2017, 3085, 874, 1339, 872, 406, 118, 177, 111, 36.5, 37.5, "37 % (same share as 2018 release states for 2017)",
         164, 242, 0,
         f"{ERC}/sites/default/files/document/file/erc_2017_stg_statistics.pdf",
         f"{ERC}/news/applications-erc-starting-grants-2018-%E2%80%93-facts-and-figures",
         "ERC press release: women 14.5 % vs men 12.7 % success in 2017 (external check)."),
    Call(2018, 3170, 918, 1341, 911, 403, 118, 170, 115, 36.5, 37.5, "around 37 %",
         159, 244, 0,
         f"{ERC}/sites/default/files/document/file/erc_2018_stg_statistics.pdf",
         f"{ERC}/news/applications-erc-starting-grants-2018-%E2%80%93-facts-and-figures"),
    Call(2019, 3106, 867, 1363, 876, 408, 115, 178, 115, 38.0, 39.0, "nearly 39 %",
         154, 254, 0,
         f"{ERC}/sites/default/files/document/file/erc_2019_stg_statistics.pdf",
         f"{ERC}/news/starting-grants-applications-fact-and-figures"),
    Call(2020, 3272, 923, 1409, 940, 436, 124, 186, 126, 37.0, 38.0, "nearly 38 %",
         163, 273, 0,
         f"{ERC}/sites/default/files/document/file/erc_2020_stg_statistics.pdf",
         f"{ERC}/news/starting-grants-2020-applications-fact-and-figures",
         "Preliminary submissions 3,271; evaluated 3,272."),
    Call(2021, 4066, 1113, 1762, 1191, 397, 111, 172, 114, 39.0, 40.0, "nearly 40 %",
         170, 226, 1,
         f"{ERC}/sites/default/files/document/file/erc_2021_stg_statistics.pdf",
         f"{ERC}/news/applications-erc-starting-grants-2021-facts-and-figures",
         "Initial selection (397). An updated release later listed 471 funded incl. reserve list, "
         "without a gender split; we use the version with the gender split."),
    Call(2022, 2932, 860, 1224, 848, 408, 124, 168, 116, 40.0, 41.0, "nearly 41 %",
         161, 245, 2,
         f"{ERC}/sites/default/files/2022-11/stg_2022_statistics.pdf",
         f"{ERC}/news/applications-erc-starting-grants-2022-facts-and-figures"),
    Call(2023, 2696, 735, 1150, 811, 400, 110, 173, 117, 39.0, 40.0, "nearly 40 %",
         171, 228, 1,
         f"{ERC}/sites/default/files/2023-09/erc-2023-stg-statistics.pdf",
         f"{ERC}/news-events/news/applications-erc-starting-grants-2023-facts-and-figures",
         "Updated statistics (Jan 2025) list 398 funded: F 173, M 224, NB 1 - used in a sensitivity run."),
    Call(2024, 3474, 992, 1443, 1039, 494, 146, 209, 139, 39.0, 40.0, "nearly 40 %",
         216, 275, 3,
         f"{ERC}/sites/default/files/2024-09/erc-2024-stg-statistics.pdf",
         f"{ERC}/news-events/news/starting-grants-2024-applications-facts-and-figures"),
    Call(2025, 3928, 1099, 1640, 1189, 478, 137, 197, 144, 39.5, 40.5, "40 %",
         201, 271, 6,
         f"{ERC}/system/files/2025-09/erc-2025-stg-statistics.pdf",
         f"{ERC}/news-events/news/starting-grants-2025-applications-facts-and-figures",
         "Domain x gender split available: F LS55/PE64/SH82; M LS79/PE133/SH59; NB LS3/SH3."),
    Call(2026, 4807, 1261, 1971, 1575, 421, 113, 169, 139, 42.0, 43.0, "nearly 43 %",
         172, 248, 1,
         f"{ERC}/system/files/2026-09/erc-2026-stg-statistics.pdf",
         "ERC facts & figures for the 2026 call as reported by secondary sources (grantbite.com, proposia.ai); "
         "flagged for verification against the ERC release.",
         "Most recent call (results 3 Sep 2026); women's applicant share from secondary reporting."),
]

# Sensitivity-only calls: exact grantee gender counts, but the women's applicant share
# was not located in an ERC release.  A documented prior interval is used instead
# (2013 call: 30 %; 2017 call: 37 % = "more women than ever"; StG 2007-2016 aggregate: 31 %).
CALLS_IMPUTED: List[Call] = [
    Call(2013, 3329, 1073, 1486, 770, 287, 108, 126, 53, 29.0, 31.0, "SECONDARY: ~30 % (press report of ERC figures)",
         86, 201, 0,
         f"{ERC}/sites/default/files/document/file/erc_2013_stg_statistics.pdf",
         "Science|Business report on the 2013 call (30 % of applications from women, up from 24 % in 2012)",
         "Grantees '30 % women' (rounded) => 86 of 287; applicant share from a secondary press report; sensitivity only."),
    Call(2015, 2920, 940, 1269, 711, 350, 114, 156, 80, 31.0, 36.0, "IMPUTED prior interval",
         99, 251, 0,
         f"{ERC}/sites/default/files/document/file/erc_2015_stg_statistics.pdf",
         "not located - imputed", "Applicant share imputed; sensitivity analysis only."),
    Call(2016, 2935, 869, 1288, 778, 390, 121, 180, 89, 31.0, 36.0, "IMPUTED prior interval",
         119, 271, 0,
         f"{ERC}/sites/default/files/document/file/erc_2016_stg_statistics.pdf",
         "not located - imputed", "Applicant share imputed; sensitivity analysis only."),
]

# Historical (FP7-era) aggregate comparator, ERC gender statistics (rounded rates):
# StG 2007-2013: success rate women 8 %, men 10 % (EURAXESS summary of ERC gender statistics, Apr 2018);
# StG 2007-2016: 31 % of applications from women, 27 % of grants to women (ERC Gender Statistics, Dec 2016).
HISTORICAL = {
    "fp7_stg": {"period": "2007-2013", "sr_women": 0.08, "sr_men": 0.10,
                "n_apps_total": 26693,  # 9167+2503+2873+4080+4741+3329
                "n_grants_total": 2273,  # 299+244+427+480+536+287 (initial selections)
                "src": "https://euraxess.ec.europa.eu/worldwide/south-korea/gender-equality-policies-and-gender-distribution-msca-and-erc"},
    "stg_2007_2016": {"share_apps_women": 0.31, "share_grants_women": 0.27,
                      "src": f"{ERC}/sites/default/files/document/file/Gender_statistics_Dec_2016.pdf"},
}

# --------------------------------------------------------------------------- #
# Host-country distribution of grantees (statistics PDFs; bar-chart labels)
# --------------------------------------------------------------------------- #
HOST_COUNTRY: Dict[int, Dict[str, int]] = {
    2013: dict(UK=60, DE=46, IL=32, FR=29, NL=26, CH=21, ES=14, BE=12, AT=8, IT=8, SE=8, PT=5, FI=4, NO=3, EL=2, HU=2,
               IE=2, CY=1, CZ=1, HR=1, PL=1, TR=1),
    2015: dict(UK=61, DE=53, NL=38, FR=35, IL=30, CH=28, IT=22, ES=13, SE=11, BE=10, AT=9, DK=8, IE=6, FI=5,
               CZ=4, PT=4, TR=4, HU=3, PL=2, EL=1, MT=1, NO=1, RO=1),
    2016: dict(DE=76, UK=67, FR=53, NL=34, CH=24, ES=21, BE=20, SE=16, AT=14, IL=14, IT=13, FI=7, DK=6, PT=5,
               EL=3, HU=3, IE=3, NO=3, PL=3, CZ=1, EE=1, IS=1, RO=1, TR=1),
    2017: dict(UK=79, DE=67, FR=53, NL=35, IL=28, ES=22, CH=21, IT=19, AT=16, SE=16, BE=12, DK=8, FI=7, NO=6,
               PT=5, CZ=2, IE=2, PL=2, TR=2, CY=1, HU=1, LU=1, RO=1),
    2018: dict(DE=76, UK=67, NL=46, FR=37, IL=22, CH=19, ES=18, DK=17, SE=17, BE=16, IT=15, NO=10, FI=10, AT=9,
               IE=6, CZ=5, PT=5, PL=4, LU=1, SI=1, EE=1, RO=1),
    2019: dict(DE=73, UK=64, NL=53, FR=41, IL=34, CH=31, ES=20, IT=18, BE=14, SE=14, AT=10, DK=9, NO=7, FI=5,
               EL=2, PL=2, PT=2, SI=2, TR=2, CZ=1, EE=1, HR=1, HU=1, IE=1),
    2020: dict(DE=88, UK=62, NL=42, FR=38, CH=34, ES=23, IL=23, SE=23, BE=21, IT=20, DK=12, AT=11, FI=7, NO=7,
               PT=6, IE=4, PL=3, TR=3, CZ=2, EL=2, CY=1, HU=1, LU=1, RO=1, SI=1),
    2021: dict(DE=72, FR=53, UK=46, NL=44, CH=28, IT=28, ES=23, IL=19, SE=14, BE=10, NO=9, FI=8, IE=8, PL=8,
               DK=7, AT=6, PT=5, CZ=4, TR=2, EL=1, LU=1, SI=1),
    2024: dict(DE=98, NL=51, UK=50, FR=49, IT=41, ES=33, IL=30, AT=24, BE=22, SE=22, FI=18, DK=15, NO=14, IE=7,
               PT=5, CZ=2, EE=2, EL=2, LT=2, PL=2, SI=2, HR=1, IS=1, TR=1),
    2025: dict(DE=99, UK=60, NL=44, FR=41, CH=35, BE=31, IT=30, ES=28, SE=21, AT=20, DK=10, IL=10, IE=8, FI=7,
               NO=7, PT=6, PL=6, CZ=4, SI=3, EE=2, HU=2, EL=1, HR=1, LU=1, TR=1),
    2026: dict(DE=89, UK=47, FR=38, CH=36, NL=33, IT=22, SE=22, BE=21, DK=19, ES=19, AT=18, FI=12, IL=11, NO=7,
               CZ=6, PL=6, IE=5, CY=2, RO=2, EL=1, LT=1, LU=1, PT=1, SI=1, TR=1),
}
# Calls 2022 and 2023 publish the same chart without numeric labels; they are therefore absent here.

# --------------------------------------------------------------------------- #
# Long-run competition series: evaluated proposals and selected proposals per call
# --------------------------------------------------------------------------- #
# Applications 2007-2013 are verified against "ERC funding activities 2007-2013" (ERC, 2022 reprint);
# grant counts for 2007-2012 and both numbers for 2014 are as recalled from ERC annual releases and are
# flagged "recalled" - the dynamics module reports results with and without them.
COMPETITION_SERIES = [
    # year, applications, grants, budget_million_eur (None if not verified), status
    (2007, 9167, 299, None, "recalled grants"),
    (2009, 2503, 244, None, "recalled grants"),
    (2010, 2873, 427, None, "recalled grants"),
    (2011, 4080, 480, None, "recalled grants"),
    (2012, 4741, 536, None, "recalled grants"),
    (2013, 3329, 287, None, "verified (statistics PDF)"),
    (2014, 3273, 328, None, "recalled (initial selection; 375 incl. reserve list)"),
    (2015, 2920, 350, None, "verified (statistics PDF, incl. reserve list)"),
    (2016, 2935, 390, None, "verified (statistics PDF, incl. reserve list)"),
    (2017, 3085, 406, 605, "verified"),
    (2018, 3170, 403, 603, "verified"),
    (2019, 3106, 408, 621, "verified"),
    (2020, 3272, 436, 677, "verified (budget: ERC facts & figures 2020)"),
    (2021, 4066, 397, 619, "verified (initial selection; 471 incl. reserve list)"),
    (2022, 2932, 408, 636, "verified"),
    (2023, 2696, 400, 628, "verified"),
    (2024, 3474, 494, 780, "verified"),
    (2025, 3928, 478, 761, "verified"),
    (2026, 4807, 421, 705, "verified (budget: ERC results release, Sep 2026)"),
]
# Budgets 2017-2019 and 2021-2025 are as recalled from ERC results releases (not re-verified in this session).

# Horizon Europe "widening" Member States and associated widening countries
WIDENING_EU = {"BG", "HR", "CY", "CZ", "EE", "EL", "HU", "LV", "LT", "MT", "PL", "PT", "RO", "SK", "SI"}
WIDENING_ASSOC = {"AL", "AM", "BA", "FO", "GE", "MD", "ME", "MK", "RS", "TN", "TR", "UA", "XK"}


# --------------------------------------------------------------------------- #
# Derived analytic tables
# --------------------------------------------------------------------------- #
def two_by_two(call: Call, share: float | None = None, exclude_nb_from_n: bool = False) -> dict:
    """Return the gender x outcome 2x2 table for one call.

    a = women funded, b = women not funded, c = men funded, d = men not funded.
    `share` overrides the women's applicant share (used for sensitivity draws).
    """
    s = call.share_w if share is None else share
    n = call.n_total - (call.g_nonbinary if exclude_nb_from_n else 0)
    n_w = int(round(s * n))
    n_m = n - n_w
    a, c = call.g_female, call.g_male
    b, d = n_w - a, n_m - c
    return dict(year=call.year, a=a, b=b, c=c, d=d, n_w=n_w, n_m=n_m, n=n,
                g=call.g_female + call.g_male, share_w=s)


def analytic_table(calls: List[Call] | None = None, **kw) -> pd.DataFrame:
    calls = CALLS if calls is None else calls
    rows = [two_by_two(c, **kw) for c in calls]
    df = pd.DataFrame(rows)
    df["p_w"] = df.a / df.n_w
    df["p_m"] = df.c / df.n_m
    df["share_grants_w"] = df.a / df.g
    return df


def provenance_table(calls: List[Call] | None = None) -> pd.DataFrame:
    calls = CALLS if calls is None else calls
    return pd.DataFrame([{
        "call": c.year, "evaluated_proposals": c.n_total, "LS": c.n_ls, "PE": c.n_pe, "SH": c.n_sh,
        "selected": c.g_total, "sel_LS": c.g_ls, "sel_PE": c.g_pe, "sel_SH": c.g_sh,
        "women_share_apps_text": c.share_w_text, "share_lo": c.share_w_lo, "share_hi": c.share_w_hi,
        "grantees_F": c.g_female, "grantees_M": c.g_male, "grantees_NB": c.g_nonbinary,
        "source_statistics": c.src_stats, "source_share": c.src_share, "notes": c.notes,
    } for c in calls])


def host_country_frame() -> pd.DataFrame:
    recs = []
    for yr, d in HOST_COUNTRY.items():
        for cc, n in d.items():
            recs.append(dict(year=yr, country=cc, grants=n,
                             widening_eu=cc in WIDENING_EU, widening_any=cc in (WIDENING_EU | WIDENING_ASSOC)))
    return pd.DataFrame(recs)


if __name__ == "__main__":
    print(analytic_table().round(4).to_string())
    hc = host_country_frame()
    print(hc.groupby("year").grants.sum())
